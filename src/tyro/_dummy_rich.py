# This file is to simulate the rich library API to offer a non-rich support for minimal installations.
import re


class Dummy:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def __call__(self, *args, **kwargs):
        return args[0] if args else self

    def __getattr__(self, name):
        def method(*args, **kwargs):
            return args[0] if args else self

        return method

    def __str__(self):
        return "\n".join(str(o) for o in self._args)

    def __len__(self):
        return 0


Columns = Dummy

RenderableType = Dummy
Padding = Dummy
Group = Dummy
Rule = Dummy
Style = Dummy
Table = Dummy
Theme = Dummy

_MARKUP_PATTERN = re.compile(r"\[/?[^\[\]]+\]")


def remove_markup(txt):
    return _MARKUP_PATTERN.sub("", txt)

class Console(Dummy):
    def print(self, renderable):
        print(remove_markup(str(renderable)))

class Panel(Dummy):
    def __str__(self):
        if title := self._kwargs.get("title", ""):
            title = "─" * 10 + " " + title + " " + "─" * 10 + " \n"
        return title + super().__str__()


class Text(Dummy):

    def __init__(self, content: str):
        self._text = [content]

    def __str__(self):
        return "\n".join(self._text)

    @staticmethod
    def from_ansi(txt, *args, **kwargs):
        return Text(txt)

    @staticmethod
    def from_markup(txt, *args, **kwargs):
        return Text(remove_markup(txt))
