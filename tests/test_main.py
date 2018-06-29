from uvicorn.main import Server


def test_server():
    server = Server(None)
    server.should_exit = True
    server.run()
