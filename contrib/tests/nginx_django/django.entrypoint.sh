#!/bin/bash
pip install /app/uvicorn

rm -rf /app/uvicorn/.*
rm -rf /app/uvicorn/*

printf "ALLOWED_HOSTS=['*']" >> /app/example/example/settings.py

"$@"
