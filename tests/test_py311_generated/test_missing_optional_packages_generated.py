import builtins

import pytest


# https://stackoverflow.com/questions/60227582/making-a-python-test-think-an-installed-package-is-not-available
@pytest.fixture
def hide_optional_packages(monkeypatch):
    import_orig = builtins.__import__

    def mocked_import(name, *args, **kwargs):
        if name in ("attr", "pydantic", "flax", "omegaconf"):
            raise ImportError()
        return import_orig(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mocked_import)


def test_missing_optional_packages(hide_optional_packages):
    def main(x: int) -> int:
        return x

    import tyro

    assert tyro.cli(main, args=["--x", "5"]) == 5
