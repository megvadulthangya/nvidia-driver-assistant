#!/usr/bin/python3

from setuptools import setup

import glob

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
        ("/usr/share/driver-assistant/supported-gpus/", glob.glob("supported-gpus/*")),
        ("/usr/share/driver-assistant/driver_eula/", ["driver_eula/LICENSE"]),
    ]
    + extra_data,
    scripts=["driver-assistant"],
)
