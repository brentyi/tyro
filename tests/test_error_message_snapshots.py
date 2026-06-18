# mypy: ignore-errors
"""Byte-for-byte snapshots of tyro's parse-error messages.

These pin the exact stderr rendering of every triggerable parse-failure
category so that refactors of the error/rendering path (e.g. routing error
output through tyro._errors._render) can be proven behavior-preserving.

Snapshots live in ``error_message_snapshots.json`` next to this file. To
regenerate intentionally (only when a message change is desired and reviewed),
run this module as a script: ``python tests/test_error_message_snapshots.py``.
"""

import contextlib
import dataclasses
import io
import json
import pathlib
from typing import Tuple, Union

import pytest
from typing_extensions import Annotated, Literal

import tyro

_SNAPSHOT_PATH = pathlib.Path(__file__).parent / "error_message_snapshots.json"


@dataclasses.dataclass
class _Cfg:
    token: str
    number: int
    name: str = "default"


@dataclasses.dataclass
class _A:
    a: int = 0


@dataclasses.dataclass
class _B:
    b: str
    flag: bool = False


_MG = tyro.conf.create_mutex_group(required=True)


def _mgfn(
    option_a: Annotated[Union[str, None], _MG] = None,
    option_b: Annotated[Union[int, None], _MG] = None,
) -> None:
    del option_a, option_b


_OG = tyro.conf.create_mutex_group(required=False)


def _ogfn(
    option_a: Annotated[Union[str, None], _OG] = None,
    option_b: Annotated[Union[int, None], _OG] = None,
) -> None:
    del option_a, option_b


_PMG = tyro.conf.create_mutex_group(required=True)


@dataclasses.dataclass
class _PosMutex:
    # A *positional* argument inside a required mutex group: when the group is
    # unsatisfied, the missing-mutex renderer formats positionals by metavar
    # (e.g. 'pos') rather than by flag.
    pos: Annotated[tyro.conf.Positional[Union[int, None]], _PMG] = None
    option_b: Annotated[Union[str, None], _PMG] = None


@dataclasses.dataclass
class _Pair:
    xy: Tuple[int, int]


@dataclasses.dataclass
class _Ch:
    mode: Literal["a", "b", "c"] = "a"


@dataclasses.dataclass
class SubA:
    required_a: int  # required arg living inside subcommand a


@dataclasses.dataclass
class SubB:
    required_b: str


@dataclasses.dataclass
class _Nested:
    sub: Union[SubA, SubB]


# label -> (callable/type, args). prog is pinned to "prog" for stable output.
_CASES = {
    "missing_args": (_Cfg, ["--name", "x"]),
    "missing_mutex_group": (_mgfn, []),
    # Required mutex group whose members include a positional argument: covers
    # the positional branch of the missing-mutex renderer (rendered by metavar).
    "missing_mutex_group_with_positional": (_PosMutex, []),
    "missing_subcommand": (Union[_A, _B], []),
    "mutex_conflict": (_ogfn, ["--option-a", "x", "--option-b", "3"]),
    "bad_value_too_few": (_Pair, ["--xy", "1"]),
    "invalid_choice": (_Ch, ["--mode", "z"]),
    "unrecognized_args": (
        _Cfg,
        ["--token", "t", "--number", "1", "--bogus", "x"],
    ),
    "instantiation_failure": (_Cfg, ["--number", "notint", "--token", "t"]),
    # Missing a required arg *inside a selected subcommand* exercises the
    # multi-prog footer (prog spans "prog sub:sub-a"), which the flat cases
    # above do not cover. The subcommand must actually be selected: SubA/SubB
    # have no leading underscore, so the names are "sub:sub-a"/"sub:sub-b".
    "missing_args_in_subcommand": (_Nested, ["sub:sub-a"]),
    # Missing required arg AND an unrecognized token together exercises the
    # trailing "Unrecognized options" block of the missing-args renderer.
    "missing_args_with_unrecognized": (_Nested, ["sub:sub-a", "--bogus"]),
    # NOTE: two _render branches are not snapshot here because they have no
    # stable public trigger -- SubcommandConflict (needs a default subcommand
    # whose flag implicitly selects it, then an explicit conflicting selection)
    # and BadValue(reason="fixed"). They are covered structurally by
    # test_parse_error_hooks.test_structural_event_construction instead.
    #
    # The BadValue(reason="too_few_values") *variadic* branch ("Expected at
    # least one value.") is also unsnapshotted: it only fires for
    # nargs="+" (_tyro_backend.py), but LoweredArgumentDefinition.nargs is
    # only ever int/"*"/"?" -- "+" is never produced, so that branch is
    # currently unreachable. The fixed-arity too_few_values path is covered by
    # "bad_value_too_few" above.
}


def _capture(cls, args) -> str:
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            tyro.cli(cls, args=args, prog="prog")
    except SystemExit:
        pass
    return stderr.getvalue()


@pytest.fixture(autouse=True)
def _require_native_backend(backend):
    # Snapshots are of the native ("tyro") backend's rendering; argparse differs.
    if backend != "tyro":
        pytest.skip("error-message snapshots target the native backend only")


@pytest.mark.parametrize("label", list(_CASES.keys()))
def test_error_message_snapshot(label: str) -> None:
    snapshots = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    cls, args = _CASES[label]
    actual = _capture(cls, args)
    assert actual != "", f"{label} produced no stderr output"
    assert actual == snapshots[label], (
        f"Rendered error for {label!r} changed. If intentional, regenerate via "
        f"`python {pathlib.Path(__file__).name}`."
    )


def _regenerate() -> None:
    snapshots = {label: _capture(*case) for label, case in _CASES.items()}
    _SNAPSHOT_PATH.write_text(
        json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {len(snapshots)} snapshots to {_SNAPSHOT_PATH}")


if __name__ == "__main__":
    _regenerate()
