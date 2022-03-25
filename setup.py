import os
import sys
import subprocess
from setuptools import setup, find_packages

requirements = open("requirements.txt").read().strip().split("\n")

try:
    version = (
        subprocess.check_output(["git", "describe", "--tags"]).decode("utf8").strip()
    )
except subprocess.CalledProcessError:
    print("Volare must be built with a full Git clone.", file=sys.stderr)
    exit(os.EX_DATAERR)

setup(
    name="volare",
    packages=find_packages(),
    version=version,
    description="A sky130 PDK builder/version manager",
    long_description=open("Readme.md").read(),
    long_description_content_type="text/markdown",
    author="Mohamed Gaber",
    author_email="mohamed.gaber@efabless.com",
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
    ],
    entry_points={"console_scripts": ["volare = volare.__main__:cli"]},
    python_requires=">3.6",
)
