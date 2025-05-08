from setuptools import setup, find_packages
from miarka_processing_service import __version__
import os

def read_file(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

try:
    with open("requirements/prod", "r") as f:
        install_requires = [x.strip() for x in f.readlines()]
except IOError:
    install_requires = []

setup(
    name='miarka_processing_service',
    version=__version__,
    description="Service to perform operations on miarka.",
    long_description=read_file('README.md'),
    keywords='bioinformatics',
    author='CGU, Uppsala University',
    packages=find_packages(include=["miarka_processing_service*"]),
    include_package_data=True,
    entry_points={
        'console_scripts': ['miarka-processing-service = miarka_processing_service.app:start']
    },
    install_requires=install_requires,
)
