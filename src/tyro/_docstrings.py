"""Helpers for parsing docstrings. Used for helptext generation."""

import builtins
import collections.abc
import dataclasses
import functools
import inspect
import itertools
import re
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    List,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from typing_extensions import get_origin, is_typeddict

from tyro._typing_compat import is_typing_generic, is_typing_protocol

from . import _resolver, _strings, _unsafe_cache
from .conf import _markers

T = TypeVar("T", bound=Callable)


class _Token:
    def __init__(self, token_type: int, content: str, logical_line: int) -> None:
        self.token_type = token_type
        self.content = content
        self.logical_line = logical_line


class _ClassTokenization:
    def __init__(
        self,
        actual_line_from_field_name: Dict[str, int],
        field_comments: Dict[str, str],
    ) -> None:
        self.actual_line_from_field_name = actual_line_from_field_name
        self.field_comments = field_comments  # Pre-computed comment for each field.

    @staticmethod
    def make(source: str) -> "_ClassTokenization":
        """Parse the source code of a class, and cache some tokenization information."""
        import io
        import tokenize

        tokens_from_actual_line: Dict[int, List[_Token]] = {1: []}
        actual_line_from_field_name: Dict[str, int] = {}
        classdef_logical_line: int = -1
        has_any_comments = False

        logical_line: int = 1
        actual_line: int = 1

        # Name at the beginning of the current logical line. We use a naive heuristic for
        # finding fields: any name at the beginning of a line that's followed by a colon.
        line_has_token = False
        maybe_field: Optional[Tuple[str, int]] = None

        for toktype, tok, _, _, _ in tokenize.generate_tokens(
            io.StringIO(source).readline
        ):
            # Note: we only track logical line numbers, which are delimited by
            # `tokenize.NEWLINE`. `tokenize.NL` tokens appear when logical lines are
            # broken into multiple lines of code; these are ignored.
            if toktype == tokenize.NEWLINE:
                logical_line += 1
                actual_line += 1
                tokens_from_actual_line[actual_line] = []
                line_has_token = False
            elif toktype == tokenize.NL:
                actual_line += 1
                tokens_from_actual_line[actual_line] = []
            elif toktype not in (tokenize.INDENT, tokenize.DEDENT):
                tokens_from_actual_line[actual_line].append(
                    _Token(toktype, tok, logical_line)
                )

                if maybe_field is not None and tok == ":":
                    actual_line_from_field_name.setdefault(*maybe_field)
                maybe_field = None

                if toktype == tokenize.COMMENT:
                    has_any_comments = True
                elif not line_has_token:
                    line_has_token = True
                    if toktype == tokenize.NAME:
                        maybe_field = (tok, actual_line)

                # Track if we've seen the class definition.
                if (
                    classdef_logical_line == -1
                    and toktype == tokenize.NAME
                    and tok == "class"
                ):
                    classdef_logical_line = logical_line

        # Pre-compute comments for all fields in a single forward pass.
        # This is O(n) instead of O(fields × lines).
        field_comments: Dict[str, str] = {}

        # Early return: if there are no comments in the source, skip all the work below.
        if not has_any_comments:
            return _ClassTokenization(actual_line_from_field_name, field_comments)

        # Build reverse mapping: actual_line -> field_name.
        line_to_field: Dict[int, str] = {
            line: field_name for field_name, line in actual_line_from_field_name.items()
        }

        # Single forward pass through actual lines to associate comments with fields.
        comment_buffer: List[Tuple[str, bool]] = []  # (comment_text, is_sphinx)
        sorted_actual_lines = sorted(tokens_from_actual_line.keys())

        for line_idx, actual_line in enumerate(sorted_actual_lines):
            line_tokens = tokens_from_actual_line[actual_line]

            # Check if this line has a field.
            if actual_line in line_to_field:
                field_name = line_to_field[actual_line]

                # Check for inline comment on the same line as the field.
                if (
                    len(line_tokens) > 0
                    and line_tokens[-1].token_type == tokenize.COMMENT
                ):
                    comment_text = line_tokens[-1].content
                    assert comment_text.startswith("#")
                    if comment_text.startswith("#:"):
                        field_comments[field_name] = _strings.remove_single_line_breaks(
                            comment_text[2:].strip()
                        )
                    else:
                        field_comments[field_name] = _strings.remove_single_line_breaks(
                            comment_text[1:].strip()
                        )
                    # Inline comments always clear the buffer.
                    comment_buffer = []
                # Otherwise, assign buffered comments if any.
                elif len(comment_buffer) > 0:
                    # Sphinx-style comments only apply if directly above.
                    has_sphinx = any(is_sphinx for _, is_sphinx in comment_buffer)
                    field_comments[field_name] = _strings.remove_single_line_breaks(
                        "\n".join(text for text, _ in comment_buffer)
                    )

                    # After assigning comments, decide whether to keep buffer:
                    # - Sphinx comments: always clear (apply to one field only).
                    # - Non-Sphinx comments: keep buffer if next line is also a field
                    #   (for grouped comments like "Description of both y and z").
                    # - Otherwise: clear buffer (prevents comments from applying to non-adjacent fields).
                    next_line_is_field = (
                        line_idx + 1 < len(sorted_actual_lines)
                        and sorted_actual_lines[line_idx + 1] in line_to_field
                    )
                    if has_sphinx or not next_line_is_field:
                        comment_buffer = []

            # Track comments for the buffer.
            elif (
                len(line_tokens) == 1
                and line_tokens[0].token_type == tokenize.COMMENT
                and line_tokens[0].logical_line > classdef_logical_line
            ):
                comment_text = line_tokens[0].content
                assert comment_text.startswith("#")
                is_sphinx = comment_text.startswith("#:")
                if is_sphinx:
                    comment_buffer.append((comment_text[2:].strip(), True))
                else:
                    comment_buffer.append((comment_text[1:].strip(), False))

            # Empty line or non-comment, non-field line: clear buffer.
            # This prevents comments above methods, assignments, or other
            # non-field code from leaking to subsequent fields.
            else:
                comment_buffer = []

        return _ClassTokenization(actual_line_from_field_name, field_comments)


_source_cache: Dict[type, Union[str, OSError, TypeError]] = _unsafe_cache.make_cache()


def _get_source(cls: type) -> Union[str, OSError, TypeError]:
    """Same as `inspect.getsource()`, but caches and returns errors."""
    out = _source_cache.get(cls)
    if out is None:
        try:
            out = inspect.getsource(cls)
        except (OSError, TypeError) as e:
            out = e
        _source_cache[cls] = out
    return out


_tokenization_cache: Dict[type, _ClassTokenization] = _unsafe_cache.make_cache()


def _get_field_comment(cls: Type, field_name: str) -> Optional[str]:
    """Get the comment associated with a field, from this class or any of its parents."""
    # We can skip tokenization if we don't see any comments.
    if not any(
        isinstance(source, str) and "#" in source
        for source in map(_get_source, cls.__mro__)
    ):
        return None

    for search_cls in cls.__mro__:
        # Inherited generics seem challenging for now.
        # https://github.com/python/typing/issues/777
        assert is_typing_generic(search_cls) or get_origin(search_cls) is None

        tokenization = _tokenization_cache.get(search_cls)
        if tokenization is None:
            source = _get_source(search_cls)
            if isinstance(source, OSError):
                # OSError is raised when we can't read the source code. This is
                # fine, we just assume there's no docstring. For example:
                # - Dynamic dataclasses: "could not find class definition".
                # - Pydantic: "source code not available".
                # - inspect.py: "could not get source code".
                return None
            elif isinstance(source, TypeError):  # pragma: no cover
                # Notebooks cause "___ is a built-in class" TypeError.
                assert "built-in class" in source.args[0]
                return None
            tokenization = _ClassTokenization.make(source)
            _tokenization_cache[search_cls] = tokenization

        # Grab field-specific tokenization data.
        if field_name in tokenization.actual_line_from_field_name:
            return tokenization.field_comments.get(field_name, None)

    assert not dataclasses.is_dataclass(cls), (
        "Docstring parsing error -- this usually means that there are multiple"
        " dataclasses in the same file with the same name but different scopes."
    )
    return None


@functools.lru_cache(maxsize=1024)
def _parse_docstring(
    docstring: str,
) -> Tuple[Optional[str], Dict[str, Optional[str]]]:
    """Parse a docstring. Returns a description and a dictionary mapping parameter names
    to their descriptions."""
    # Fast path: avoid importing docstring_parser if none of the styles that it supports
    # have any sections that could start in this docstring:
    #
    # - ReST: lines starting with `:`.
    # - Google: lines ending with `:`.
    # - NumPy: lines that are only dashes, or lines that start with `..`.
    # - Epydoc: lines starting with `@`.
    text = inspect.cleandoc(docstring)
    if not re.search(r"^\s*[:@]|^\s*\.\.|:\s*$|^\s*-+\s*$", text, flags=re.MULTILINE):
        short, line_break, long = text.partition("\n")
        parts = []
        if len(short) > 0:
            parts.append(short)
            if long.startswith("\n"):
                parts.append("")
        if len(long.strip()) > 0:
            parts.append(long.strip())
        return ("\n".join(parts) if len(parts) > 0 else None), {}

    import docstring_parser

    parsed = docstring_parser.parse(docstring)
    return (
        parsed.description,
        {doc.arg_name: doc.description for doc in parsed.params},
    )


def parse_params_from_docstring(docstring: Optional[str]) -> Dict[str, Optional[str]]:
    """Get the description of each parameter in a docstring."""
    if docstring is None:
        return {}
    return _parse_docstring(docstring)[1]


def _get_attribute_docstrings(source: str) -> Dict[str, str]:
    """Get the docstring that follows each attribute in a class definition. This should
    match the behavior of `docstring_parser.parse_from_object()`."""
    import ast
    import textwrap

    out: Dict[str, str] = {}
    prev_attr: Optional[str] = None

    def visit(node: ast.AST) -> None:
        nonlocal prev_attr
        if (
            prev_attr is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out[prev_attr] = node.value.value

        prev_attr = None
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name):
                prev_attr = target.id
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                visit(child)

    tree = ast.parse(textwrap.dedent(source))
    if isinstance(tree.body[0], ast.ClassDef):
        visit(tree.body[0])
    return out


_docstring_from_class: Optional[MutableMapping[type, Dict[str, str]]] = None


def parse_docstring_from_object(cls: type) -> Dict[str, str]:
    """Get field descriptions from the docstring of a class and its attributes."""
    # Cached across calls, but without keeping classes alive. `weakref` is only imported
    # when we need helptext.
    global _docstring_from_class
    if _docstring_from_class is None:
        import weakref

        _docstring_from_class = weakref.WeakKeyDictionary()
    out = _docstring_from_class.get(cls)
    if out is None:
        out = _parse_docstring_from_object(cls)
        _docstring_from_class[cls] = out
    return out


def _parse_docstring_from_object(cls: type) -> Dict[str, str]:
    docstring = cls.__doc__
    params = {} if not docstring else _parse_docstring(docstring)[1]
    out: Dict[str, str] = {k: v for k, v in params.items() if v is not None}

    source = _get_source(cls)
    if isinstance(source, TypeError):
        raise source
    elif isinstance(source, str):
        for name, description in _get_attribute_docstrings(source).items():
            if name not in params:
                out[name] = description
    return out


_NOT_CACHED: Any = object()
_field_docstring_cache: Dict[Any, Optional[str]] = _unsafe_cache.make_cache()


def get_field_docstring(
    cls: Type, field_name: str, markers: Tuple[_markers.Marker, ...]
) -> Optional[str]:
    """Get docstring for a field in a class."""

    # NoneType will break docstring_parser.
    if cls is type(None):
        return None

    # Internal types don't have any docstrings.
    if cls.__module__ == "tyro._dummy_wrapper":
        return None

    include_comments = _markers.HelptextFromCommentsOff not in markers
    key = (cls, field_name, include_comments)
    out = _field_docstring_cache.get(key, _NOT_CACHED)
    if out is _NOT_CACHED:
        out = _get_field_docstring(cls, field_name, include_comments)
        _field_docstring_cache[key] = out
    return out


def _get_field_docstring(
    cls: Type, field_name: str, include_comments: bool
) -> Optional[str]:
    # Try to parse using docstring_parser.
    for cls_search in cls.__mro__:
        if cls_search.__module__ == "builtins":
            continue  # Skip `object`, `Callable`, `tuple`, etc.
        if is_typing_generic(cls_search) or is_typing_protocol(cls_search):
            continue
        docstring = parse_docstring_from_object(cls_search).get(field_name, None)
        if docstring is not None:
            return _strings.dedent(
                _strings.remove_single_line_breaks(docstring)
            ).strip()

    # If docstring_parser failed, let's try looking for comments.
    # Comments are pre-computed during tokenization for efficiency.
    if not include_comments:
        return None
    return _get_field_comment(cls, field_name)


_callable_description_blocklist: Set[Hashable] = set(
    filter(
        lambda x: isinstance(x, Hashable),  # type: ignore
        itertools.chain(
            vars(builtins).values(),
            vars(collections.abc).values(),
        ),
    )
)


_callable_description_cache: Dict[Any, str] = _unsafe_cache.make_cache()


def get_callable_description(f: Callable) -> str:
    """Get description associated with a callable via docstring parsing.

    `dataclasses.dataclass` will automatically populate __doc__ based on the
    fields of the class if a docstring is not specified; this helper will
    ignore these docstrings."""
    key = _unsafe_cache.type_key(f)
    out = _callable_description_cache.get(key)
    if out is None:
        out = _get_callable_description(f)
        _callable_description_cache[key] = out
    return out


def _get_callable_description(f: Callable) -> str:
    f, _ = _resolver.resolve_generic_types(f)
    f = _resolver.unwrap_origin_strip_extras(f)
    if f in _callable_description_blocklist:
        return ""

    # Return original docstring when used with functools.partial, not
    # functools.partial's docstring.
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

    if dataclasses.is_dataclass(f) and docstring.startswith(f.__name__ + "("):  # type: ignore
        default_doc = f.__name__ + str(inspect.signature(f)).replace(" -> None", "")  # type: ignore
        if docstring == default_doc:
            return ""

    description = _parse_docstring(docstring)[0]
    if description is None:
        return ""
    return description
