# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from distutils.util import convert_path
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

version_info = {}
version_path = convert_path('reportbro/version.py')
with open(version_path) as version_file:
    exec(version_file.read(), version_info)

setup(
    name='reportbro-lib',
    version=version_info['__version__'],
    description='Generate PDF and Excel reports from visually designed templates',
    long_description=long_description,
    url='https://www.reportbro.com',

    author='jobsta',
    author_email='alex@reportbro.com',
    license='AGPL-3.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: GNU Affero General Public License v3',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],

    keywords='pdf excel report generate create web template layout',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[
        'Babel>=2.0',
        'enum34',
        'reportbro-fpdf>=1.7.10',
        'Pillow>=4.0',
        'reportbro-simpleeval>=0.9.11',
        'qrcode>=6.1',
        'typing;python_version<"3.5"',
        'xlsxwriter'
    ],

    package_data={
        'reportbro': ['data/logo_watermark.png'],
    },
)
