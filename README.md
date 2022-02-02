DDI
===

The Data Documentation Initiative (DDI) is an international standard available at [ddialliance.org](https://ddialliance.org/)

ckanext-ddi
===========

![Tests](https://github.com/okfn/ckanext-ddi/workflows/Tests/badge.svg?branch=master)
[![codecov](https://codecov.io/gh/okfn/ckanext-ddi/branch/master/graph/badge.svg?token=64CxGCG5z4)](https://codecov.io/gh/okfn/ckanext-ddi)

**NOTE**: This is a heavily customized version for a specific project. If you want more generic support check out the upstream repo: https://github.com/liip/ckanext-ddi

---


DDI extension for CKAN.

Features:

* [Configuration of DDI fields to customize display](#configuration)
* [Upload DDI files (XML) to a CKAN instance](#import)


## Installation

**Requirement: This extensions runs on CKAN 2.8 or higher.**

Use `pip` to install this plugin. This example installs it in `/home/www-data`

```bash
source /home/www-data/pyenv/bin/activate
pip install -e git+https://github.com/liip/ckanext-ddi.git#egg=ckanext-ddi --src /home/www-data
cd /home/www-data/ckanext-ddi
pip install -r requirements.txt
python setup.py develop
```

Make sure to add `ddi_import` to `ckan.plugins` in your config file.

Make sure

* [ckanext-harvest extension](https://github.com/ckan/ckanext-harvest) and
* [ckanext-scheming extension](https://github.com/ckan/ckanext-scheming)

are installed as well.

## Configuration

### CKAN configuration (production.ini)
Available options are:

```bash
ckanext.ddi.default_license = CC0-1.0
ckanext.ddi.allow_duplicates = True
ckanext.ddi.override_datasets = False
ckanext.ddi.default_country_code = WORLD
```

The `config_file` is simply the path to the DDI-specific configuration of this extension (see below).
The `default_license` allows a user to configure a license that is used for all DDI imports, if the license is not specified explicitly.
The `allow_duplicates` option is used to determine, if duplicate datasets are allowed or not. Duplicates are determined by the unique `id_number` attribute (defaults to `False`).
With `override_datasets` you can specify, if you import a dataset that already exists, if a new dataset should be created or if the existing one should be overridden (defaults to `False`).
The `default_conuntry_code` option will force all datasets to have a country code (defaults to `WORLD` because UNHCR extension use it).

### Web interface

#### Import

If you are logged in and you have the appropriate permissions, you find a new button "Import Dataset from DDI/XML" on the dataset page.

![Import Dataset from DDI/XML button](https://raw.github.com/liip/ckanext-ddi/master/screenshots/add_dataset_button.png)

This buttons leads you to an import page, where a DDI XML can either be uploaded or specified as URL.

![Import Dataset page](https://raw.github.com/liip/ckanext-ddi/master/screenshots/import_dataset.png)



## Development

This CKAN extensions uses flake8 to ensure basic code quality.

You can add a pre-commit hook when you have installed flake8:

```bash
flake8 --install-hook
```

Travis CI is used to check the code for all PRs.

## Acknowledgements

This module was developed with support from the World Bank to provide a solution for National Statistical Offices (NSOs) that need to publish data on CKAN platforms.
