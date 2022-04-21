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
    line_number: int


@dataclasses.dataclass(frozen=True)
class _FieldData:
    index: int
    line_number: int
    prev_field_line_number: int


@dataclasses.dataclass(frozen=True)
class _ClassTokenization:
    tokens: List[_Token]
    tokens_from_line: Dict[int, List[_Token]]
    field_data_from_name: Dict[str, _FieldData]

    @staticmethod
    @functools.lru_cache(maxsize=8)
    def make(cls) -> "_ClassTokenization":
        """Parse the source code of a class, and cache some tokenization information."""
        readline = io.BytesIO(inspect.getsource(cls).encode("utf-8")).readline

        tokens: List[_Token] = []
        tokens_from_line: Dict[int, List[_Token]] = {1: []}
        field_data_from_name: Dict[str, _FieldData] = {}

        line_number: int = 1
        for toktype, tok, start, end, line in tokenize.tokenize(readline):
            if toktype in (tokenize.NEWLINE, tokenize.NL):
                line_number += 1
                tokens_from_line[line_number] = []
            elif toktype is not tokenize.INDENT:
                token = _Token(token_type=toktype, content=tok, line_number=line_number)
                tokens.append(token)
                tokens_from_line[line_number].append(token)

        prev_field_line_number: int = 1
        for i, token in enumerate(tokens[:-1]):
            if token.token_type == tokenize.NAME:
                # Naive heuristic for field names
                if (
                    tokens[i + 1].content == ":"
                    and tokens[i] == tokens_from_line[tokens[i].line_number][0]
                    and token.content not in field_data_from_name
                ):
                    field_data_from_name[token.content] = _FieldData(
                        index=i,
                        line_number=token.line_number,
                        prev_field_line_number=prev_field_line_number,
                    )
                    prev_field_line_number = token.line_number

        return _ClassTokenization(
            tokens=tokens,
            tokens_from_line=tokens_from_line,
            field_data_from_name=field_data_from_name,
        )


def get_class_tokenization_with_field(
    cls: Type, field_name: str
) -> Optional[_ClassTokenization]:
    # Search for token in this class + all parents.
    found_field: bool = False
    classes_to_search = cls.mro()
    for search_cls in classes_to_search:
        # Unwrap generics.
        origin_cls = get_origin(search_cls)
        if origin_cls is not None:
            search_cls = origin_cls

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

    # Check for docstring-style comment.
    line_number = field_data.line_number + 1
    while (
        line_number in tokenization.tokens_from_line
        and len(tokenization.tokens_from_line[line_number]) > 0
    ):
        first_token = tokenization.tokens_from_line[line_number][0]
        first_token_content = first_token.content.strip()

        # Found a docstring!
        if (
            first_token.token_type == tokenize.STRING
            and first_token_content.startswith('"""')
            and first_token_content.endswith('"""')
        ):
            return _strings.dedent(first_token_content[3:-3])

        # Found the next field.
        if (
            first_token.token_type == tokenize.NAME
            and len(tokenization.tokens_from_line[line_number]) >= 2
            and tokenization.tokens_from_line[line_number][1].content == ":"
        ):
            break

        # Found a method.
        if first_token.content == "def":
            break

        line_number += 1

    # Check for comment on the same line as the field.
    final_token_on_line = tokenization.tokens_from_line[field_data.line_number][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.content
        assert comment.startswith("#")
        return comment[1:].strip()

    # Check for comment on the line before the field.
    comment_index = field_data.index
    comments: List[str] = []
    current_line_number = field_data.line_number
    while True:
        comment_index -= 1
        comment_token = tokenization.tokens[comment_index]
        if (
            # Looking for comments!
            comment_token.token_type == tokenize.COMMENT
            # Comments should come after the previous field.
            and comment_token.line_number > field_data.prev_field_line_number
            # And be contiguous.
            and comment_token.line_number == current_line_number - 1
        ):
            assert comment_token.content.startswith("#")
            current_line_number -= 1
            comments.append(comment_token.content[1:].strip())
        else:
            break
    if len(comments) > 0:
        return "\n".join(comments[::-1])

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
