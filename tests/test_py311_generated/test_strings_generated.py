from tyro import _strings


def test_swap_delimiters():
    # Test with default delimiter (hyphen).
    assert _strings.swap_delimiters("my_string_name") == "my-string-name"
    assert _strings.swap_delimiters("___my_string_name__") == "___my-string-name__"
    assert _strings.swap_delimiters("_leading") == "_leading"
    assert _strings.swap_delimiters("trailing_") == "trailing_"
    assert _strings.swap_delimiters("_both_") == "_both_"
    assert _strings.swap_delimiters("___multiple___") == "___multiple___"
    assert (
        _strings.swap_delimiters("no_delimiters_at_edges") == "no-delimiters-at-edges"
    )

    # Test with underscore delimiter.
    with _strings.delimiter_context("_"):
        assert _strings.swap_delimiters("my-string-name") == "my_string_name"
        assert _strings.swap_delimiters("---my-string-name--") == "---my_string_name--"
        assert _strings.swap_delimiters("-leading") == "-leading"
        assert _strings.swap_delimiters("trailing-") == "trailing-"
        assert _strings.swap_delimiters("-both-") == "-both-"
        assert _strings.swap_delimiters("---multiple---") == "---multiple---"
        assert (
            _strings.swap_delimiters("no-delimiters-at-edges")
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


def test_join_union_metavars():
    """Verify that join_union_metavars handles empty inputs and returns empty string."""
    # Empty list should return empty string.
    assert _strings.join_union_metavars([]) == ""

    # Empty generator should also return empty string.
    assert _strings.join_union_metavars(x for x in []) == ""

    # Verify normal union metavar merging behavior.
    assert _strings.join_union_metavars(["NONE", "INT"]) == "NONE|INT"
    assert _strings.join_union_metavars(["{0,1,2}", "{3,4}"]) == "{0,1,2,3,4}"
    assert (
        _strings.join_union_metavars(["{0,1,2}", "{3,4}", "STR"]) == "{0,1,2,3,4}|STR"
    )
    assert _strings.join_union_metavars(["STR", "INT INT"]) == "STR|{INT INT}"
