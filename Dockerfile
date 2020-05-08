FROM python:3.8-slim
WORKDIR /usr/src/app

COPY . .
RUN python -m venv . && pip install -r requirements.txt && pip install starlette && pip install -e .
