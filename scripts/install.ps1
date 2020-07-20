PYTHON="python3"
REQUIREMENTS="requirements_windows.txt"
VENV="venv"
"$PYTHON" -m venv "$VENV"
PIP="$VENV/bin/pip"

"$PIP" install -r "$REQUIREMENTS"
"$PIP" install -e .
