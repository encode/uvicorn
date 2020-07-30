ARG PYTHON_VERSION="3.8"
FROM python:${PYTHON_VERSION}-slim

ARG DJANGO_VERSION="3.0.8"
# if set to any value then latest version of django will be installed
ARG DJANGO_LATEST

RUN if [ -z "${DJANGO_LATEST+x}" ]; then pip install django==${DJANGO_VERSION}; else pip install django; fi

WORKDIR /app
RUN django-admin startproject example
WORKDIR /app/example

COPY django.entrypoint.sh .
RUN chmod +x ./django.entrypoint.sh
ENTRYPOINT ["./django.entrypoint.sh"]
