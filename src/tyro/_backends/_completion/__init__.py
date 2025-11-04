"""Shell completion generation for tyro."""

from __future__ import annotations

from ._base import CompletionGenerator
from ._tyro_bash import TyroBashCompletionGenerator
from ._tyro_zsh import TyroZshCompletionGenerator

__all__ = [
    "CompletionGenerator",
    "TyroBashCompletionGenerator",
    "TyroZshCompletionGenerator",
]
