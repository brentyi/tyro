from dcargs import _strings


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
