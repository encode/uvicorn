FROM python:3.8

WORKDIR /app

RUN pip install --no-cache-dir fastapi==0.70.0 memory_profiler==0.58.0 uvicorn[standard]==0.15.0

COPY main.py /app

EXPOSE 8000
