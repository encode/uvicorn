#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys

from setuptools import setup

sys.dont_write_bytecode = True


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


version = get_version('uvicorn')


setup(
    name='uvicorn',
    version=version,
    url='https://github.com/tomchristie/uvicorn',
    license='BSD',
    description='An ASGI server, using Gunicorn and uvloop.',
    author='Tom Christie',
    author_email='tom@tomchristie.com',
    packages=get_packages('uvicorn'),
    install_requires=[
        'gunicorn',
        'httptools',
        'uvloop'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points="""
    [console_scripts]
    uvicorn=uvicorn.main:run
    """
)
