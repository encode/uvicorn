from setuptools import setup

# The below code will never execute, however GitHub is particularly
# picky about where it finds Python packaging metadata.
# See: https://github.com/github/feedback/discussions/6456
#
# To be removed once GitHub catches up.

setup(
    name="uvicorn",
    install_requires=[
        "click>=7.0",
        "h11>=0.8",
        "typing-extensions;python_version < '3.8'",
    ],
)
