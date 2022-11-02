"""Pydantic Integration

In addition to standard dataclasses, `tyro` also supports
[Pydantic](https://github.com/pydantic/pydantic) models.

Usage:
`python ./08_pydantic.py --help`
`python ./08_pydantic.py --field1 hello`
`python ./08_pydantic.py --field1 hello --field2 5`
"""
from pydantic import BaseModel, Field

import tyro


class Args(BaseModel):
    """Description.
    This should show up in the helptext!"""

    field1: str
    field2: int = Field(3, description="An integer field.")


if __name__ == "__main__":
    args = tyro.cli(Args)
    print(args)
