"""Helpers for parsing dataclass docstrings. Used for helptext generation."""

import dataclasses
import functools
import inspect
import io
import tokenize
from typing import Dict, List, Optional, Type

from typing_extensions import get_origin

from . import _resolver, _strings


@dataclasses.dataclass(frozen=True)
class _Token:
    token_type: int
    content: str
    logical_line: int
    actual_line: int


@dataclasses.dataclass(frozen=True)
class _FieldData:
    index: int
    logical_line: int
    actual_line: int
    prev_field_logical_line: int


@dataclasses.dataclass(frozen=True)
class _ClassTokenization:
    tokens: List[_Token]
    tokens_from_logical_line: Dict[int, List[_Token]]
    tokens_from_actual_line: Dict[int, List[_Token]]
    field_data_from_name: Dict[str, _FieldData]

    @staticmethod
    @functools.lru_cache(maxsize=8)
    def make(clz) -> "_ClassTokenization":
        """Parse the source code of a class, and cache some tokenization information."""
        readline = io.BytesIO(inspect.getsource(clz).encode("utf-8")).readline

        tokens: List[_Token] = []
        tokens_from_logical_line: Dict[int, List[_Token]] = {1: []}
        tokens_from_actual_line: Dict[int, List[_Token]] = {1: []}
        field_data_from_name: Dict[str, _FieldData] = {}

        logical_line: int = 1
        actual_line: int = 1
        for toktype, tok, start, end, line in tokenize.tokenize(readline):
            # Note: we only track logical line numbers, which are delimited by
            # `tokenize.NEWLINE`. `tokenize.NL` tokens appear when logical lines are
            # broken into multiple lines of code; these are ignored.
            if toktype == tokenize.NEWLINE:
                logical_line += 1
                actual_line += 1
                tokens_from_logical_line[logical_line] = []
                tokens_from_actual_line[actual_line] = []
            elif toktype == tokenize.NL:
                actual_line += 1
                tokens_from_actual_line[actual_line] = []
            elif toktype is not tokenize.INDENT:
                token = _Token(
                    token_type=toktype,
                    content=tok,
                    logical_line=logical_line,
                    actual_line=actual_line,
                )
                tokens.append(token)
                tokens_from_logical_line[logical_line].append(token)
                tokens_from_actual_line[actual_line].append(token)

        prev_field_logical_line: int = 1
        for i, token in enumerate(tokens[:-1]):
            if token.token_type == tokenize.NAME:
                # Naive heuristic for field names.
                if (
                    tokens[i + 1].content == ":"
                    and tokens[i] == tokens_from_actual_line[tokens[i].actual_line][0]
                    and token.content not in field_data_from_name
                ):
                    field_data_from_name[token.content] = _FieldData(
                        index=i,
                        logical_line=token.logical_line,
                        actual_line=token.actual_line,
                        prev_field_logical_line=prev_field_logical_line,
                    )
                    prev_field_logical_line = token.logical_line

        return _ClassTokenization(
            tokens=tokens,
            tokens_from_logical_line=tokens_from_logical_line,
            tokens_from_actual_line=tokens_from_actual_line,
            field_data_from_name=field_data_from_name,
        )


def get_class_tokenization_with_field(
    cls: Type, field_name: str
) -> Optional[_ClassTokenization]:
    # Search for token in this class + all parents.
    found_field: bool = False
    classes_to_search = cls.mro()
    for search_cls in classes_to_search:
        # Inherited generics seem challenging for now.
        # https://github.com/python/typing/issues/777
        assert get_origin(search_cls) is None

        # Skip parent classes that aren't dataclasses.
        if not dataclasses.is_dataclass(search_cls):
            continue

        try:
            tokenization = _ClassTokenization.make(search_cls)  # type: ignore
        except OSError as e:
            # Dynamic dataclasses will result in an OSError -- this is fine, we just assume
            # there's no docstring.
            assert "could not find class definition" in e.args[0]
            return None
        except TypeError as e:   # pragma: no cover
            # Notebooks cause “___ is a built-in class” TypeError.
            assert "built-in class" in e.args[0]
            return None


        # Grab field-specific tokenization data.
        if field_name in tokenization.field_data_from_name:
            found_field = True
            break

    assert found_field, (
        "Docstring parsing error -- this usually means that there are multiple"
        " dataclasses in the same file with the same name but different scopes."
    )

    return tokenization


def get_field_docstring(cls: Type, field_name: str) -> Optional[str]:
    """Get docstring for a field in a class."""

    tokenization = get_class_tokenization_with_field(cls, field_name)
    if tokenization is None:  # Currently only happens for dynamic dataclasses.
        return None

    field_data = tokenization.field_data_from_name[field_name]

    # Check for docstring-style comment. This should be on the next logical line.
    logical_line = field_data.logical_line + 1
    if (
        logical_line in tokenization.tokens_from_logical_line
        and len(tokenization.tokens_from_logical_line[logical_line]) >= 1
    ):
        first_token = tokenization.tokens_from_logical_line[logical_line][0]
        first_token_content = first_token.content.strip()

        # Found a docstring!
        if (
            first_token.token_type == tokenize.STRING
            and first_token_content.startswith('"""')
            and first_token_content.endswith('"""')
        ):
            return _strings.dedent(first_token_content[3:-3])

    # Check for comment on the same line as the field.
    final_token_on_line = tokenization.tokens_from_logical_line[
        field_data.logical_line
    ][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.content
        assert comment.startswith("#")
        return comment[1:].strip()

    # Check for comments that come before the field. This is intentionally written to
    # support comments covering multiple (grouped) fields, for example:
    #
    #     # Optimizer hyperparameters.
    #     learning_rate: float
    #     beta1: float
    #     beta2: float
    #
    # In this case, 'Optimizer hyperparameters' will be treated as the docstring for all
    # 3 fields.
    comments: List[str] = []
    current_actual_line = field_data.actual_line - 1
    while current_actual_line in tokenization.tokens_from_actual_line:
        actual_line_tokens = tokenization.tokens_from_actual_line[current_actual_line]
        current_actual_line -= 1

        # We stop looking if we find an empty line.
        if len(actual_line_tokens) == 0:
            break

        # Record single comments!
        if (
            len(actual_line_tokens) == 1
            and actual_line_tokens[0].token_type == tokenize.COMMENT
        ):
            (comment_token,) = actual_line_tokens
            assert comment_token.content.startswith("#")
            comments.append(comment_token.content[1:].strip())
        elif len(comments) > 0:
            # Comments should be contiguous.
            break

    if len(comments) > 0:
        return "\n".join(reversed(comments))

    return None


def get_dataclass_docstring(cls: Type) -> str:
    """Get dataclass docstring, but only if it is hand-specified.

    Note that the `dataclasses.dataclass` will automatically populate __doc__ based on
    the fields of the class if a docstring is not specified; this helper will ignore
    these docstrings."""
    cls, _unused = _resolver.resolve_generic_classes(cls)

    # Docstring should never be `None` with a dataclass.
    assert cls.__doc__ is not None

    # Ignore any default docstrings, as generated by `dataclasses.dataclass`.
    default_doc = cls.__name__ + str(inspect.signature(cls)).replace(" -> None", "")
    if cls.__doc__ == default_doc:
        return ""

    return cls.__doc__
