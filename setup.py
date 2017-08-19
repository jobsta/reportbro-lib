# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from codecs import open
from os import path
from reportbro import __version__

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='reportbro-lib',
    version=__version__,
    description='PDF and Excel report generation library',
    long_description=long_description,
    url='https://www.reportbro.com',

    author='jobsta',
    author_email='alex@reportbro.com',
    license='AGPL-3.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        #'Development Status :: 5 - Production/Stable',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: GNU Affero General Public License v3',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='pdf excel report generation creation design',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=[
        'Babel>=2.0',
        'enum34',
        'reportbro-fpdf>=1.7.4',
        'Pillow>=4.0',
        'simpleeval',
        'xlsxwriter'
    ],

    package_data={
        'reportbro': ['data/logo_watermark.png'],
    },
)