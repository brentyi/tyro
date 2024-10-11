import pytest

from tyro.extras import SubcommandApp

app = SubcommandApp()
app_just_one = SubcommandApp()


@app_just_one.command
@app.command
def greet(name: str, loud: bool = False) -> None:
    """Greet someone."""
    greeting = f"Hello, {name}!"
    if loud:
        greeting = greeting.upper()
    print(greeting)


@app.command(name="addition")
def add(a: int, b: int) -> None:
    """Add two numbers."""
    print(f"{a} + {b} = {a + b}")


def test_app_just_one_cli(capsys):
    # Test: `python my_script.py --help`
    with pytest.raises(SystemExit):
        app_just_one.cli(args=["--help"])
    captured = capsys.readouterr()
    assert "usage: " in captured.out
    assert "greet" not in captured.out
    assert "addition" not in captured.out
    assert "--name" in captured.out


def test_app_cli(capsys):
    # Test: `python my_script.py --help`
    with pytest.raises(SystemExit):
        app.cli(args=["--help"])
    captured = capsys.readouterr()
    assert "usage: " in captured.out
    assert "greet" in captured.out
    assert "addition" in captured.out

    # Test: `python my_script.py greet --help`
    with pytest.raises(SystemExit):
        app.cli(args=["greet", "--help"], sort_subcommands=False)
    captured = capsys.readouterr()
    assert "usage: " in captured.out
    assert "Greet someone." in captured.out

    # Test: `python my_script.py greet --name Alice`
    app.cli(args=["greet", "--name", "Alice"], sort_subcommands=True)
    captured = capsys.readouterr()
    assert captured.out.strip() == "Hello, Alice!"

    # Test: `python my_script.py greet --name Bob --loud`
    app.cli(args=["greet", "--name", "Bob", "--loud"])
    captured = capsys.readouterr()
    assert captured.out.strip() == "HELLO, BOB!"

    # Test: `python my_script.py addition --help`
    with pytest.raises(SystemExit):
        app.cli(args=["addition", "--help"])
    captured = capsys.readouterr()
    assert "usage: " in captured.out
    assert "Add two numbers." in captured.out

    # Test: `python my_script.py addition 5 3`
    app.cli(args=["addition", "--a", "5", "--b", "3"])
    captured = capsys.readouterr()
    assert captured.out.strip() == "5 + 3 = 8"
