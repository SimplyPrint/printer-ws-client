import re
from setuptools import setup

VERSIONFILE="simplyprint_ws_client/version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^VERSION = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)

if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(
    name="simplyprint-ws-client",
    version=verstr,
    description="SimplyPrint WebSocket Client",
    url="https://github.com/SimplyPrint/printer-ws-client",
    author="SimplyPrint",
    license="AGPLv3",
    packages=["simplyprint_ws_client"],
    install_requires=[
        "tornado==6.2",
        "psutil==5.9.4",
        "sentry-sdk==1.17.0",
        "netifaces==0.11.0",
        "requests==0.11.0",
    ]
)
