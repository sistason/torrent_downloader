#!/usr/bin/env python

from distutils.core import setup
from setuptools import find_packages

setup(name='Torrent Downloader via Premiumize.me',
      version='1.1',
      description='Search and download from piratebay via premiumize.me',
      author='Sistason',
      url='https://github.com/sistason/torrent_downloader',
      classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3',
      ],
      packages=find_packages(),
      install_requires=[
        'click',
      ],
      entry_points={
        'console_scripts': [
            'torr_dl=torrent_downloader.cli:cli'
        ],
      },
      )
