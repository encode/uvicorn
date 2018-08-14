#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import platform

from setuptools import setup


def get_version(package):
    """
    Return package version as listed in `__version__` in `init.py`.
    """
    path = os.path.join(package, '__init__.py')
    init_py = open(path, 'r', encoding='utf8').read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)


def get_long_description():
    """
    Return the README.
    """
    return open('README.md', 'r', encoding='utf8').read()


def get_packages(package):
    """
    Return root package and all sub-packages.
    """
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(package)
            if os.path.exists(os.path.join(dirpath, '__init__.py'))]


if platform.python_implementation() == 'PyPy':
    requirements = [
        'click',
        'h11',
        'websockets>=6.0'
    ]
elif platform.system() == 'Windows' or platform.system().startswith('CYGWIN'):
    requirements = [
        'click',
        'h11',
        'websockets>=6.0'
    ]
else:
    requirements = [
        'click',
        'h11',
        'httptools',
        'uvloop',
        'websockets>=6.0'
    ]


setup(
    name='uvicorn',
    version=get_version('uvicorn'),
    url='https://github.com/encode/uvicorn',
    license='BSD',
    description='The lightning-fast ASGI server.',
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    author='Tom Christie',
    author_email='tom@tomchristie.com',
    packages=get_packages('uvicorn'),
    install_requires=requirements,
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
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    entry_points="""
    [console_scripts]
    uvicorn=uvicorn.main:main
    """
)
