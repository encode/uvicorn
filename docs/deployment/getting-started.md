# Deployment

Server deployment is a complex area, that will depend on what kind of service you're deploying Uvicorn onto.

### TL;DR
As a general rule, you probably want to:

* Run `uvicorn --reload` from the command line for local development.
* Run `gunicorn -k uvicorn.workers.UvicornWorker` for production (non containerized).
* Run behind Nginx for self-hosted deployments.
* Finally, run everything behind a CDN for caching support, and serious DDOS protection.

## Quick Start

This section is meant to get you started serving an ASGI application as quick as possible.

[ASGI Specification]: https://asgi.readthedocs.io/en/latest/
[awesome-asgi]: https://github.com/florimondmanca/awesome-asgi


### Running from the command line

The simplest way to run `uvicorn` is from the command line.

```bash
$ uvicorn example:app --reload --port 5000
```

The ASGI application should be specified in the form `path.to.module:instance.path`

Use `--reload` to turn on auto-reloading. 
!!! note
    `--reload` is recommended only for local use, during the development phase.
    
    The `--reload` and `--workers` arguments are **mutually exclusive**.

To see the complete set of available options, use [`uvicorn --help`](../index.md#command-line-options). 


See the [settings documentation](../settings.md) for more details on the supported options for running uvicorn.

### Running programmatically

Uvicorn can also be run programmatically. To run directly from within a Python program, you should use `uvicorn.run(app, **config)`. 

**`example.py`**

```python
import uvicorn

class App:
    ...

app = App()

if __name__ == "__main__":
    uvicorn.run("example:app", host="127.0.0.1", port=5000, log_level="info")
```

The set of configuration options available is the same as for the options listed under running from commandline.

!!! note
    Note that the application instance itself *can* be passed instead of the app
    import string.

    ```python
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="info")
    ```

    However, this style only works if you are not using multiprocessing (`workers=NUM`)
    or reloading (`reload=True`), so we recommend using the import string style.

    Also note that in this case, you should put `uvicorn.run` into `if __name__ == '__main__'` clause in the main module.

    Remember, the `reload` and `workers` parameters are **mutually exclusive**.

