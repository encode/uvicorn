pytest --ignore venv --cov=uvicorn --cov=tests --cov-report=term-missing
coverage html
autoflake --recursive uvicorn tests
flake8 uvicorn tests --ignore=W503,E203,E501,E731
black uvicorn tests --check
