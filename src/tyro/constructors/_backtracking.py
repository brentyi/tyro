"""Backtracking parser for handling variable-length argument sequences."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._primitive_spec import PrimitiveConstructorSpec


def parse_with_backtracking(
    args: list[str],
    specs: tuple[PrimitiveConstructorSpec[Any], ...],
    is_repeating: bool = False,
) -> list[Any] | None:
    """Parse arguments using backtracking when specs have variable nargs.

    Args:
        args: List of string arguments to parse.
        specs: Tuple of PrimitiveConstructorSpec instances. If is_repeating=True,
            only the first spec is used repeatedly.
        is_repeating: If True, use specs[0] repeatedly until all args consumed.
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

        # For tuples like Tuple[Union[int, str], Union[float, Tuple[float, float]]]:
        result = parse_with_backtracking(
            args=["hello", "1.5", "2.5"],
            specs=(int_or_str_spec, float_or_pair_spec),
            is_repeating=False
        )
    """

    def backtrack(
        spec_idx: int, arg_idx: int, current_result: list[Any]
    ) -> list[Any] | None:
        """Recursively try to parse remaining arguments."""
        # Base cases.
        if is_repeating:
            # For repeating specs, success when all args consumed.
            if arg_idx == len(args):
                return current_result
            spec = specs[0]
        else:
            # For non-repeating specs, success when all specs processed.
            if spec_idx == len(specs):
                return current_result if arg_idx == len(args) else None
            if arg_idx == len(args):
                return None
            spec = specs[spec_idx]

        # Get nargs options for current spec.
        if spec.nargs == "*":
            raise ValueError("Backtracking parser does not support nargs='*'")
        nargs_options = (spec.nargs,) if isinstance(spec.nargs, int) else spec.nargs

        # Try each possible nargs value.
        for nargs_option in nargs_options:
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
                next_spec_idx = spec_idx if is_repeating else spec_idx + 1
                result = backtrack(
                    next_spec_idx,
                    arg_idx + nargs_option,
                    current_result + [parsed],
                )
                if result is not None:
                    return result
            except ValueError:
                # This option didn't work, try next.
                continue

        # No valid parse found from this position.
        return None

    return backtrack(0, 0, [])
