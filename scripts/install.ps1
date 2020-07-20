PYTHON="python3"
REQUIREMENTS="requirements.txt"
VENV="venv"
"$PYTHON" -m venv "$VENV"
PIP="$VENV/bin/pip"

"$PIP" install -r "$REQUIREMENTS"
"$PIP" install -e .
