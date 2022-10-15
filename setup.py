from setuptools import setup
from simplyprint_ws_client import VERSION

setup(
    name="simplyprint-ws-client",
    version=VERSION,
    description="SimplyPrint Websocket Client",
    url="https://github.com/SimplyPrint/printer-ws-client",
    author="SimplyPrint",
    license="AGPLv3",
    packages=["simplyprint_ws_client"],
    install_requires=[
        "tornado",
        "psutil",
        "sentry-sdk",
        "netifaces",
        "requests",
    ]
)
