"""Backtracking parser for handling variable-length argument sequences."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._primitive_spec import PrimitiveConstructorSpec


@dataclasses.dataclass
class BacktrackState:
    """State for backtracking parser."""

    spec_idx: int
    arg_idx: int
    parsed_value: Any | None  # The value parsed at this state, if any.
    parent: BacktrackState | None  # Link to parent state to reconstruct path.
    nargs_option_idx: int
    # `arg_idx` at the start of the current cycle (only meaningful when
    # `is_repeating`). Used to detect a full cycle of specs that consumed zero
    # arguments, which would otherwise loop forever (e.g. a repeated zero-width
    # spec like the empty tuple `Tuple[()]`).
    cycle_start_arg_idx: int = 0


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

    # Use iterative approach with explicit stack to avoid recursion limit.
    stack: list[BacktrackState] = [BacktrackState(0, 0, None, None, 0, 0)]

    def reconstruct_path(state: BacktrackState) -> list[Any]:
        """Reconstruct the parsed values from the state chain."""
        result = []
        current: BacktrackState | None = state
        while current is not None:
            if current.parent is not None:  # Skip the initial state
                result.append(current.parsed_value)
            current = current.parent
        return list(reversed(result))

    while stack:
        state = stack.pop()
        spec_idx = state.spec_idx
        arg_idx = state.arg_idx
        nargs_option_idx = state.nargs_option_idx

        # Base cases.
        cycle_start_arg_idx = state.cycle_start_arg_idx
        if is_repeating:
            # For repeating specs, success when all args consumed.
            if arg_idx == len(args):
                # When repeating multiple specs, ensure we completed full cycles.
                if len(specs) > 1 and spec_idx % len(specs) != 0:
                    # Known limitation: a repeating multi-spec whose *trailing*
                    # spec is zero-width (e.g. `Dict[str, Tuple[()]]`) is
                    # rejected here. Closing the cycle with the empty match
                    # would bypass the zero-progress pruning below, which is
                    # load-bearing for disambiguating unions. Such types are
                    # impractical, so we accept the clean rejection.
                    continue  # Incomplete cycle, not a valid parse.
                return reconstruct_path(state)
            # At a cycle boundary, detect a full cycle that consumed zero
            # arguments. Such a path can never consume the remaining args and
            # would loop forever (e.g. a repeated zero-width spec); prune it.
            if spec_idx > 0 and spec_idx % len(specs) == 0:
                if arg_idx == cycle_start_arg_idx:
                    continue
                cycle_start_arg_idx = arg_idx  # A new cycle begins here.
            spec = specs[spec_idx % len(specs)]
        else:
            # For non-repeating specs, success when all specs processed.
            if spec_idx == len(specs):
                if arg_idx == len(args):
                    return reconstruct_path(state)
                else:
                    continue
            spec = specs[spec_idx]
            if arg_idx == len(args):
                # All arguments consumed, but specs remain. A spec that can
                # match zero arguments (e.g. the empty tuple `Tuple[()]` with
                # nargs=0) can still complete the parse; otherwise this path is
                # dead. Positive-nargs specs are pruned naturally below.
                zero_ok = spec.nargs in ("*", 0) or (
                    isinstance(spec.nargs, tuple) and 0 in spec.nargs
                )
                if not zero_ok:
                    continue

        # Get nargs options for current spec.
        if spec.nargs == "*":
            # For nargs='*', try all possible lengths from 0 to remaining args.
            # Try longer matches first to prefer consuming more args.
            nargs_options = tuple(range(len(args) - arg_idx, -1, -1))
        else:
            nargs_options = (spec.nargs,) if isinstance(spec.nargs, int) else spec.nargs

        # Check if we've tried all nargs options for this state.
        if nargs_option_idx >= len(nargs_options):
            continue

        # Push state for trying next nargs option.
        if nargs_option_idx + 1 < len(nargs_options):
            stack.append(
                BacktrackState(
                    spec_idx,
                    arg_idx,
                    state.parsed_value,
                    state.parent,
                    nargs_option_idx + 1,
                    state.cycle_start_arg_idx,
                )
            )

        # Try current nargs option.
        nargs_option = nargs_options[nargs_option_idx]
        if arg_idx + nargs_option > len(args):
            continue

        # Extract candidate arguments.
        candidate_args = args[arg_idx : arg_idx + nargs_option]
        if spec.choices is not None and any(
            arg not in spec.choices for arg in candidate_args
        ):
            continue

        try:
            # Try to parse this chunk.
            parsed = spec.instance_from_str(candidate_args)
            next_spec_idx = spec_idx + 1

            # Push new state to explore this path.
            stack.append(
                BacktrackState(
                    next_spec_idx,
                    arg_idx + nargs_option,
                    parsed,
                    state,
                    0,
                    cycle_start_arg_idx,
                )
            )
        except ValueError:
            # This option didn't work, will try next via the pushed state above.
            continue

    # No valid parse found.
    return None
