from setuptools import setup

setup(
    name='dfxapiclient',
    version='1.0.0',
    packages=['dfxapiclient'],
    install_requires=['asyncio', 'protobuf', 'requests', 'uuid', 'websockets'],
    setup_requires=['wheel'],
    long_description=open('README.md').read(),
)
