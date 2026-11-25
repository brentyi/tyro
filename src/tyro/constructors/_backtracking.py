"""Backtracking parser for handling variable-length argument sequences."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator

if TYPE_CHECKING:
    from ._primitive_spec import PrimitiveConstructorSpec


class LazyValueError(ValueError):
    """A ValueError with a message that's formatted only when it's needed. Formatting can
    be slow, and backtracking will discard most errors."""

    def __init__(self, message: Callable[[], str]) -> None:
        self._message = message
        super().__init__()

    @property
    def args(self) -> tuple[str]:  # type: ignore
        return (self._message(),)

    def __str__(self) -> str:
        return self._message()


def mark_as_scalar(
    instance_from_str: Callable[[list[str]], Any], scalar_fn: Callable[[str], Any]
) -> None:
    """Annotate an `instance_from_str(args)` function as being equivalent to
    `scalar_fn(args[0])`. This is used for parsing long sequences efficiently.

    We annotate functions and not `PrimitiveConstructorSpec` objects, because the latter
    can be copied with `dataclasses.replace(spec, instance_from_str=...)`."""
    instance_from_str.__tyro_scalar_fns__ = scalar_fn  # type: ignore


def mark_as_tuple(
    instance_from_str: Callable[[list[str]], Any],
    specs: list[PrimitiveConstructorSpec[Any]],
) -> None:
    """Annotate an `instance_from_str(args)` function as being equivalent to
    `(specs[0].instance_from_str(args[:1]), specs[1].instance_from_str(args[1:2]), ...)`,
    if all of these are scalars."""
    scalar_fns = [get_scalar_fns(spec) for spec in specs]
    if len(specs) > 0 and all(map(callable, scalar_fns)):
        instance_from_str.__tyro_scalar_fns__ = tuple(scalar_fns)  # type: ignore


def get_scalar_fns(
    spec: PrimitiveConstructorSpec[Any],
) -> Callable[[str], Any] | tuple[Callable[[str], Any], ...] | None:
    """Get the function(s) attached by `mark_as_scalar()` or `mark_as_tuple()`."""
    if spec.choices is not None:
        return None
    return getattr(spec.instance_from_str, "__tyro_scalar_fns__", None)


def parse_with_backtracking(
    args: list[str],
    specs: tuple[PrimitiveConstructorSpec[Any], ...],
    is_repeating: bool = False,
) -> list[Any] | None:
    """Parse arguments using backtracking when specs have variable nargs.

    Args:
        args: List of string arguments to parse.
        specs: Tuple of PrimitiveConstructorSpec instances.
        is_repeating: If True with single spec, use specs[0] repeatedly.
            If True with multiple specs, repeat the entire sequence of specs.
            If False, use each spec in order exactly once.

    Returns:
        List of parsed values if successful, None if no valid parse exists.

    Examples:
        # For sequences like List[Union[int, Tuple[int, int]]]:
        result = parse_with_backtracking(
            args=["1", "2", "3", "4"],
            specs=(spec_with_nargs_1_or_2,),
            is_repeating=True
        )

        # For dicts like Dict[str, Union[int, Tuple[int, int]]]:
        result = parse_with_backtracking(
            args=["key1", "1", "2", "key2", "3"],
            specs=(key_spec, val_spec),
            is_repeating=True
        )

        # For tuples like Tuple[Union[int, str], Union[float, Tuple[float, float]]]:
        result = parse_with_backtracking(
            args=["hello", "1.5", "2.5"],
            specs=(int_or_str_spec, float_or_pair_spec),
            is_repeating=False
        )
    """

    if len(specs) == 0:
        # The empty tuple type `Tuple[()]` produces zero inner specs. The only
        # valid parse consumes zero arguments. (This is reached when an empty
        # tuple is nested inside another container, whose parser invokes the
        # empty tuple's instantiator.)
        return [] if len(args) == 0 else None

    # Fast path: there's no ambiguity when all argument counts are fixed.
    if all(isinstance(spec.nargs, int) and spec.nargs > 0 for spec in specs):
        return _parse_fixed(args, specs, is_repeating)

    num_args = len(args)
    num_specs = len(specs)

    # Valid argument counts for each spec, in the order that they should be attempted.
    # `None` if any number of arguments is valid.
    nargs_options_from_spec: list[tuple[int, ...] | None] = []
    for spec in specs:
        if spec.nargs == "*":
            nargs_options_from_spec.append(None)
        elif isinstance(spec.nargs, int):
            nargs_options_from_spec.append((spec.nargs,))
        else:
            nargs_options_from_spec.append(spec.nargs)

    # We run a depth-first search. Each frame in our stack corresponds to a state:
    #
    # - The index of the next spec. This is taken modulo `num_specs`.
    # - The index of the next argument.
    # - `arg_idx` at the start of the current cycle (only meaningful when
    #   `is_repeating`). Used to detect a full cycle of specs that consumed zero
    #   arguments, which would otherwise loop forever (e.g. a repeated zero-width
    #   spec like the empty tuple `Tuple[()]`).
    # - An iterator over argument counts that we haven't attempted yet.
    #
    # `values[i]` is the parsed value used to transition from `stack[i]` to
    # `stack[i + 1]`.
    #
    # An explicit stack lets us avoid the recursion limit.
    stack: list[tuple[int, int, int, Iterator[int]]] = []
    values: list[Any] = []

    # The outcome of each state is fully determined by this key: the spec, the argument,
    # and whether any arguments have been consumed in this cycle. If we're seeing a state
    # for a second time, we already know that we can't succeed from it.
    visited: set[tuple[int, int, bool]] = set()

    # State that we're about to enter.
    spec_idx = 0
    arg_idx = 0
    cycle_start = 0
    while True:
        # Check if the state that we're entering is complete or a dead end.
        is_dead_end = False
        key: tuple[int, int, bool] | None = None
        if is_repeating:
            # For repeating specs, success when all args consumed.
            if arg_idx == num_args:
                # When repeating multiple specs, ensure we completed full cycles.
                #
                # Known limitation: a repeating multi-spec whose *trailing*
                # spec is zero-width (e.g. `Dict[str, Tuple[()]]`) is
                # rejected here. Closing the cycle with the empty match
                # would bypass the zero-progress pruning below, which is
                # load-bearing for disambiguating unions. Such types are
                # impractical, so we accept the clean rejection.
                if spec_idx in (0, num_specs):
                    return values
                is_dead_end = True
            # At a cycle boundary, detect a full cycle that consumed zero
            # arguments. Such a path can never consume the remaining args and
            # would loop forever (e.g. a repeated zero-width spec); prune it.
            elif spec_idx == num_specs:
                if arg_idx == cycle_start:
                    is_dead_end = True
                cycle_start = arg_idx  # A new cycle begins here.
                spec_idx = 0
        elif spec_idx == num_specs:
            # For non-repeating specs, success when all specs processed.
            if arg_idx == num_args:
                return values
            is_dead_end = True

        if not is_dead_end:
            key = (spec_idx, arg_idx, arg_idx == cycle_start)
            is_dead_end = key in visited

        if is_dead_end:
            # Return to the previous state. This must exist; the initial state is never
            # a dead end unless there are no specs.
            values.pop()
            spec_idx, arg_idx, cycle_start, nargs_iter = stack[-1]
        else:
            assert key is not None
            visited.add(key)
            nargs_options = nargs_options_from_spec[spec_idx]
            nargs_iter = (
                # For nargs='*', try all possible lengths from 0 to remaining args.
                # Try longer matches first to prefer consuming more args.
                iter(range(num_args - arg_idx, -1, -1))
                if nargs_options is None
                else iter(nargs_options)
            )
            stack.append((spec_idx, arg_idx, cycle_start, nargs_iter))

        # Find the next transition, popping states that we've exhausted.
        while True:
            spec = specs[spec_idx]
            choices = spec.choices
            for nargs in nargs_iter:
                # Extract candidate arguments.
                next_arg_idx = arg_idx + nargs
                if next_arg_idx > num_args:
                    continue
                candidate_args = args[arg_idx:next_arg_idx]
                if choices is not None and any(
                    arg not in choices for arg in candidate_args
                ):
                    continue

                # Try to parse this chunk.
                try:
                    values.append(spec.instance_from_str(candidate_args))
                except ValueError:
                    continue

                spec_idx += 1
                arg_idx = next_arg_idx
                break
            else:
                stack.pop()
                if len(stack) == 0:
                    # No valid parse found.
                    return None
                values.pop()
                spec_idx, arg_idx, cycle_start, nargs_iter = stack[-1]
                continue
            break


def _parse_fixed(
    args: list[str],
    specs: tuple[PrimitiveConstructorSpec[Any], ...],
    is_repeating: bool,
) -> list[Any] | None:
    """Parse arguments when all specs have a fixed, nonzero number of arguments. This
    runs in linear time."""
    num_args = len(args)
    cycle_nargs = sum(spec.nargs for spec in specs)  # type: ignore
    if is_repeating:
        if num_args % cycle_nargs != 0:
            return None
    elif num_args != cycle_nargs:
        return None

    # Parsing long sequences of scalars is common, and can be vectorized.
    scalar_fns_from_spec = [get_scalar_fns(spec) for spec in specs]
    if None not in scalar_fns_from_spec:
        # We can think of this as parsing a table, where each row is a cycle.
        columns: list[Iterable[Any]] = []
        arg_idx = 0
        try:
            for scalar_fns in scalar_fns_from_spec:
                if isinstance(scalar_fns, tuple):
                    num_fns = len(scalar_fns)
                    columns.append(
                        zip(
                            *[
                                list(map(fn, args[arg_idx + i :: cycle_nargs]))
                                for i, fn in enumerate(scalar_fns)
                            ]
                        )
                    )
                else:
                    num_fns = 1
                    assert scalar_fns is not None
                    columns.append(list(map(scalar_fns, args[arg_idx::cycle_nargs])))
                arg_idx += num_fns
        except ValueError:
            return None
        if len(columns) == 1:
            return list(columns[0])
        return [value for row in zip(*columns) for value in row]

    if is_repeating and len(specs) == 1 and cycle_nargs == 1:
        (spec,) = specs
        choices = spec.choices
        if choices is not None and any(
            arg not in choices for arg in dict.fromkeys(args)
        ):
            return None
        instance_from_str = spec.instance_from_str
        try:
            return [instance_from_str([arg]) for arg in args]
        except ValueError:
            return None

    out: list[Any] = []
    arg_idx = 0
    while arg_idx < num_args:
        for spec in specs:
            nargs = spec.nargs
            assert isinstance(nargs, int)
            candidate_args = args[arg_idx : arg_idx + nargs]
            arg_idx += nargs
            choices = spec.choices
            if choices is not None and any(
                arg not in choices for arg in candidate_args
            ):
                return None
            try:
                out.append(spec.instance_from_str(candidate_args))
            except ValueError:
                return None
    return out
