import re

import requests
import codecs

import ckan.plugins.toolkit as tk
from ckan.lib.munge import munge_title_to_name, munge_name
from ckanext.harvest.harvesters import HarvesterBase
from ckanext.ddi.importer import metadata

from ckanext.scheming.helpers import scheming_get_dataset_schema

import ckanapi

import logging
log = logging.getLogger(__name__)


class DdiImporter(HarvesterBase):
    def __init__(self, username=None):
        self.username = username

    def run(self, file_path=None, url=None, params=None, upload=None, data=None):
        """ Run the import process from uploaded file or from URL """

        pkg_dict = None
        ckan_metadata = metadata.DdiCkanMetadata()

        if file_path is not None:
            with codecs.open(file_path, 'rb') as xml_file:
                pkg_dict = ckan_metadata.load(xml_file.read())
        elif url is not None:
            log.debug('Fetch file from %s' % url)
            try:
                r = requests.get(url)
            except requests.exceptions.RequestException as e:
                raise ContentFetchError(
                    'Error while getting URL %s: %r'
                    % (url, e)
                )

            pkg_dict = ckan_metadata.load(r.content)
            resources = []

            # if we can assume the URL is from a NADA catalogue
            # set some properties automagically
            if '/index.php/catalog/ddi/' in url:
                nada_catalog_url = url.replace('/ddi/', '/', 1)
                if pkg_dict['url'] == '':
                    pkg_dict['url'] = nada_catalog_url

                resources.append({
                    'url': nada_catalog_url,
                    'name': 'NADA catalog entry',
                    'format': 'html',
                    'type': 'attachment',
                    'file_type': 'other',
                    'visibility': data.get('visibility', 'restricted')
                })

            if pkg_dict['url'] == '':
                pkg_dict['url'] = url

            resources.append({
                'url': url,
                'name': 'DDI XML',
                'format': 'xml',
                'type': 'attachment',
                'file_type': 'other',
                'visibility': data.get('visibility', 'restricted')
            })
            pkg_dict['resources'] = resources

        pkg_dict = self.improve_pkg_dict(pkg_dict, params, data)

        try:
            return self.insert_or_update_pkg(pkg_dict, upload)
        except tk.ValidationError as e:
            raise e
        except Exception as e:
            raise ContentImportError(
                'Could not import dataset %s: %s'
                % (pkg_dict.get('name', ''), e)
            )

    def insert_or_update_pkg(self, pkg_dict, upload=None):
        registry = ckanapi.LocalCKAN(username=self.username)
        allow_duplicates = tk.asbool(
            tk.config.get('ckanext.ddi.allow_duplicates', False)
        )
        override_datasets = tk.asbool(
            tk.config.get('ckanext.ddi.override_datasets', False)
        )

        visibility = pkg_dict.pop('visibility', 'restricted')

        try:
            existing_pkg = registry.call_action('package_show', pkg_dict)
            if not allow_duplicates and not override_datasets:
                raise ContentDuplicateError(
                    'Dataset already exists and duplicates are not allowed.'
                )

            if override_datasets:
                pkg_dict.pop('id', None)
                pkg_dict.pop('name', None)
                existing_pkg.update(pkg_dict)
                pkg_dict = existing_pkg
                registry.call_action('package_update', pkg_dict)
            else:
                raise ckanapi.NotFound()
        except ckanapi.NotFound:
            pkg_dict.pop('id', None)
            pkg_dict['name'] = self._gen_new_name(pkg_dict['name'])
            registry.call_action('package_create', pkg_dict)

        if upload is not None:
            try:
                registry.call_action(
                    'resource_create',
                    {
                        'package_id': pkg_dict['name'],
                        'upload': upload,
                        'name': 'DDI XML',
                        'format': 'xml',
                        'url': '',
                        'type': 'attachment',
                        'file_type': 'other',
                        'visibility': visibility
                    }
                )
            except Exception as e:
                raise UploadError(
                    'Could not upload file: %s' % str(e)
                )

        log.debug(pkg_dict['name'])
        return pkg_dict['name']

    def improve_pkg_dict(self, pkg_dict, params, data=None):
        if pkg_dict['name'] != '':
            pkg_dict['name'] = munge_name(pkg_dict['name']).replace('_', '-')
        else:
            pkg_dict['name'] = munge_title_to_name(pkg_dict['title'])
        if pkg_dict['url'] == '':
            pkg_dict.pop('url', None)

        # override the 'id' as this never matches the CKAN internal ID
        pkg_dict['id'] = pkg_dict['name']

        if params is not None and params.get(license, None) is not None:
            pkg_dict['license_id'] = params['license']
        else:
            pkg_dict['license_id'] = tk.config.get('ckanext.ddi.default_license')

        # TODO: move all this to a interface method in ckanext-unhcr

        # Save as draft to enable the stages on the form
        # TODO: what about updates (if overriding)
        pkg_dict['state'] = 'draft'

        if data:
            for field in (
                'owner_org',
                'private',
                'visibility',  # for resources
                'license_id',
                'external_access_level',
            ):
                if field in data:
                    pkg_dict[field] = data[field]

            pkg_dict['archived'] = 'False'

        if pkg_dict.get('keywords'):
            pkg_dict['keywords'] = _get_keywords(pkg_dict['keywords'])

        if pkg_dict.get('unit_of_analysis'):
            pkg_dict['unit_of_measurement'] = pkg_dict['unit_of_analysis']

        if pkg_dict.get('data_collector'):
            pkg_dict['data_collector'] = _get_data_collector_values(
                pkg_dict['data_collector'])

        if pkg_dict.get('data_collection_technique'):
            pkg_dict['data_collection_technique'] = _get_data_collection_technique_value(
                pkg_dict['data_collection_technique'])

        if pkg_dict.get('id_number'):
            pkg_dict['original_id'] = pkg_dict['id_number']

        if pkg_dict.get('abstract'):
            pkg_dict['notes'] = pkg_dict['abstract']

        if pkg_dict.get('abbreviation'):
            pkg_dict['short_title'] = pkg_dict['abbreviation']

        pkg_dict['ddi'] = True

        return pkg_dict


def _get_dataset_schema():

    return scheming_get_dataset_schema('dataset')


def get_allowed_values(field_name):

    schema = _get_dataset_schema()
    if not schema:
        return []

    for field in schema['dataset_fields']:
        if field['field_name'] == field_name:
            allowed_values = field['choices']

    return allowed_values


def _get_data_collection_technique_value(xml_value):

    allowed_values = get_allowed_values('data_collection_technique')

    try:
        brackets_code = re.search(r'\[.*?\]', xml_value).group(0)
        brackets_code = brackets_code.lstrip('[').rstrip(']')
    except AttributeError:
        brackets_code = ''

    for allowed_value in allowed_values:
        if (xml_value.lower() == allowed_value['label'].lower() or
                xml_value.lower() == allowed_value['value'].lower() or
                brackets_code.lower() == allowed_value['value']):
            return allowed_value['value']

    return xml_value


def _get_data_collector_values(xml_values):
    collectors = []
    for item in xml_values:
        value = item.get('value', '')
        if value:
            collectors.append(value.strip())
    return ','.join(collectors)


def _get_keywords(xml_values):

    out = []

    allowed_values = get_allowed_values('keywords')

    for item in xml_values:
        found = False
        for allowed_value in allowed_values:
            if (item.get('abbr', '').lower() == allowed_value['value'] or
                    item.get('value', '').lower() == allowed_value['label'].lower()):
                out.append(allowed_value['value'])
                found = True
                break
        if not found:
            # Add value anyway so it fails validation
            out.append(item.get('value'))

    return out


class ContentFetchError(Exception):
    pass


class ContentImportError(Exception):
    pass


class ContentDuplicateError(Exception):
    pass


class UploadError(Exception):
    pass
