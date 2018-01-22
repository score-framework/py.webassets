# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
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
import xxhash
from collections import namedtuple

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

    :confkey:`rootdir` :confdefault:`None`
        The folder where this module will store the bundled assets.

    :confkey:`modules` :confdefault:`[]`
        A list of configured score modules to retrieve proxy objects from. The
        configured modules listed here must all expose a
        ``score_webassets_proxy()`` method, that returns a
        :class:`WebassetsProxy` object.

    :confkey:`freeze` :confdefault:`False`
        Option for speeding up :term:`asset hash` calculations.

        See :ref:`webassets_freezing` for valid values.

    :confkey:`tpl.autobundle` :confdefault:`False`
        Whether the webassets_* functions registered with :mod:`score.tpl`
        should provide :term:`bundles <asset bundle>` instead of separate files.
        This should be set to `True` on deployment systems to speed up web page
        rendering.

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
            'webassets_content', self._generate_html_content, escape=False)

    def _register_http_route(self):
        @self.http.newroute('score.webassets', '/_assets/{module}/{path>.*}')
        def webassets(ctx, module, paths):
            request = ctx.http.request
            status, headers, body = self.get_request_response(Request(
                '/' + request.path.lstrip('/').split('/', maxsplit=1)[1],
                request.GET,
                request.headers,
            ))
            ctx.http.response.status = status
            for header, value in headers.items():
                ctx.http.response.headers[header] = value
            ctx.http.response.text = body

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
            if self.tpl_autobundle:
                paths = self._get_proxy_default_bundle_paths(proxy)
            else:
                paths = self._get_proxy_default_paths(proxy)
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

    def _generate_html_content(self, module, *paths):
        if not paths:
            paths = None
        return self.get_bundle_content(module, paths)

    def _get_proxy_default_paths(self, proxy):
        if not self.freeze:
            return list(proxy.iter_default_paths())
        if not hasattr(self, '_proxy_default_paths'):
            self._proxy_default_paths = {}
        if proxy not in self._proxy_default_paths:
            iterator = proxy.iter_default_paths()
            self._proxy_default_paths[proxy] = list(iterator)
        return self._proxy_default_paths[proxy]

    def _get_proxy_default_bundle_paths(self, proxy):
        if not self.freeze:
            return list(proxy.iter_default_bundle_paths())
        if not hasattr(self, '_proxy_default_bundle_paths'):
            self._proxy_default_bundle_paths = {}
        if proxy not in self._proxy_default_bundle_paths:
            iterator = proxy.iter_default_bundle_paths()
            self._proxy_default_bundle_paths[proxy] = list(iterator)
        return self._proxy_default_bundle_paths[proxy]

    def get_asset_content(self, module, path):
        """
        Returns the content of the asset identified my its *module* and *path*.
        """
        proxy = self._get_proxy(module, path)
        return proxy.render(path)

    def get_asset_mimetype(self, module, path):
        """
        Returns the mime type of the asset identified my its *module* and
        *path*.
        """
        proxy = self._get_proxy(module, path)
        return proxy.mimetype(path)

    def get_asset_hash(self, module, path):
        """
        Provides the :term:`hash <asset hash>` of the asset identified my its
        *module* and *path*.
        """
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
        """
        Returns the relative URL to the asset identified by its *module* and
        *path*, that this module can resolve via :meth:`get_request_response`.

        You won't need this function, if you're using :mod:`score.http`. But if
        your means of deployment is different, you will want to create URLs to
        your assets using this function. It will look something like this::

            /css/reset.css?_v=0b2931cc6255c72e

        This should be rewritten to something you can detect in your
        application::

            /_score_webassets/css/reset.css?_v=0b2931cc6255c72e

        Whenever a URL starting with your custom prefix is requested, you can
        pass the modified :class:`Request` with the original URL to
        :meth:`get_request_response`:

        .. code-block:: python

            status, headers, body = webassets.get_request_response(Request(
                '/css/reset.css',
                {'_v': '0b2931cc6255c72e'},
                {'Accept-Encoding': 'gzip,deflate',
                 'Referer': ... }
            ))
        """
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

    def get_bundle_name(self, module, paths=None):
        """
        Provides a unique name for a :term:`bundle <asset bundle>` consisting of
        assets found in given *module* and given *paths*. Will use the module's
        :meth:`default paths <WebassetsProxy.iter_default_bundle_paths>`, if the
        latter is omitted.

        This feature is used internally for storing different bundles inside the
        same folder, for example.
        """
        if paths is None:
            proxy = self._get_proxy(module)
            paths = self._get_proxy_default_bundle_paths(proxy)
        elif not paths:
            raise ValueError('No paths provided')
        return xxhash.xxh64('\0'.join(sorted(paths)).encode('UTF-8'))\
            .hexdigest()

    def get_bundle_hash(self, module, paths=None):
        """
        Provides the :term:`hash <asset hash>` of a :term:`bundle <asset
        bundle>` consisting of assets found in given *module* and given *paths*.
        Will use the module's :meth:`default paths
        <WebassetsProxy.iter_default_bundle_paths>`, if the latter is omitted.
        """
        if paths is None:
            proxy = self._get_proxy(module)
            paths = self._get_proxy_default_bundle_paths(proxy)
        elif not paths:
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

    def get_bundle_content(self, module, paths=None):
        """
        Returns the content of requested :term:`bundle <asset bundle>`. The
        *module* name is required and will create a bundle with module's
        :meth:`default paths <WebassetsProxy.iter_default_bundle_paths>`. It is
        also possible to create a bundle with a specific list of :term:`asset
        paths <asset path>`.
        """
        if paths is None:
            proxy = self._get_proxy(module)
            paths = list(proxy.iter_default_bundle_paths())
        elif not paths:
            raise ValueError('No paths provided')
        else:
            proxy = self._get_proxy(module, *paths)
        return proxy.create_bundle(paths)

    def get_bundle_url(self, module, paths=None):
        """
        Returns the relative URL to given :term:`bundle <asset bundle>`, that
        this module can resolve via :meth:`get_request_response`. The *module*
        name is required and will create a bundle with module's :meth:`default
        paths <WebassetsProxy.iter_default_bundle_paths>`. It is also possible
        to create a bundle with a specific list of :term:`asset paths <asset
        path>`.

        See :meth:`get_asset_url` for example usage.
        """
        if paths is None:
            proxy = self._get_proxy(module)
            paths = self._get_proxy_default_bundle_paths(proxy)
        elif not paths:
            raise ValueError('No paths provided')
        else:
            proxy = self._get_proxy(module, *paths)
        if len(paths) == 1:
            return self.get_asset_url(module, paths[0])
        if not self.rootdir:
            raise RuntimeError(
                'Cannot generate bundle url: no rootdir configured')
        bundle_name = self.get_bundle_name(module, paths)
        bundle_hash = self.get_bundle_hash(module, paths)
        file = os.path.join(self.rootdir, module, bundle_name, bundle_hash)
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

    def get_request_response(self, request):
        """
        Provides the most efficient response to an HTTP :class:`Request` to
        obtain an asset. The return value is 3-tuple ``(status, headers, body)``
        containing an HTTP status code, a `dict` of HTTP headers and the
        response body.
        The *headers* list in the latter case is a `dict` mapping header names
        to their values, whereas the *body* is just a string. Note that none of
        the return values are formatted in any way. They will need to be
        properly encoded (which should happen automatically in most frameworks).
        """
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
            return 404, {}, ''

    def _get_common_response(self, request, module, path, loader):
        headers = dict((key.lower(), value)
                       for key, value in request.headers.items())
        if '_v' in request.GET:
            can_send_304 = (
                'if-none-match' in headers or
                'if-modified-since' in headers)
            # it really doesn't matter what the values of these headers are,
            # they merely indicate that the resource was requested by the client
            # earlier and it is now checking for changes. but since assets with
            # hashes are immutable, we can always respond with 304.
            if can_send_304:
                return 304, {}, ''
            hash_ = request.GET['_v']
            try:
                mimetype, body = loader(hash_)
            except FileNotFoundError:
                raise AssetNotFound(module, path)
            return 200, {
                'Content-Type': mimetype,
                'Cache-Control': 'max-age=' + str(60 * 60 * 24 * 30 * 12),
                'Etag': hash_,
                'Last-Modified': email.utils.formatdate(),
            }, body
        if 'if-modified-since' in headers and self.rootdir:
            t = time.mktime(email.utils.parsedate(
                headers['if-modified-since']))
            folder = os.path.join(self.rootdir, module, path)
            try:
                if not any(os.path.getmtime(f) > t for f in os.listdir(folder)):
                    # there aren't any newer files in this folder
                    return 304, {}, ''
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
        return 200, headers, body

    def _get_proxy(self, module, *paths):
        if module not in self.modules:
            path = '???'
            if paths:
                path = paths[0]
            raise AssetNotFound(module, path)
        proxy = self.proxies[module]
        if self.freeze:
            if not hasattr(self, '_proxy_valid_paths'):
                self._proxy_valid_paths = {}
            if proxy not in self._proxy_valid_paths:
                self._proxy_valid_paths[proxy] = []
            valid_paths = self._proxy_valid_paths[proxy]
            for path in paths:
                if path in valid_paths:
                    continue
                if not proxy.validate_path(path):
                    raise AssetNotFound(module, path)
                valid_paths.append(path)
        else:
            for path in paths:
                if not proxy.validate_path(path):
                    raise AssetNotFound(module, path)
        return proxy


class AssetNotFound(Exception):
    """
    Thrown when an asset was requested, but not found. Web applications might
    want to return the HTTP status code 404 in this case.

    Assets are uniquely identified by the combination of their :term:`module
    <asset module>` name and a :term:`path <asset path>`.
    """

    def __init__(self, module, path):
        self.module = module
        self.path = path
        super().__init__('/%s/%s' % (module, path))
