import dcargs._strings as _strings


def test_words_from_name():
    assert _strings.hyphen_separated_from_camel_case("MyHTTPServer") == "my-http-server"
    assert (
        _strings.hyphen_separated_from_camel_case("my-http-server") == "my-http-server"
    )
    assert _strings.hyphen_separated_from_camel_case("MyHttpServer") == "my-http-server"
