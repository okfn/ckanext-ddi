from setuptools import setup, find_packages

version = '2.0.2'

setup(
    name='ckanext-ddi',
    version=version,
    description="CKAN extension for the DDI standard format for the Worldbank",
    long_description="""\
    """,
    classifiers=[],  # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Liip AG',
    author_email='ogd@liip.ch',
    url='http://www.liip.ch',
    license='AGPL',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['ckanext', 'ckanext.ddi'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
    ],
    entry_points="""
    [ckan.plugins]
    ddi_import=ckanext.ddi.plugins:DdiImport
    """,
)
