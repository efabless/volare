#!/usr/bin/env python3
from setuptools import setup, find_packages

from volare import __version__

requirements = open("requirements.txt").read().strip().split("\n")

setup(
    name="volare",
    packages=find_packages(),
    package_data={"volare": ["py.typed"]},
    version=__version__,
    description="An open_pdks PDK builder/version manager",
    long_description=open("Readme.md").read(),
    long_description_content_type="text/markdown",
    author="Efabless Corporation",
    author_email="donn@efabless.com",
    install_requires=requirements,
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
    ],
    entry_points={"console_scripts": ["volare = volare.__main__:cli"]},
    python_requires=">3.6",
)
