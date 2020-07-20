#!/bin/sh -e

# Use the Python executable provided from the `-p` option, or a default.
[ "$1" = "-p" ] && PYTHON=$2 || PYTHON="python3"

echo $OSTYPE

if [ "$OSTYPE" = "linux-gnu" ]; then
  REQUIREMENTS="requirements.txt"
elif [ "$OSTYPE" = "win32" ]; then
  REQUIREMENTS="requirements_windows.txt"
else
  echo "SHIT"
fi

echo "$REQUIREMENTS"

VENV="venv"

set -x

if [ -z "$GITHUB_ACTIONS" ]; then
  "$PYTHON" -m venv "$VENV"
  PIP="$VENV/bin/pip"
else
  PIP="pip"
fi

"$PIP" install -r "$REQUIREMENTS"
"$PIP" install -e .
