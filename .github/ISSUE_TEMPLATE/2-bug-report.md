---
name: Bug report
about: Report a bug to help improve this project
---

### Checklist

<!-- Please make sure you check all these items before submitting your bug report. -->

- [ ] The bug is reproducible against the latest release and/or `master`.
- [ ] There are no similar issues or pull requests to fix it yet.

### Describe the bug

<!-- A clear and concise description of what the bug is. -->

### To reproduce

<!-- Provide a *minimal* example with steps to reproduce the bug locally.

NOTE: try to keep any external dependencies *at an absolute minimum* .
In other words, remove anything that doesn't make the bug go away.

-->

### Expected behavior

<!-- A clear and concise description of what you expected to happen. -->

### Actual behavior

<!-- A clear and concise description of what actually happens. -->

### Debugging material

<!-- Any tracebacks, screenshots, etc. that can help understanding the problem.

NOTE:
- Please list tracebacks in full (don't truncate them).
- If relevant, consider turning on DEBUG or TRACE logs for additional details (see the Logging section on https://www.uvicorn.org/settings/ specifically the `log-level` flag).
- Consider using `<details>` to make tracebacks/logs collapsible if they're very large (see https://gist.github.com/ericclemmons/b146fe5da72ca1f706b2ef72a20ac39d).
-->

### Environment

- OS / Python / Uvicorn version: just run `uvicorn --version`
- The exact command you're running uvicorn with, all flags you passed included. If you run it with gunicorn please do the same. If there is a reverse-proxy involved and you cannot reproduce without it please give the minimal config of it to reproduce.

### Additional context

<!-- Any additional information that can help understanding the problem.

Eg. linked issues, or a description of what you were trying to achieve. -->