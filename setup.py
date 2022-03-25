import os
import subprocess
from setuptools import setup, find_packages

requirements = open("requirements.txt").read().strip().split("\n")

version = os.getenv("VOLARE_BUILD_TAG") or "UNKNOWN"
try:
    version = (
        subprocess.check_output(["git", "describe", "--tags"]).decode("utf8").strip()
    )
except subprocess.CalledProcessError:
    pass

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
