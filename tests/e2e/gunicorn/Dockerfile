# syntax = docker/dockerfile:1.2-experimental
FROM python:3.9-slim-buster as builder
RUN export DEBIAN_FRONTEND=noninteractive && \
  apt-get update && \
  apt-get -y upgrade && \
  apt-get install -y --no-install-recommends curl build-essential git wait-for-it && \
  apt-get -y clean && \
  rm -rf /var/lib/apt/lists/*
RUN pip install gunicorn starlette
COPY ["requirements.txt", "setup.py", "setup.cfg", "README.md", "/opt/"]
COPY ./uvicorn /opt/uvicorn
WORKDIR /opt
RUN pip install -r /opt/requirements.txt