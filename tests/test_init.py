"""Tests for tyro/__init__.py — lazy loading, deprecated aliases, and exports."""

import pytest

import tyro


def test_version():
    """Check that __version__ is a string."""
    assert isinstance(tyro.__version__, str)


def test_cli_export():
    """tyro.cli should be the real cli function."""
    from tyro._cli import cli

    assert tyro.cli is cli


def test_conf_export():
    """tyro.conf should be the conf module."""
    from tyro import conf

    assert tyro.conf is conf


def test_constructors_export():
    """tyro.constructors should be the constructors module."""
    from tyro import constructors

    assert tyro.constructors is constructors


def test_missing_export():
    """tyro.MISSING should be accessible."""
    from tyro._singleton import MISSING

    assert tyro.MISSING is MISSING


def test_missing_nonprop_export():
    """tyro.MISSING_NONPROP should be accessible."""
    from tyro._singleton import MISSING_NONPROP

    assert tyro.MISSING_NONPROP is MISSING_NONPROP


def test_unsupported_type_annotation_error_export():
    """Deprecated UnsupportedTypeAnnotationError should be importable from tyro."""
    from tyro.constructors._primitive_spec import UnsupportedTypeAnnotationError

    assert tyro.UnsupportedTypeAnnotationError is UnsupportedTypeAnnotationError


def test_extras_lazy_import():
    """tyro.extras should be lazily importable via __getattr__."""
    import importlib

    extras = importlib.import_module("tyro.extras")
    # Access via attribute triggers __getattr__ or cached global
    assert tyro.extras is extras


def test_deprecated_parse_alias():
    """tyro.parse should be a deprecated alias for tyro.cli."""
    from tyro._cli import cli

    assert tyro.parse is cli


def test_deprecated_from_yaml_alias():
    """tyro.from_yaml should be a deprecated lazy alias."""
    from tyro.extras._serialization import from_yaml

    assert tyro.from_yaml is from_yaml


def test_deprecated_to_yaml_alias():
    """tyro.to_yaml should be a deprecated lazy alias."""
    from tyro.extras._serialization import to_yaml

    assert tyro.to_yaml is to_yaml


def test_getattr_unknown_attribute():
    """Accessing a nonexistent attribute on tyro should raise AttributeError."""
    with pytest.raises(AttributeError, match="module 'tyro' has no attribute"):
        tyro.this_attribute_does_not_exist  # noqa: B018


def test_deprecated_aliases_are_cached():
    """After first access, deprecated aliases should be cached in globals."""
    # First access triggers __getattr__ and caches
    _ = tyro.parse
    # Second access should hit the cached global, not __getattr__ again
    assert tyro.parse is tyro.parse


def test_extras_is_cached():
    """After first access, extras should be cached in globals."""
    _ = tyro.extras
    assert tyro.extras is tyro.extras
