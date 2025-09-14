"""Adapted from @mirceamironenco.

https://github.com/brentyi/tyro/issues/340"""

from __future__ import annotations

from dataclasses import dataclass

from helptext_utils import get_helptext_with_checks

import tyro


@dataclass(frozen=True)
class HFSFTDatasetConfig:
    name: str
    split: str | None = None
    data_files: str | None = None

    completions_only: bool = True
    packed_seqlen: int | None = None
    apply_chat_template: bool = False
    max_seq_len: int | None = None

    columns: tuple[str, str, str | None, str | None] | None = None
    """instruction, completion, input, system"""


@dataclass
class Config:
    train_data: HFSFTDatasetConfig = HFSFTDatasetConfig(
        name="yahma/alpaca-cleaned",
        completions_only=True,
        packed_seqlen=4097,
        max_seq_len=2048,
        apply_chat_template=True,
        columns=("instruction", "output", "input", None),
    )


def test_mixed_primitive() -> None:
    assert (
        tyro.cli(
            Config,
            args=["--train-data.name", "foo", "--train-data.completions-only"],
        ).train_data.name
        == "foo"
    )
    assert "None}|{STR STR {None}|STR {None}|STR}" in get_helptext_with_checks(Config)
