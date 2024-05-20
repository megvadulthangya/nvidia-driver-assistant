#!/usr/bin/python3

from setuptools import setup

extra_data = []

setup(
    name="driver-assistant",
    author="Alberto Milone",
    author_email="amilone@nvidia.com",
    maintainer="Alberto Milone",
    maintainer_email="amilone@nvidia.com",
    url="https://temporaryaddress.com",
    license="mit",
    description="Detect the NVIDIA GPUs and recommend a driver",
    packages=["DriverAssistant"],
    data_files=[
        ("/usr/share/driver-assistant/", "supported-gpus"),
        ("/usr/share/doc/driver-assistant/", ["README"]),
    ]
    + extra_data,
    scripts=["driver-assistant"],
)
