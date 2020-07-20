set PREFIX="venv/bin/"
PYTHONPATH=. ${PREFIX}pytest --ignore venv --cov=uvicorn --cov=tests --cov-report=term-missing ${@}
${PREFIX}coverage html
${PREFIX}autoflake --recursive uvicorn tests
${PREFIX}flake8 uvicorn tests --ignore=W503,E203,E501,E731
${PREFIX}black uvicorn tests --check
