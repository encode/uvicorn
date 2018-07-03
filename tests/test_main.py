from uvicorn.main import Server, load_app


def test_server():
    server = Server(None)
    server.should_exit = True
    server.run()


def test_load_app():
    assert callable(
        load_app("tests.fixtures.a.b:c")
    ), "should resolve dot notated module paths"

    def fn():
        pass

    assert callable(load_app(fn)), "should load callables directly"
