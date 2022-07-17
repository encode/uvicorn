#!/usr/bin/env python

import os
import re

from setuptools import setup

PACKAGE_NAME = "uvicorn"

PACKAGE_INIT_FILENAME = "__init__.py"


def read_utf8_file(filepath):
    """
    Return file contents read as UTF-8.
    """
    return open(filepath, encoding="utf8").read()


def get_version():
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    return re.search(
        r"__version__ = "
        r"(['\"])"
        r"(?P<version>[^'\"]+)"
        r"\1",
        read_utf8_file(
            os.path.join(PACKAGE_NAME, PACKAGE_INIT_FILENAME),
        ),
    ).group("version")


def get_long_description():
    """
    Return contents of README file.
    """
    return read_utf8_file("README.md")


def get_packages():
    """
    Return root package and all sub-packages.
    """
    return [
        dirpath
        for dirpath, _dirnames, filenames
        in os.walk(PACKAGE_NAME)
        if PACKAGE_INIT_FILENAME in filenames
    ]


env_marker_cpython = (
    "sys_platform != 'win32'"
    " and (sys_platform != 'cygwin'"
    " and platform_python_implementation != 'PyPy')"
)

env_marker_win = "sys_platform == 'win32'"
env_marker_below_38 = "python_version < '3.8'"

minimal_requirements = [
    "click>=7.0",
    "h11>=0.8",
    "typing-extensions;" + env_marker_below_38,
]


extra_requirements = [
    "websockets>=10.0",
    "httptools>=0.4.0",
    "uvloop>=0.14.0,!=0.15.0,!=0.15.1; " + env_marker_cpython,
    "colorama>=0.4;" + env_marker_win,
    "watchfiles>=0.13",
    "python-dotenv>=0.13",
    "PyYAML>=5.1",
]


setup(
    name=PACKAGE_NAME,
    version=get_version(),
    url="https://www.uvicorn.org/",
    license="BSD",
    description="The lightning-fast ASGI server.",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Tom Christie",
    author_email="tom@tomchristie.com",
    packages=get_packages(),
    python_requires=">=3.7",
    install_requires=minimal_requirements,
    extras_require={"standard": extra_requirements},
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    entry_points="""
    [console_scripts]
    uvicorn=uvicorn.main:main
    """,
    project_urls={
        "Funding": "https://github.com/sponsors/encode",
        "Source": "https://github.com/encode/uvicorn",
        "Changelog": "https://github.com/encode/uvicorn/blob/master/CHANGELOG.md",
    },
)
