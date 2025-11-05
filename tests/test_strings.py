from tyro import _strings


def test_swap_delimeters():
    # Test with default delimiter (hyphen).
    assert _strings.swap_delimeters("my_string_name") == "my-string-name"
    assert _strings.swap_delimeters("___my_string_name__") == "___my-string-name__"
    assert _strings.swap_delimeters("_leading") == "_leading"
    assert _strings.swap_delimeters("trailing_") == "trailing_"
    assert _strings.swap_delimeters("_both_") == "_both_"
    assert _strings.swap_delimeters("___multiple___") == "___multiple___"
    assert (
        _strings.swap_delimeters("no_delimiters_at_edges") == "no-delimiters-at-edges"
    )

    # Test with underscore delimiter.
    with _strings.delimeter_context("_"):
        assert _strings.swap_delimeters("my-string-name") == "my_string_name"
        assert _strings.swap_delimeters("---my-string-name--") == "---my_string_name--"
        assert _strings.swap_delimeters("-leading") == "-leading"
        assert _strings.swap_delimeters("trailing-") == "trailing-"
        assert _strings.swap_delimeters("-both-") == "-both-"
        assert _strings.swap_delimeters("---multiple---") == "---multiple---"
        assert (
            _strings.swap_delimeters("no-delimiters-at-edges")
            == "no_delimiters_at_edges"
        )


def test_words_from_name():
    assert _strings.hyphen_separated_from_camel_case("MyHTTPServer") == "my-http-server"
    assert (
        _strings.hyphen_separated_from_camel_case("my-http-server") == "my-http-server"
    )


def test_make_field_name():
    assert _strings.make_field_name(["hello", "world"]) == "hello.world"
    assert _strings.make_field_name(["hello_world", "world"]) == "hello-world.world"
    assert (
        _strings.make_field_name(["hello_world", "___hello_world"])
        == "hello-world.___hello-world"
    )
    assert (
        _strings.make_field_name(["hello_world", "---hello_world"])
        == "hello-world.---hello-world"
    )


def test_postprocess_helptext():
    assert _strings.remove_single_line_breaks("hello world") == "hello world"
    assert _strings.remove_single_line_breaks("hello\nworld") == "hello world"
    assert _strings.remove_single_line_breaks("hello   \nworld") == "hello world"
    assert _strings.remove_single_line_breaks("hello\n\nworld") == "hello\n\nworld"
    assert (
        _strings.remove_single_line_breaks(
            "a paragraph:\nSentence one.\nSentence two.\nSentence three.\n"
        )
        == "a paragraph: Sentence one. Sentence two. Sentence three."
    )
    assert (
        _strings.remove_single_line_breaks(
            "a bulleted list:\n"
            "- The first problem.\n"
            "- The second problem.\n"
            "- The third problem.\n"
        )
        == "a bulleted list:\n"
        "- The first problem.\n"
        "- The second problem.\n"
        "- The third problem."
    )
    assert (
        _strings.remove_single_line_breaks(
            "an indented list:\n"
            " The first problem.\n"
            " The second problem.\n"
            " The third problem.\n"
        )
        == "an indented list:\n"
        " The first problem.\n"
        " The second problem.\n"
        " The third problem."
    )
    assert (
        _strings.remove_single_line_breaks(
            "a numbered list:\n"
            "1. The first problem.\n"
            "2. The second problem.\n"
            "3. The third problem.\n"
        )
        == "a numbered list:\n"
        "1. The first problem.\n"
        "2. The second problem.\n"
        "3. The third problem."
    )
