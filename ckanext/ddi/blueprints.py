# -*- coding: utf-8 -*-

import json
import logging
import shutil
import tempfile
import os

from flask import Blueprint
from flask.views import MethodView
from werkzeug.datastructures import FileStorage

import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic as logic
import ckan.model as model
import ckan.plugins.toolkit as toolkit

import ckanapi

from ckanext.ddi.importer import ddiimporter

log = logging.getLogger(__name__)

try:
    # CKAN 2.9
    from ckan.views.home import CACHE_PARAMETERS
except ImportError:
    # CKAN <= 2.8
    from ckan.controllers.home import CACHE_PARAMETERS

try:
    # CKAN 2.9
    from ckan.views.dataset import _get_pkg_template, _setup_template_variables
except ImportError:
    # CKAN <= 2.8: these functions don't exist in core yet
    from ckan.lib.plugins import lookup_package_plugin

    def _get_pkg_template(template_type, package_type=None):
        pkg_plugin = lookup_package_plugin(package_type)
        method = getattr(pkg_plugin, template_type)
        try:
            return method(package_type)
        except TypeError as err:
            if u'takes 1' not in str(err) and u'takes exactly 1' not in str(err):
                raise
            return method()

    def _setup_template_variables(context, data_dict, package_type=None):
        return lookup_package_plugin(package_type).setup_template_variables(
            context, data_dict
        )


ddi_import_blueprint = Blueprint(
    'ddi_import',
    __name__,
    url_prefix=u'/dataset',
    url_defaults={u'package_type': u'dataset'},
)


class ImportView(MethodView):

    package_form = 'package/import_package_form.html'

    def _clean_request_form(self):
        form_data = logic.clean_dict(
            dict_fns.unflatten(
                logic.tuplize_dict(
                    logic.parse_params(
                        toolkit.request.form, ignore_keys=CACHE_PARAMETERS
                    )
                )
            )
        )
        form_data.update(
            logic.clean_dict(
                dict_fns.unflatten(
                    logic.tuplize_dict(logic.parse_params(toolkit.request.files))
                )
            )
        )
        return form_data

    def _get_context(self):
        return {
            'model': model,
            'session': model.Session,
            'user': toolkit.c.user,
            'auth_user_obj': toolkit.c.userobj,
            'save': 'save' in toolkit.request.form,
        }

    def _check_auth(self):
        if not hasattr(toolkit.c, "user") or not toolkit.c.user:
            return toolkit.abort(403, "Forbidden")

        context = self._get_context()

        try:
            toolkit.check_access('package_create', context)
        except toolkit.NotAuthorized:
            return toolkit.abort(401, toolkit._('Unauthorized to create a package'))

    def get(self, package_type, data=None, errors=None, error_summary=None):
        self._check_auth()

        data = data or self._clean_request_form()
        errors = errors or {}
        error_summary = error_summary or {}

        data['group_id'] = toolkit.request.params.get('group') or\
            toolkit.request.form.get('groups__0__id')

        stage = ['active']
        if data.get('state', '').startswith('draft'):
            stage = ['active', 'complete']

        form_snippet = self.package_form
        form_vars = {
            'data': data,
            'errors': errors,
            'error_summary': error_summary,
            'action': 'new',
            'stage': stage,
            'dataset_type': package_type,
        }

        toolkit.c.pkg = None
        toolkit.c.pkg_dict = None
        context = self._get_context()
        _setup_template_variables(context, {}, package_type=package_type)

        new_template = _get_pkg_template(u'new_template', package_type)

        return toolkit.render(
            new_template,
            extra_vars={
                u'form_vars': form_vars,
                u'form_snippet': form_snippet,
                u'dataset_type': package_type,
                u'resources_json': json.dumps(data.get('resources', [])),
                u'errors_json': json.dumps(errors),
            },
        )

    def post(self, package_type):
        self._check_auth()

        pkg_id = None
        file_path = None

        data = self._clean_request_form()

        try:
            user = toolkit.c.user
            importer = ddiimporter.DdiImporter(username=user)

            if isinstance(data.get('upload'), FileStorage):
                log.debug('upload: %s' % data['upload'])
                file_path = self._save_temp_file(data['upload'].stream)
                log.debug('file_path: %s' % file_path)
                pkg_id = importer.run(
                    file_path=file_path,
                    upload=data['upload'],
                    data=data,
                )
            elif data.get('url'):
                log.debug('url: %s' % data['url'])
                pkg_id = importer.run(
                    url=data['url'],
                    data=data,
                )
            else:
                raise PackageImportError('An XML file (uploaded file or URL) is required')

            registry = ckanapi.LocalCKAN(username=user)

            resource_dict = {
                'package_id': pkg_id,
                'name': 'DDI RDF',
                'format': 'rdf',
                'url': '',
                'type': 'attachment',
                'file_type': 'other',
                'visibility': data.get('visibility', 'restricted')
            }
            if isinstance(data.get('rdf_upload'), FileStorage):
                resource_dict['upload'] = data['rdf_upload']
                registry.call_action('resource_create', resource_dict)
            elif data.get('rdf_url'):
                resource_dict['url'] = data['rdf_url']
                registry.call_action('resource_create', resource_dict)

            toolkit.h.flash_success(
                toolkit._(
                    'Dataset import from XML successfully completed. '
                    + 'You can now add data files to it.'
                )
            )
        except toolkit.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(package_type, data, errors, error_summary)
        except Exception as e:
            errors = {
                'import': toolkit._('Dataset import from XML failed: %s' % str(e))
            }
            return self.get(package_type, data, errors)
        finally:
            if file_path is not None:
                os.remove(file_path)

        if pkg_id is not None:
            try:
                toolkit.requires_ckan_version("2.9")
                url = toolkit.h.url_for(
                    u'{}_resource.new'.format(package_type),
                    id=pkg_id,
                )
            except toolkit.CkanVersionException:
                url = toolkit.h.url_for(
                    controller='package',
                    action='new_resource',
                    id=pkg_id,
                )
            return toolkit.redirect_to(url)
        else:
            return toolkit.redirect_to(toolkit.h.url_for('ddi_import.import'))

    def _save_temp_file(self, fileobj):
        fd, file_path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as output_file:
            fileobj.seek(0)
            shutil.copyfileobj(fileobj, output_file)
            fileobj.seek(0)
        return file_path


class PackageImportError(Exception):
    pass


ddi_import_blueprint.add_url_rule(
    rule=u'/import',
    view_func=ImportView.as_view(str(u'import')),
    strict_slashes=False,
)
