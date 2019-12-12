#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import io

# -- import re
from glob import glob
from os.path import basename
from os.path import dirname
from os.path import join
from os.path import splitext

from setuptools import find_packages
from setuptools import setup


def read(*names, **kwargs):
    with io.open(
        join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")
    ) as fh:
        return fh.read()


setup(
    name="batch_config",
    version="1.564.11",
    license="BSD-2-Clause",
    description="Convenience wrappers for running batch jobs in python",
    author="Jason Thorpe",
    author_email="jdthorpe@gmail.com",
    url="https://github.com/jdthorpe/batch-config",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        # uncomment if you test on these interpreters:
        # 'Programming Language :: Python :: Implementation :: IronPython',
        # 'Programming Language :: Python :: Implementation :: Jython',
        # 'Programming Language :: Python :: Implementation :: Stackless',
        "Topic :: Utilities",
    ],
    project_urls={"Issue Tracker": "https://github.com/jdthorpe/batch-config/issues"},
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
    ],
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
    install_requires=[
        "azure-batch==8.0.0",
        "azure-storage-blob==12.0.0",
        "jsonschema==3.2.0",
    ],
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    setup_requires=["pytest-runner"],
    entry_points={},  # { 'console_scripts': [ 'nameless = nameless.cli:main', w] },
)
#-- adal==1.2.2
#-- attrs==19.3.0
#-- azure-batch==8.0.0
#-- azure-common==1.1.23
#-- azure-core==1.0.0
#-- azure-storage-blob==12.0.0
#-- -e git+https://github.com/jdthorpe/batch-config.git@6b326c5875e78a2d9abe65081ccb335d3baf4275#egg=batch_config
#-- certifi==2019.9.11
#-- cffi==1.13.2
#-- chardet==3.0.4
#-- cryptography==2.8
#-- idna==2.8
#-- importlib-metadata==0.23
#-- isodate==0.6.0
#-- joblib==0.14.0
#-- jsonschema==3.2.0
#-- more-itertools==7.2.0
#-- msrest==0.6.10
#-- msrestazure==0.6.2
#-- numpy==1.17.4
#-- oauthlib==3.1.0
#-- pycparser==2.19
#-- PyJWT==1.7.1
#-- pyrsistent==0.15.6
#-- python-dateutil==2.8.1
#-- requests==2.22.0
#-- requests-oauthlib==1.3.0
#-- six==1.13.0
#-- urllib3==1.25.7
#-- zipp==0.6.0
