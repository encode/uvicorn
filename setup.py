#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re

from setuptools import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    path = os.path.join(package, "__init__.py")
    init_py = open(path, "r", encoding="utf8").read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


def get_long_description():
    """
    Return the README.
    """
    return open("README.md", "r", encoding="utf8").read()


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [
        dirpath
        for dirpath, dirnames, filenames in os.walk(package)
        if os.path.exists(os.path.join(dirpath, "__init__.py"))
    ]


env_marker = (
    "sys_platform != 'win32'"
    " and sys_platform != 'cygwin'"
    " and platform_python_implementation != 'PyPy'"
)

requirements = [
    "click==7.*",
    "h11>=0.8,<0.10",
    "websockets==8.*",
    "httptools==0.1.* ;" + env_marker,
    "uvloop>=0.14.0 ;" + env_marker,
]

extras_require = {"watchgodreload": ["watchgod>=0.6,<0.7"]}


setup(
    name="uvicorn",
    version=get_version("uvicorn"),
    url="https://github.com/encode/uvicorn",
    license="BSD",
    description="The lightning-fast ASGI server.",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Tom Christie",
    author_email="tom@tomchristie.com",
    packages=get_packages("uvicorn"),
    install_requires=requirements,
    extras_require=extras_require,
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    entry_points="""
    [console_scripts]
    uvicorn=uvicorn.main:main
    """,
)
