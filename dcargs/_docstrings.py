import dataclasses
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
class _Tokenization:
    tokens: List[_Token]
    tokens_from_line: Dict[int, List[_Token]]

    @staticmethod
    def make(cls) -> "_Tokenization":
        readline = io.BytesIO(inspect.getsource(cls).encode("utf-8")).readline
        tokens: List[_Token] = []
        tokens_from_line: Dict[int, List[_Token]] = {1: []}
        line_number: int = 1
        for toktype, tok, start, end, line in tokenize.tokenize(readline):
            if toktype in (tokenize.NEWLINE, tokenize.NL):
                line_number += 1
                tokens_from_line[line_number] = []
            elif toktype is not tokenize.INDENT:
                token = _Token(token_type=toktype, token=tok, line_number=line_number)
                tokens.append(token)
                tokens_from_line[line_number].append(token)
        return _Tokenization(tokens=tokens, tokens_from_line=tokens_from_line)


_cached_tokenization: Dict[Type, _Tokenization] = {}


def get_field_docstring(cls: Type, field_name: str) -> Optional[str]:
    """Get docstring for a field in a class."""

    if isinstance(cls, _GenericAlias):
        cls = cls.__origin__

    assert dataclasses.is_dataclass(cls)
    if cls not in _cached_tokenization:
        try:
            _cached_tokenization[cls] = _Tokenization.make(cls)
        except OSError as e:
            # Dynamic dataclasses
            assert "could not find class definition" in e.args[0]
            return None

    tokens = _cached_tokenization[cls].tokens
    tokens_from_line = _cached_tokenization[cls].tokens_from_line

    # Scan for our token
    prev_line_with_name: Optional[int] = None
    field_line: Optional[int] = None
    field_index: Optional[int] = None
    for i, token in enumerate(tokens):
        if token.token_type == tokenize.NAME:
            if token.token == field_name and tokens[i + 1].token == ":":
                field_line = tokens[i].line_number
                field_index = i
                break
            else:
                prev_line_with_name = tokens[i].line_number
    assert (
        field_line is not None
        and field_index is not None
        and prev_line_with_name is not None
    ), "Docstring parsing error -- this usually means that there are multiple \
    dataclasses in the same file with the same name but different scopes."

    # Check for docstring-style comment
    if field_line + 1 in tokens_from_line and len(tokens_from_line[field_line + 1]) > 0:
        first_token_on_next_line = tokens_from_line[field_line + 1][0]
        if first_token_on_next_line.token_type == tokenize.STRING:
            docstring = first_token_on_next_line.token.strip()
            assert docstring.endswith('"""') and docstring.startswith('"""')
            return _strings.dedent(docstring[3:-3])

    # Check for comment on the same line as the field
    final_token_on_line = tokens_from_line[field_line][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.token
        assert comment.startswith("#")
        return comment[1:].strip()

    # Check for comment on the line before the field
    comment_index = field_index
    comments: List[str] = []
    while True:
        comment_index -= 1
        comment_token = tokens[comment_index]
        if (
            comment_token.token_type == tokenize.COMMENT
            and comment_token.line_number > prev_line_with_name
        ):
            assert comment_token.token.startswith("#")
            comments.append(comment_token.token[1:].strip())
        else:
            break
    if len(comments) > 0:
        return "\n".join(comments[::-1])

    return None
