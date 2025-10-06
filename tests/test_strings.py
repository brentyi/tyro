from tyro import _strings


def test_words_from_name():
    assert _strings.hyphen_separated_from_camel_case("MyHTTPServer") == "my-http-server"
    assert (
        _strings.hyphen_separated_from_camel_case("my-http-server") == "my-http-server"
    )


def test_make_field_name():
    # Test make_extern_prefix (user-facing names with delimiter swapping)
    assert _strings.make_extern_prefix(["hello", "world"]) == "hello.world"
    assert _strings.make_extern_prefix(["hello_world", "world"]) == "hello-world.world"
    assert (
        _strings.make_extern_prefix(["hello_world", "___hello_world"])
        == "hello-world.___hello-world"
    )
    assert (
        _strings.make_extern_prefix(["hello_world", "---hello_world"])
        == "hello-world.---hello-world"
    )

    # Test make_intern_prefix (internal names without delimiter swapping)
    assert _strings.make_intern_prefix(["hello", "world"]) == "hello.world"
    assert _strings.make_intern_prefix(["hello_world", "world"]) == "hello_world.world"
    assert (
        _strings.make_intern_prefix(["hello_world", "___hello_world"])
        == "hello_world.___hello_world"
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
