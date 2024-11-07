"""Helpers for parsing docstrings. Used for helptext generation."""

import builtins
import collections.abc
import dataclasses
import functools
import inspect
import io
import itertools
import sys
import tokenize
from typing import Callable, Dict, Generic, Hashable, List, Optional, Set, Type, TypeVar

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
    classes_to_search = cls.__mro__
    tokenization = None
    for search_cls in classes_to_search:
        # Inherited generics seem challenging for now.
        # https://github.com/python/typing/issues/777
        assert search_cls is Generic or get_origin(search_cls) is None

        try:
            tokenization = _ClassTokenization.make(search_cls)  # type: ignore
        except OSError:
            # OSError is raised when we can't read the source code. This is
            # fine, we just assume there's no docstring. We can uncomment the
            # assert below for debugging.
            #
            # assert (
            #     # Dynamic dataclasses.
            #     "could not find class definition" in e.args[0]
            #     # Pydantic.
            #     or "source code not available" in e.args[0]
            #     # Third error that can be raised by inspect.py.
            #     or "could not get source code" in e.args[0]
            # )
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


@functools.lru_cache(maxsize=1024)
def parse_docstring_from_object(obj: object) -> Dict[str, str]:
    return {
        doc.arg_name: doc.description
        for doc in docstring_parser.parse_from_object(obj).params
        if doc.description is not None
    }


@_unsafe_cache.unsafe_cache(1024)
def get_field_docstring(cls: Type, field_name: str) -> Optional[str]:
    """Get docstring for a field in a class."""

    # NoneType will break docstring_parser.
    if cls is type(None):
        return None

    # Try to parse using docstring_parser.
    for cls_search in cls.__mro__:
        if cls_search.__module__ == "builtins":
            continue  # Skip `object`, `Callable`, `tuple`, etc.
        docstring = parse_docstring_from_object(cls_search).get(field_name, None)
        if docstring is not None:
            return _strings.dedent(
                _strings.remove_single_line_breaks(docstring)
            ).strip()

    # If docstring_parser failed, let's try looking for comments.
    tokenization = get_class_tokenization_with_field(cls, field_name)
    if tokenization is None:  # Currently only happens for dynamic dataclasses.
        return None

    field_data = tokenization.field_data_from_name[field_name]

    # Check for comment on the same line as the field.
    final_token_on_line = tokenization.tokens_from_logical_line[
        field_data.logical_line
    ][-1]
    if final_token_on_line.token_type == tokenize.COMMENT:
        comment: str = final_token_on_line.content
        assert comment.startswith("#")
        if comment.startswith("#:"):  # Sphinx autodoc-style comment.
            # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-autoattribute
            return _strings.remove_single_line_breaks(comment[2:].strip())
        else:
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
    # 3 fields. There are tradeoffs we are making here.
    #
    # The exception this is Sphinx-style comments:
    #
    #     #: The learning rate.
    #     learning_rate: float
    #     beta1: float
    #     beta2: float
    #
    # Where, by convention the comment only applies to the field that directly follows it.

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
    directly_above_field = True
    is_sphinx_doc_comment = False
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
            if comment_token.content.startswith("#:"):  # Sphinx autodoc-style comment.
                # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-autoattribute
                comments.append(comment_token.content[2:].strip())
                is_sphinx_doc_comment = True
            else:
                comments.append(comment_token.content[1:].strip())
        elif len(comments) > 0:
            # Comments should be contiguous.
            break
        else:
            # This comment is not directly above the current field.
            directly_above_field = False

        current_actual_line -= 1

    if len(comments) > 0 and not (is_sphinx_doc_comment and not directly_above_field):
        return _strings.remove_single_line_breaks("\n".join(reversed(comments)))

    return None


_callable_description_blocklist: Set[Hashable] = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(
            vars(builtins).values(),
            vars(collections.abc).values(),
        ),
    )
)


@_unsafe_cache.unsafe_cache(1024)
def get_callable_description(f: Callable) -> str:
    """Get description associated with a callable via docstring parsing.

    `dataclasses.dataclass` will automatically populate __doc__ based on the
    fields of the class if a docstring is not specified; this helper will
    ignore these docstrings."""

    f, _ = _resolver.resolve_generic_types(f)
    f = _resolver.unwrap_origin_strip_extras(f)
    if f in _callable_description_blocklist:
        return ""

    # Return original docstring when used with functools.partial, not
    # functools.partial's docstinrg.
    if isinstance(f, functools.partial):
        f = f.func

    if "pydantic" in sys.modules.keys():
        try:
            import pydantic
        except ImportError:
            # Needed for mock import test.
            pydantic = None  # type: ignore
    else:
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

    parts: List[str] = []
    if parsed_docstring.short_description is not None:
        parts.append(parsed_docstring.short_description)
    if parsed_docstring.long_description is not None:
        parts.append(parsed_docstring.long_description)
    return "\n".join(parts)
