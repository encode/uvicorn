#!/bin/bash
pip install /app/uvicorn

rm -rf /app/uvicorn/.*
rm -rf /app/uvicorn/*

"$@"
