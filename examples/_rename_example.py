import pathlib

import dcargs


def main(source: pathlib.Path, dest: pathlib.Path, /) -> None:
    """Rename an example, while also replacing any occurrences of its old name within
    its contents."""
    assert not dest.exists()
    source.write_text(source.read_text().replace(str(source), str(dest)))
    source.rename(dest)


if __name__ == "__main__":
    dcargs.cli(main)
