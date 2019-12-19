# Examples

## Custom logging

The below `logging_example.yaml` is a yaml representation of the default logging configuration.

You could load it to a dict using pyyaml for instance with:

```python
with open('logging_example.yaml', 'r') as stream:
    config = yaml.load(stream, yaml.FullLoader)
```

Then you can pass the config dict, using the `--log-config` flag.

It sets 2 loggers:
1. `uvicorn.error` whose formatter is the `uvicorn.logging.DefaultFormatter`. 
2. `uvicorn.access` whose formatter is the `uvicorn.logging.AccessFormatter`. 

Both formatters will output a colorized automatically if a tty is detected.

If you used the `--use-colors / --no-use-colors` then the output will / won't be colorized.

```yaml
version: 1
disable_existing_loggers: False
formatters:
  default:
    "()": uvicorn.logging.DefaultFormatter
    format: "%(levelprefix)s %(message)s"
  access:
    "()": uvicorn.logging.AccessFormatter
    format: '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
handlers:
  default:
    formatter: default
    class: logging.StreamHandler
    stream: ext://sys.stdout
  access:
    formatter: access
    class: logging.StreamHandler
    stream: ext://sys.stdout
loggers:
  uvicorn.error:
    level: INFO
    handlers:
      - default
    propagate: no
  uvicorn.access:
    level: INFO
    handlers:
      - access
    propagate: no
```
