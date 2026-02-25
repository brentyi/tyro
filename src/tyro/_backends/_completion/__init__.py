"""Shell completion generation for tyro."""

from __future__ import annotations

from ._base import CompletionGenerator
from ._tyro_bash import TyroBashCompletionGenerator
from ._tyro_zsh import TyroZshCompletionGenerator
from ._tyro_fish import TyroFishCompletionGenerator

__all__ = [
    "CompletionGenerator",
    "TyroBashCompletionGenerator",
    "TyroZshCompletionGenerator",
    "TyroFishCompletionGenerator",
]
