import dataclasses
import functools
import inspect
import io
import tokenize
from typing import Dict, List, Optional, Type

from typing_extensions import _GenericAlias  # type: ignore

from . import _strings


@dataclasses.dataclass
class _Token:
    token_type: int
    token: str
    line_number: int


@dataclasses.dataclass
class _FieldData:
    index: int
    line_number: int
    prev_field_line_number: int


@dataclasses.dataclass
class _Tokenization:
    tokens: List[_Token]
    tokens_from_line: Dict[int, List[_Token]]
    field_data_from_name: Dict[str, _FieldData]

    @staticmethod
    @functools.lru_cache(maxsize=4)
    def make(cls) -> "_Tokenization":
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
                token = _Token(token_type=toktype, token=tok, line_number=line_number)
                tokens.append(token)
                tokens_from_line[line_number].append(token)

        prev_field_line_number: int = 1
        for i, token in enumerate(tokens[:-1]):
            if token.token_type == tokenize.NAME:
                # Naive heuristic for field names
                # This will currently catch variable/argument annotations as well
                if (
                    tokens[i + 1].token == ":"
                    and token.token not in field_data_from_name
                ):
                    field_data_from_name[token.token] = _FieldData(
                        index=i,
                        line_number=token.line_number,
                        prev_field_line_number=prev_field_line_number,
                    )
                    prev_field_line_number = token.line_number

        return _Tokenization(
            tokens=tokens,
            tokens_from_line=tokens_from_line,
            field_data_from_name=field_data_from_name,
        )


def get_field_docstring(cls: Type, field_name: str) -> Optional[str]:
    """Get docstring for a field in a class."""

    if isinstance(cls, _GenericAlias):
        cls = cls.__origin__

    assert dataclasses.is_dataclass(cls)
    try:
        tokenization = _Tokenization.make(cls)  # type: ignore
    except OSError as e:
        # Dynamic dataclasses will result in an OSError -- this is fine, we just assume
        # there's no docstring.
        assert "could not find class definition" in e.args[0]
        return None

    # Grab field-specific tokenization data.
    assert (
        field_name in tokenization.field_data_from_name
    ), "Docstring parsing error -- this usually means that there are multiple \
    dataclasses in the same file with the same name but different scopes."
    field_data = tokenization.field_data_from_name[field_name]

    # Check for docstring-style comment.
    if (
        field_data.line_number + 1 in tokenization.tokens_from_line
        and len(tokenization.tokens_from_line[field_data.line_number + 1]) > 0
    ):
        first_token_on_next_line = tokenization.tokens_from_line[
            field_data.line_number + 1
        ][0]
        if first_token_on_next_line.token_type == tokenize.STRING:
            docstring = first_token_on_next_line.token.strip()
            assert docstring.endswith('"""') and docstring.startswith('"""')
            return _strings.dedent(docstring[3:-3])

    # Check for comment on the same line as the field.
    final_token_on_line = tokenization.tokens_from_line[field_data.line_number][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.token
        assert comment.startswith("#")
        return comment[1:].strip()

    # Check for comment on the line before the field.
    comment_index = field_data.index
    comments: List[str] = []
    while True:
        comment_index -= 1
        comment_token = tokenization.tokens[comment_index]
        if (
            comment_token.token_type == tokenize.COMMENT
            and comment_token.line_number > field_data.prev_field_line_number
        ):
            assert comment_token.token.startswith("#")
            comments.append(comment_token.token[1:].strip())
        else:
            break
    if len(comments) > 0:
        return "\n".join(comments[::-1])

    return None
