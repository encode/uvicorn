REQUIREMENTS="requirements_windows.txt"
VENV="venv"
python3 -m venv "$VENV"
PIP="$VENV\bin\pip"

"$PIP" install -r "$REQUIREMENTS"
"$PIP" install -e .
