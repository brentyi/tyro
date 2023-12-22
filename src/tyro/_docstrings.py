"""Helpers for parsing docstrings. Used for helptext generation."""

import collections.abc
import dataclasses
import functools
import inspect
import io
import itertools
import tokenize
from typing import Callable, Dict, Generic, Hashable, List, Optional, Type, TypeVar

import docstring_parser
from typing_extensions import get_origin, is_typeddict

from . import _resolver, _strings, _unsafe_cache

T = TypeVar("T", bound=Callable)


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
    @_unsafe_cache.unsafe_cache(64)
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
                is_first_token = True
                for t in tokens_from_logical_line[token.logical_line]:
                    if t == token:
                        break
                    if t.token_type is not tokenize.COMMENT:
                        is_first_token = False
                        break

                if not is_first_token:
                    continue

                if (
                    tokens[i + 1].content == ":"
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


@_unsafe_cache.unsafe_cache(1024)
def get_class_tokenization_with_field(
    cls: Type, field_name: str
) -> Optional[_ClassTokenization]:
    # Search for token in this class + all parents.
    found_field: bool = False
    classes_to_search = cls.mro()
    tokenization = None
    for search_cls in classes_to_search:
        # Inherited generics seem challenging for now.
        # https://github.com/python/typing/issues/777
        assert search_cls is Generic or get_origin(search_cls) is None

        try:
            tokenization = _ClassTokenization.make(search_cls)  # type: ignore
        except OSError as e:
            assert (
                # Dynamic dataclasses will result in an OSError -- this is fine, we just assume
                # there's no docstring.
                "could not find class definition" in e.args[0]
                # Pydantic.
                or "source code not available" in e.args[0]
            )
            return None
        except TypeError as e:  # pragma: no cover
            # Notebooks cause “___ is a built-in class” TypeError.
            assert "built-in class" in e.args[0]
            return None

        # Grab field-specific tokenization data.
        if field_name in tokenization.field_data_from_name:
            found_field = True
            break

    if dataclasses.is_dataclass(cls):
        assert found_field, (
            "Docstring parsing error -- this usually means that there are multiple"
            " dataclasses in the same file with the same name but different scopes."
        )

    return tokenization


@_unsafe_cache.unsafe_cache(1024)
def get_field_docstring(cls: Type, field_name: str) -> Optional[str]:
    """Get docstring for a field in a class."""

    docstring = inspect.getdoc(cls)
    if docstring is not None:
        for param_doc in docstring_parser.parse(docstring).params:
            if param_doc.arg_name == field_name:
                return (
                    _strings.remove_single_line_breaks(param_doc.description)
                    if param_doc.description is not None
                    else None
                )

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
            return _strings.remove_single_line_breaks(
                _strings.dedent(first_token_content[3:-3])
            )

    # Check for comment on the same line as the field.
    final_token_on_line = tokenization.tokens_from_logical_line[
        field_data.logical_line
    ][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.content
        assert comment.startswith("#")
        return _strings.remove_single_line_breaks(comment[1:].strip())

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

    # Get first line of the class definition, excluding decorators. This logic is only
    # needed for Python >= 3.9; in 3.8, we can simply use
    # `tokenization.tokens[0].logical_line`.
    classdef_logical_line = -1
    for token in tokenization.tokens:
        if token.content == "class":
            classdef_logical_line = token.logical_line
            break
    assert classdef_logical_line != -1

    comments: List[str] = []
    current_actual_line = field_data.actual_line - 1
    while current_actual_line in tokenization.tokens_from_actual_line:
        actual_line_tokens = tokenization.tokens_from_actual_line[current_actual_line]

        # We stop looking if we find an empty line.
        if len(actual_line_tokens) == 0:
            break

        # We don't look in the first logical line. This includes all comments that come
        # before the end parentheses in the class definition (eg comments in the
        # subclass list).
        if actual_line_tokens[0].logical_line <= classdef_logical_line:
            break

        # Record single comments!
        if (
            len(actual_line_tokens) == 1
            and actual_line_tokens[0].token_type is tokenize.COMMENT
        ):
            (comment_token,) = actual_line_tokens
            assert comment_token.content.startswith("#")
            comments.append(comment_token.content[1:].strip())
        elif len(comments) > 0:
            # Comments should be contiguous.
            break

        current_actual_line -= 1

    if len(comments) > 0:
        return _strings.remove_single_line_breaks("\n".join(reversed(comments)))

    return None


_callable_description_blocklist = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(__builtins__.values(), vars(collections.abc).values()),  # type: ignore
    )
)


@_unsafe_cache.unsafe_cache(1024)
def get_callable_description(f: Callable) -> str:
    """Get description associated with a callable via docstring parsing.

    Note that the `dataclasses.dataclass` will automatically populate __doc__ based on
    the fields of the class if a docstring is not specified; this helper will ignore
    these docstrings."""

    f, _unused = _resolver.resolve_generic_types(f)
    f = _resolver.unwrap_origin_strip_extras(f)
    if f in _callable_description_blocklist:
        return ""

    # Return original docstring when used with functools.partial, not
    # functools.partial's docstinrg.
    if isinstance(f, functools.partial):
        f = f.func

    try:
        import pydantic
    except ImportError:
        pydantic = None  # type: ignore

    # Note inspect.getdoc() causes some corner cases with TypedDicts.
    docstring = f.__doc__
    if (
        docstring is None
        and inspect.isclass(f)
        # Ignore TypedDict's __init__ docstring, because it will just be `dict`
        and not is_typeddict(f)
        # Ignore NamedTuple __init__ docstring.
        and not _resolver.is_namedtuple(f)
        # Ignore pydantic base model constructor docstring.
        and not (pydantic is not None and f.__init__ is pydantic.BaseModel.__init__)  # type: ignore
    ):
        docstring = f.__init__.__doc__  # type: ignore
    if docstring is None:
        return ""

    docstring = _strings.dedent(docstring)

    if dataclasses.is_dataclass(f):
        default_doc = f.__name__ + str(inspect.signature(f)).replace(" -> None", "")  # type: ignore
        if docstring == default_doc:
            return ""

    parsed_docstring = docstring_parser.parse(docstring)
    return "\n".join(
        list(
            filter(
                lambda x: x is not None,  # type: ignore
                [
                    parsed_docstring.short_description,
                    parsed_docstring.long_description,
                ],
            )
        )
    )
