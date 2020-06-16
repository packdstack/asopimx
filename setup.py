#!/usr/bin/env python3

# To view long desc. in html:
#   python setup.py --long-description | rst2html.py > output.html

#from distutils.core import setup
from setuptools import setup, find_packages

with open('README.rst') as f:
    long_desc = f.read()

setup(
    name='asopimx',
    version='0.0.1',
    description='Controller Multiplexer',
    long_description=long_desc,
    author='Daniel Hefti',
    author_email='packdstack@gmail.com',
    #url='https://www.example.com',
    #packages=['asopimx', 'asopimx.ui', 'asopimx.tools', 'asopimx.devices'],
    packages=find_packages(),
    # TODO: fill out requirements
    install_requires=['hidapi'],
    scripts=['scripts/asopimx'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Other Audience',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        # 'Programming Language :: Python :: Implementation :: PyPy', # this would be nice
        'Topic :: Games/Entertainment',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
        'Topic :: System :: Emulators',
        'Topic :: System :: Hardware :: Hardware Drivers',
        'Topic :: Utilities',
    ],
)
