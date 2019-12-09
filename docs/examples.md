# Examples

## Custom logging

The below `logging_example.yaml` is a yaml representation of the default logging configuration.
You can pass it loading a dict, using the `--log-config` flag.
It sets 2 loggers:
1. `uvicorn.error` whose formatter is the `uvicorn.logging.DefaultFormatter`. 
2. `uvicorn.access` whose formatter is the `uvicorn.logging.AccessFormatter`. 

Both formatters will output a colorized automatically if a tty is detected.

If you used the `--use-colors / --no-use-colors` then the output will / won't be colorized.

```yaml hl_lines="7 11 38 39 40 41"
{!./src/logging_example/logging_example.yaml!}
```
