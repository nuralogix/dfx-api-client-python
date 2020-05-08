from setuptools import setup

setup(
    name='dfxapiclient',
    version='1.2.0',
    packages=['dfxapiclient'],
    install_requires=['protobuf', 'requests', 'websockets'],
    setup_requires=['wheel'],
    description='The DFX API Python SimpleClient is a minimal client for the DeepAffex API.',
)
