#!/usr/bin/env bash

for ((c = 1; c <= $1; c++)); do
    ./tcping/tcping localhost 8000
done
