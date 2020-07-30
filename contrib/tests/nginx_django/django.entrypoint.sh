#!/bin/bash
pip install /app/uvicorn

rm -rfv /app/uvicorn/.*
rm -rfv /app/uvicorn/*

"$@"
