# -*- coding: utf-8 -*-

import os
import pytest
import six
import ckan.plugins.toolkit as toolkit
from ckantoolkit.tests import factories


def _assert_in_body(string, response):
    if six.PY2:
        assert string in response.body.decode('utf8')
    else:
        assert string in response.body


def _post_request(app, url, form, files, environ, **kwargs):
    try:
        # CKAN 2.9
        data = dict(form)
        for field, filename in files.items():
            data[field] = _load_test_data(filename)
        return app.post(
            url, data=data, environ_overrides=environ, follow_redirects=False, **kwargs
        )
    except TypeError:
        # CKAN 2.8
        return app.post(
            url,
            params=form,
            upload_files=[
                (field, filename, _load_test_data(filename).read(),)
                for field, filename in files.items()
            ],
            extra_environ=environ,
            **kwargs
        )


def _load_test_data(filename):
    return open(os.path.join(os.path.dirname(__file__), 'test_data', filename), 'rb')


def _patch_storage_path(monkeypatch, tmpdir, ckan_config):
    monkeypatch.setitem(ckan_config, u'ckan.storage_path', str(tmpdir))


@pytest.mark.usefixtures('clean_db', 'clean_index')
@pytest.mark.ckan_config("ckan.webassets.path", "/tmp/webassets")
class TestBlueprints(object):
    def setup(self):
        sysadmin = factories.Sysadmin()
        self.extra_environ = {'REMOTE_USER': sysadmin['name'].encode('ascii')}

    def test_form_display_unauthorized_user(self, app):
        app.get('/dataset/import', status=403)
        app.post('/dataset/import', status=403)

    def test_form_display(self, app, monkeypatch, tmpdir, ckan_config):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        resp = app.get(
            '/dataset/import',
            extra_environ=self.extra_environ,
            status=200,
        )
        _assert_in_body('<input id="field-upload" type="file" name="upload"', resp)
        _assert_in_body(
            '<input id="field-rdf_upload" type="file" name="rdf_upload"', resp
        )

    def test_form_submit_success_xml_file_from_upload(
        self, app, monkeypatch, tmpdir, ckan_config
    ):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        files = {'upload': 'ddi_test.xml'}
        resp = _post_request(
            app, '/dataset/import', {}, files, self.extra_environ, status=302
        )
        expected_id = 'ddi-test-1'
        try:
            toolkit.requires_ckan_version("2.9")
            assert (
                '/dataset/{}/resource/new'.format(expected_id)
                in resp.headers['location']
            )
        except toolkit.CkanVersionException:
            assert (
                '/dataset/new_resource/{}'.format(expected_id)
                in resp.headers['location']
            )
        dataset = toolkit.get_action('package_show')(
            {'ignore_auth': True}, {'id': expected_id}
        )
        assert dataset
        assert len(dataset['resources']) == 1
        assert 'ddi_test.xml' in dataset['resources'][0]['url']

    def test_form_submit_success_xml_and_rdf_files_from_uploads(
        self, app, monkeypatch, tmpdir, ckan_config
    ):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        files = {'upload': 'ddi_test.xml', 'rdf_upload': 'ddi_test.rdf'}
        resp = _post_request(
            app, '/dataset/import', {}, files, self.extra_environ, status=302
        )
        expected_id = 'ddi-test-1'
        try:
            toolkit.requires_ckan_version("2.9")
            assert (
                '/dataset/{}/resource/new'.format(expected_id)
                in resp.headers['location']
            )
        except toolkit.CkanVersionException:
            assert (
                '/dataset/new_resource/{}'.format(expected_id)
                in resp.headers['location']
            )
        dataset = toolkit.get_action('package_show')(
            {'ignore_auth': True}, {'id': expected_id}
        )
        assert dataset
        assert len(dataset['resources']) == 2
        assert 'ddi_test.xml' in dataset['resources'][0]['url']
        assert 'ddi_test.rdf' in dataset['resources'][1]['url']

    """
    def test_form_submit_success_xml_file_from_url(
        self, app, monkeypatch, tmpdir, ckan_config
    ):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        # TODO: test importing from a URL, mock the HTTP requests with responses

    def test_form_submit_success_xml_and_rdf_files_from_urls(
        self, app, monkeypatch, tmpdir, ckan_config
    ):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        # TODO: test importing from URLs, mock the HTTP requests with responses
    """

    def test_duplicate_dataset(self, app, monkeypatch, tmpdir, ckan_config):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        files = {'upload': 'ddi_test.xml'}
        resp = _post_request(
            app, '/dataset/import', {}, files, self.extra_environ, status=302
        )
        resp = _post_request(
            app, '/dataset/import', {}, files, self.extra_environ, status=200
        )
        _assert_in_body('Dataset already exists and duplicates are not allowed', resp)

    def test_form_submit_invalid(self, app, monkeypatch, tmpdir, ckan_config):
        _patch_storage_path(monkeypatch, tmpdir, ckan_config)
        resp = _post_request(
            app, '/dataset/import', {}, {}, self.extra_environ, status=200
        )
        _assert_in_body('An XML file (uploaded file or URL) is required', resp)
