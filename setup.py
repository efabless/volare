#!/usr/bin/env python3
import os
import subprocess
from setuptools import setup, find_packages

module_name = "volare"

__dir__ = os.path.abspath(os.path.dirname(__file__))
version = subprocess.check_output(
    [
        "python3",
        os.path.join(
            __dir__,
            module_name,
            "__version__.py",
        ),
    ],
    encoding="utf8",
)

requirements = (
    open(os.path.join(__dir__, "requirements.txt")).read().strip().split("\n")
)

setup(
    name=module_name,
    packages=find_packages(),
    package_data={"volare": ["py.typed"]},
    version=version,
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
