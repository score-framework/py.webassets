# Copyright © 2015-2017 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

from score.init import (
    ConfiguredModule, ConfigurationError, parse_list, parse_bool)
import os
import email.utils
import time
import hashlib
from collections import namedtuple
import re

Request = namedtuple('Request', ('path', 'GET', 'headers'))

defaults = {
    'rootdir': None,
    'modules': [],
    'freeze': False,
    'tpl.autobundle': False,
}


def init(confdict, http=None, tpl=None):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`netfs` :default:`True`
        The initializer will upload all webassets to a :mod:`score.netfs`
        server, if one was configured. You can disable this feature by passing a
        `False` value here
    """
    conf = dict(defaults.items())
    conf.update(confdict)
    modules = parse_list(conf['modules'])
    if conf['rootdir'] and not os.path.exists(conf['rootdir']):
        raise ConfigurationError(
            'score.webassets', 'Configured rootdir does not exist')
    try:
        freeze = parse_bool(conf['freeze'])
    except ValueError:
        freeze = conf['freeze']
    return ConfiguredWebassetsModule(http, tpl, modules, conf['rootdir'],
                                     freeze, parse_bool(conf['tpl.autobundle']))


class ConfiguredWebassetsModule(ConfiguredModule):
    """
    This module's :class:`configuration class
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, http, tpl, modules, rootdir, freeze, tpl_autobundle):
        super().__init__(__package__)
        self.http = http
        self.tpl = tpl
        self.modules = modules
        self.rootdir = rootdir
        self.freeze = freeze
        self.tpl_autobundle = tpl_autobundle
        self._frozen_versions = {}
        if tpl:
            self._register_tpl_globals()
        if http:
            self._register_http_route()

    def _register_tpl_globals(self):
        self.tpl.filetypes['text/html'].add_global(
            'webassets_link', self._generate_html_tag, escape=False)
        self.tpl.filetypes['text/html'].add_global(
            'webassets_content', self.get_bundle_content, escape=False)

    def _register_http_route(self):
        @self.http.newroute('score.webassets', '/_assets/{module}/{path>.*}')
        def webassets(ctx, module, paths):
            request = ctx.http.request
            result = self.get_request_response(Request(
                '/' + request.path.lstrip('/').split('/', maxsplit=1)[1],
                request.GET,
                request.headers,
            ))
            if isinstance(result, int):
                ctx.http.response.status = result
            else:
                for header, value in result[0].items():
                    ctx.http.response.headers[header] = value
                ctx.http.response.text = result[1]

        @webassets.vars2url
        def webassets_vars2url(ctx, module, paths):
            return '/_assets' + self.get_bundle_url(module, paths)

        @webassets.match2vars
        def webassets_match2vars(ctx, matches):
            return {
                'module': matches['module'],
                'paths': matches['path'],
            }

    def _finalize(self, score):
        self.proxies = dict(
            (module, score._modules[module].score_webassets_proxy())
            for module in self.modules)

    def _generate_html_tag(self, module, *paths):
        if not paths:
            proxy = self._get_proxy(module)
            regex = re.compile(r'(^|/)_')
            paths = list(sorted(path for path in proxy.iter_paths()
                                if not regex.search(path)))
            if not paths:
                return ''
        else:
            proxy = self._get_proxy(module, *paths)
        if self.tpl_autobundle:
            url = self.http.url(None, 'score.webassets', module, paths)
            return proxy.render_url(url)
        else:
            parts = []
            for path in paths:
                url = self.http.url(None, 'score.webassets', module, [path])
                parts.append(proxy.render_url(url))
            return ''.join(parts)

    def get_bundle_hash(self, module, paths):
        if not paths:
            raise ValueError('No paths provided')
        if isinstance(self.freeze, str):
            return self.freeze
        elif self.freeze:
            key = '%s/bundle\0%s' % (module, '\0'.join(paths))
            try:
                return self._frozen_versions[key]
            except KeyError:
                proxy = self._get_proxy(module, *paths)
                hash_ = proxy.bundle_hash(paths)
                self._frozen_versions[key] = hash_
                return hash_
        proxy = self._get_proxy(module, *paths)
        return proxy.bundle_hash(paths)

    def get_bundle_name(self, module, paths):
        if not paths:
            raise ValueError('No paths provided')
        return hashlib.sha256('\0'.join(sorted(paths)).encode('UTF-8'))\
            .hexdigest()

    def get_bundle_url(self, module, paths):
        if not paths:
            raise ValueError('No paths provided')
        if len(paths) == 1:
            return self.get_asset_url(module, paths[0])
        if not self.rootdir:
            raise RuntimeError(
                'Cannot generate bundle url: no rootdir configured')
        bundle_name = self.get_bundle_name(module, paths)
        bundle_hash = self.get_bundle_hash(module, paths)
        file = os.path.join(self.rootdir, module, bundle_name, bundle_hash)
        proxy = self._get_proxy(module, *paths)
        if not os.path.exists(file):
            os.makedirs(os.path.dirname(file), exist_ok=True)
            with open(file, 'w') as fp:
                fp.write(proxy.bundle_mimetype(paths))
                fp.write('\n')
                fp.write(proxy.create_bundle(paths))
        url = '/%s/__bundle_%s__' % (module, bundle_name,)
        if bundle_hash:
            url += '?_v=' + bundle_hash
        return url

    def get_bundle_content(self, module, *paths):
        proxy = self._get_proxy(module, *paths)
        return proxy.create_bundle(paths)

    def get_asset_hash(self, module, path):
        if isinstance(self.freeze, str):
            return self.freeze
        elif self.freeze:
            key = '%s/%s' % (module, path)
            try:
                return self._frozen_versions[key]
            except KeyError:
                proxy = self._get_proxy(module, path)
                hash_ = proxy.hash(path)
                self._frozen_versions[key] = hash_
                return hash_
        else:
            proxy = self._get_proxy(module, path)
            return proxy.hash(path)

    def get_asset_url(self, module, path):
        proxy = self._get_proxy(module, path)
        url = '/%s/%s' % (module, path)
        hash_ = self.get_asset_hash(module, path)
        if hash_:
            url += '?_v=' + hash_
            if self.rootdir:
                file = os.path.join(self.rootdir, module, path, hash_)
                if not os.path.exists(file):
                    os.makedirs(os.path.dirname(file), exist_ok=True)
                    with open(file, 'w') as fp:
                        fp.write(proxy.mimetype(path))
                        fp.write('\n')
                        fp.write(proxy.render(path))
        return url

    def get_asset_content(self, module, path):
        proxy = self._get_proxy(module, path)
        return proxy.render(path)

    def get_asset_mimetype(self, module, path):
        proxy = self._get_proxy(module, path)
        return proxy.mimetype(path)

    def get_request_response(self, request):
        try:
            module, path = request.path.lstrip('/').split('/', maxsplit=1)
            if path.startswith('__bundle_') and path.endswith('__'):
                def loader(hash_=None):
                    name = path[len('__bundle_'):-2]
                    file = os.path.join(self.rootdir, module, name, hash_)
                    try:
                        content = open(file).read()
                    except FileNotFoundError:
                        raise AssetNotFound(module,
                                            'bundle(%s)@%s' % (name, hash_))
                    return content.split('\n', maxsplit=1)
            else:
                def loader(hash_=None):
                    if hash_ and self.rootdir:
                        file = os.path.join(self.rootdir, module, path, hash_)
                        try:
                            content = open(file).read()
                        except FileNotFoundError:
                            raise AssetNotFound(module, '%s@%s' % (path, hash_))
                        return content.split('\n', maxsplit=1)
                    proxy = self._get_proxy(module, path)
                    return proxy.mimetype(path), proxy.render(path)
            return self._get_common_response(request, module, path, loader)
        except AssetNotFound:
            return 404

    def _get_common_response(self, request, module, path, loader):
        if '_v' in request.GET:
            can_send_304 = (
                'If-None-Match' in request.headers or
                'If-Modified-Since' in request.headers)
            # it really doesn't matter what the values of these headers are,
            # they merely indicate that the resource was requested by the client
            # earlier and it is now checking for changes. but since assets with
            # hashes are immutable, we can always respond with 304.
            if can_send_304:
                return 304
            hash_ = request.GET['_v']
            try:
                mimetype, body = loader(hash_)
            except FileNotFoundError:
                raise AssetNotFound(module, path)
            return ({
                'Content-Type': mimetype,
                'Cache-Control': 'max-age=' + str(60 * 60 * 24 * 30 * 12),
                'Etag': hash_,
                'Last-Modified': email.utils.formatdate(),
            }, body)
        if 'If-Modified-Since' in request.headers and self.rootdir:
            t = time.mktime(email.utils.parsedate(
                request.headers['If-Modified-Since']))
            folder = os.path.join(self.rootdir, module, path)
            try:
                if not any(os.path.getmtime(f) > t for f in os.listdir(folder)):
                    # there aren't any newer files in this folder
                    return 304
            except FileNotFoundError:
                # folder does not exist, ignore
                pass
        hash_ = request.GET.get('_v', None)
        mimetype, body = loader(hash_)
        headers = {
            'Content-Type': mimetype,
            'Last-Modified': email.utils.formatdate(),
        }
        if hash_:
            headers['Etag'] = hash_
        return (headers, body)

    def _get_proxy(self, module, *paths):
        if module not in self.modules:
            path = '???'
            if paths:
                path = paths[0]
            raise AssetNotFound(module, path)
        proxy = self.proxies[module]
        for path in paths:
            if not proxy.validate_path(path):
                raise AssetNotFound(module, path)
        return proxy


class AssetNotFound(Exception):
    """
    Thrown when an asset was requested, but not found. Web applications might
    want to return the HTTP status code 404 in this case.

    Assets are uniquely identified by the combination of a :term:`category
    <asset category>` string and a :term:`path <asset path>`.
    """

    def __init__(self, module, path):
        self.module = module
        self.path = path
        super().__init__('/%s/%s' % (module, path))
