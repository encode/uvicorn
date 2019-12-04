# Examples

## Logging

The below `logging.yaml` overrides the default logging configuration, uses the `uvicorn.error` and `uvicorn.access` loggers colorized thanks to the `use_colors` in the formatters section
It also makes use of the `TRACE` output and setup a debug logger on the `main.py`

![logging](./src/logging_example.png)

```yaml
{!./src/logging.yaml!}
```

in your `main.py`

```python
{!./src/main.py!}
```
