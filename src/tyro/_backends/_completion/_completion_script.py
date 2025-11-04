"""Standalone completion script for tyro.

This module contains the completion logic that gets embedded in bash/zsh scripts.
It uses only Python stdlib and is compatible with Python 3.8+.

This file is designed to be:
1. Type-checked by pyright
2. Unit tested directly
3. Embedded as a string in generated completion scripts
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Tuple


def reconstruct_colon_words(
    words: List[str], current_word_index: int, spec: Dict[str, Any]
) -> Tuple[List[str], int]:
    """Reconstruct words that were split by bash on colons.

    Bash treats ':' as a word separator by default, so typing "dataset:mnist"
    results in words like ["dataset", ":", "mnist"]. This function detects
    such patterns and merges them back together, but only when the merged
    result matches a known subcommand (or is a prefix of one).

    Args:
        words: List of words from the command line (without program name).
        current_word_index: Index of the word being completed (0-based).
        spec: Completion specification dictionary.

    Returns:
        Tuple of (reconstructed_words, new_current_word_index).
    """
    # Get all known subcommands for validation.
    all_subcommands = set(spec.get("subcommands", {}).keys())

    reconstructed = []
    new_cword = current_word_index
    i = 0

    while i < len(words):
        # Pattern 1: word : word (fully typed colon-separated value).
        if (
            i + 2 < len(words)
            and words[i + 1] == ":"
            and not words[i].startswith("-")
            and not words[i + 2].startswith("-")
        ):
            # Tentatively merge.
            merged = words[i] + ":" + words[i + 2]

            # Check if merged matches a known subcommand or is a prefix.
            is_valid = any(
                cmd == merged or cmd.startswith(merged) for cmd in all_subcommands
            )

            if is_valid:
                reconstructed.append(merged)
                # Adjust current word index if we're in or past the merged region.
                if current_word_index >= i + 2:
                    new_cword -= 2
                elif current_word_index == i + 1:
                    # Cursor is on the colon itself.
                    new_cword = len(reconstructed) - 1
                i += 3
                continue

        # Pattern 2: word : (partial typing, colon at end).
        if i + 1 < len(words) and words[i + 1] == ":" and not words[i].startswith("-"):
            merged = words[i] + ":"

            # Check if any subcommand starts with this prefix.
            is_valid = any(cmd.startswith(merged) for cmd in all_subcommands)

            if is_valid:
                reconstructed.append(merged)
                if current_word_index >= i + 1:
                    new_cword -= 1
                elif current_word_index == i:
                    new_cword = len(reconstructed) - 1
                i += 2
                continue

        # Pattern 3: : word (typing after colon).
        if (
            i > 0
            and words[i] == ":"
            and i + 1 < len(words)
            and not words[i + 1].startswith("-")
        ):
            # Check if previous word exists and could form a subcommand.
            if reconstructed and not reconstructed[-1].startswith("-"):
                merged = reconstructed[-1] + ":" + words[i + 1]
                is_valid = any(
                    cmd == merged or cmd.startswith(merged) for cmd in all_subcommands
                )

                if is_valid:
                    # Replace the last reconstructed word with the merged version.
                    reconstructed[-1] = merged
                    if current_word_index >= i + 1:
                        new_cword -= 1
                    i += 2
                    continue

        # No merge pattern matched.
        if words[i] != ":":  # Skip standalone colons that weren't merged.
            reconstructed.append(words[i])
            i += 1
        else:
            # Standalone colon that didn't match any pattern.
            if current_word_index > i:
                new_cword -= 1
            i += 1

    return reconstructed, new_cword


def get_completions(
    words: List[str], current_word_index: int, spec: Dict[str, Any]
) -> List[str]:
    """Get completions for the current position.

    Args:
        words: List of words on the command line (including the program name).
        current_word_index: Index of the word being completed (0-based).
        spec: Completion specification dictionary.

    Returns:
        List of completion strings in "completion\tdescription" format.
    """
    # Skip the program name.
    if current_word_index == 0:
        return []

    words = words[1:]  # Remove program name.
    current_word_index -= 1

    # Reconstruct words that were split by bash on colons.
    words, current_word_index = reconstruct_colon_words(words, current_word_index, spec)

    # Get the word being completed.
    current_word = words[current_word_index] if current_word_index < len(words) else ""

    # Helper function to navigate to current context.
    def navigate_to_context(end_index: int) -> Dict[str, Any]:
        """Navigate through subcommands and options to find current context."""
        ctx = spec
        i = 0
        while i < end_index:
            word = words[i]
            if word in ctx.get("subcommands", {}):
                ctx = ctx["subcommands"][word]
                i += 1
            elif word.startswith("-"):
                # Skip options and their arguments.
                takes_arg = False
                for opt in ctx.get("options", []):
                    if word in opt["flags"]:
                        if opt["type"] not in ("flag", "boolean"):
                            takes_arg = True
                        break
                i += 1
                if takes_arg and i < end_index:
                    i += 1  # Skip the argument value.
            else:
                i += 1
        return ctx

    # Check if we're completing an option argument (like after --mode).
    # This includes nargs>1 cases like: --modes train <TAB>
    if current_word_index > 0:
        # Navigate to current context.
        current_spec = navigate_to_context(current_word_index)

        # Look backwards to find if we're filling an option argument.
        for j in range(current_word_index - 1, -1, -1):
            prev = words[j]
            if prev.startswith("-"):
                # Found an option flag.
                for opt in current_spec.get("options", []):
                    if prev in opt["flags"]:
                        # Check if this option takes arguments and has choices.
                        if opt["type"] == "choice" and "choices" in opt:
                            # Check if we should still be completing values for this option.
                            # This handles nargs > 1 (e.g., nargs=2, nargs='+', nargs='*').
                            nargs = opt.get("nargs")
                            if nargs in ("+", "*") or (
                                isinstance(nargs, int) and nargs > 1
                            ):
                                # Multi-value option: keep offering choices.
                                # Count how many values we've already provided.
                                values_provided = current_word_index - j - 1
                                if isinstance(nargs, int):
                                    # Stop if we've provided enough values.
                                    if values_provided >= nargs:
                                        break
                                # Continue offering choices.
                                completions = []
                                for choice in opt["choices"]:
                                    if str(choice).startswith(current_word):
                                        completions.append(f"{choice}\t{choice}")
                                return completions
                            elif j == current_word_index - 1:
                                # Single-value option: only complete if immediately after flag.
                                completions = []
                                for choice in opt["choices"]:
                                    if str(choice).startswith(current_word):
                                        completions.append(f"{choice}\t{choice}")
                                return completions
                        elif (
                            opt["type"] not in ("flag", "boolean")
                            and j == current_word_index - 1
                        ):
                            # For other option types, don't provide completions.
                            return []
                # We found a flag, stop searching.
                break

    # Navigate to the current subcommand context.
    # Keep track of root spec and selected frontier subcommands.
    root_spec = spec
    current_spec = spec
    used_words = set()
    selected_frontier_subcommands = []
    has_frontier = len(spec.get("frontier_groups", [])) > 0
    i = 0

    while i < current_word_index:
        word = words[i]
        used_words.add(word)

        # Check if this word is a subcommand.
        if word in spec.get("subcommands", {}):
            # In frontier mode, don't navigate into subcommands - stay at root.
            # Instead, track selected frontier subcommands for cascade options.
            if has_frontier:
                selected_frontier_subcommands.append(word)
                i += 1
            else:
                # Normal mode: navigate into the subcommand.
                current_spec = current_spec["subcommands"][word]
                i += 1
        elif word.startswith("-"):
            # Skip options and their arguments.
            # Find the option definition to see if it takes an argument.
            takes_arg = False
            for opt in current_spec.get("options", []):
                if word in opt["flags"]:
                    if opt["type"] not in ("flag", "boolean"):
                        takes_arg = True
                    break

            i += 1
            if takes_arg and i < current_word_index:
                i += 1  # Skip the argument value.
        else:
            i += 1

    # Generate completions.
    completions = []

    # Add available options from current spec.
    for opt in current_spec.get("options", []):
        for flag in opt["flags"]:
            if flag.startswith(current_word):
                # Format: flag\tdescription (tab-separated).
                completions.append(f"{flag}\t{opt['description']}")

    # In frontier mode, also add cascade options from selected subcommands.
    if has_frontier and selected_frontier_subcommands:
        for subcmd in selected_frontier_subcommands:
            subcmd_spec = root_spec["subcommands"].get(subcmd, {})
            for opt in subcmd_spec.get("options", []):
                # Only include options marked as cascade.
                if opt.get("cascade", False):
                    for flag in opt["flags"]:
                        if flag.startswith(current_word):
                            completions.append(f"{flag}\t{opt['description']}")

    # Add available subcommands.
    # Only use root frontier groups if we're still at root level.
    frontier_groups = current_spec.get("frontier_groups", [])
    if not frontier_groups and current_spec == root_spec:
        frontier_groups = root_spec.get("frontier_groups", [])

    if frontier_groups:
        # Frontier mode: offer subcommands from groups that haven't been used yet.
        for group in frontier_groups:
            # Check if any subcommand from this group has been used.
            group_used = any(cmd in used_words for cmd in group)
            if not group_used:
                # Offer all subcommands from this group.
                for cmd in group:
                    if cmd.startswith(current_word):
                        # Look up description from root spec.
                        desc = (
                            root_spec["subcommands"]
                            .get(cmd, {})
                            .get("description", cmd)
                        )
                        completions.append(f"{cmd}\t{desc}")
    else:
        # Normal mode: offer all subcommands.
        for cmd, cmd_spec in current_spec.get("subcommands", {}).items():
            if cmd.startswith(current_word):
                completions.append(f"{cmd}\t{cmd_spec['description']}")

    return completions


def main() -> None:
    """Main entrypoint when run as a script.

    Expects command line arguments in the format:
    <word1> <word2> ... <wordN> <current_index>

    The COMPLETION_SPEC variable should be defined before calling this.
    """
    if len(sys.argv) < 2:
        sys.exit(0)

    current_index = int(sys.argv[-1])
    words = sys.argv[1:-1]

    # COMPLETION_SPEC is expected to be defined in the embedding context.
    completions = get_completions(words, current_index, COMPLETION_SPEC)  # type: ignore[name-defined]  # noqa: F821

    # Output one completion per line.
    for completion in completions:
        print(completion)


if __name__ == "__main__":
    main()
