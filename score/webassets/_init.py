# Copyright © 2015 STRG.AT GmbH, Vienna, Austria
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

import email.utils
import os
import hashlib
from score.init import (
    init_object, init_cache_folder, ConfiguredModule, parse_bool)
from .versioning import Netfs as NetfsVersionManager
import time
from webob.exc import HTTPNotFound

defaults = {
    'cachedir': None,
    'versionmanager': 'score.webassets.versioning.Dummy',
    'netfs': True,
}


def init(confdict, http, netfs=None):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`cachedir` :default:`None`
        A writable folder that will be used to cache intermediate values. This
        value is mostly unused in this module, but the initialized value can be
        used by other modules. The :mod:`css module <score.css>`, for example,
        will create a sub-folder beneath this folder, if it was initialized
        without an explicit `cachedir` of its own.

    :confkey:`versionmanager` :default:`score.webassets.versioning.Dummy`
        The :class:`VersionManager` to use. This value will be converted to an
        object using :func:`score.init.init_object`.

        See the :mod:`package description <score.webassets.versioning>` for
        available implementations.

    :confkey:`netfs` :default:`True`
        The initializer will upload all webassets to a :mod:`score.netfs`
        server, if one was configured. You can disable this feature by passing a
        `False` value here
    """
    conf = dict(defaults.items())
    conf.update(confdict)
    if conf['cachedir']:
        init_cache_folder(conf, 'cachedir', autopurge=True)
    versionmanager = init_object(conf, 'versionmanager')
    if netfs and parse_bool(conf['netfs']):
        versionmanager = NetfsVersionManager(versionmanager, netfs)
    def assetnotfound(ctx, exception):
        raise HTTPNotFound()
    http.exception_handlers[AssetNotFound] = assetnotfound
    return ConfiguredWebassetsModule(conf['cachedir'], versionmanager)


class ConfiguredWebassetsModule(ConfiguredModule):
    """
    This module's :class:`configuration class
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, cachedir, versionmanager):
        super().__init__(__package__)
        self.cachedir = cachedir
        self.versionmanager = versionmanager

    def handle_request(self, ctx, category, path):
        """
        Tries to populate the http response in the given context with the
        cached version of an asset as described in the introduction to
        :mod:`score.webassets.versioning`. The asset is specified as a
        combination of :term:`category <asset category>` and :term:`path
        <asset path>`, as usual.

        This function will handle the headers `If-None-Match` and
        `If-Modified-Since` with a status code of 304 if the according asset
        version exists and respond with the cached content if the request
        provides a :term:`version string` via the GET value ``_v``.

        If this function manages to populate the response object of the
        *request* with the appropriate values for sending to the client, it
        will return `True`. If this function cannot find the correct asset
        version, or the client did not send any version information, it will
        not populate the response and return `False`.
        """
        if 'If-None-Match' in ctx.http.request.headers:
            hash = ctx.http.request.headers['If-None-Match'].strip('"')
            cachefile = self._cache_file(category, path, hash)
            if os.path.isfile(cachefile):
                ctx.http.response.status = 304
                return True
        if 'If-Modified-Since' in ctx.http.request.headers:
            t = time.mktime(email.utils.parsedate(
                ctx.http.request.headers['If-Modified-Since']))
            folder = os.path.join(self.cachedir, category, path)
            for f in os.listdir(folder):
                if os.path.getmtime(f) > t:
                    break
            else:
                ctx.http.response.status = 304
                return True
        if '_v' in ctx.http.request.GET:
            hash = ctx.http.request.GET['_v']
            result = self.versionmanager.load(category, path, hash)
            if result:
                body, age = result
                ctx.http.response.body = body
                ctx.http.response.cache_control.max_age = \
                    str(60 * 60 * 24 * 30 * 12)  # ~1 year
                ctx.http.response.age = age
                ctx.http.response.etag = hash
                return True
        return False


class AssetNotFound(Exception):
    """
    Thrown when an asset was requested, but not found. Web applications might
    want to return the HTTP status code 404 in this case.

    Assets are uniquely identified by the combination of a :term:`category
    <asset category>` string and a :term:`path <asset path>`.
    """

    def __init__(self, category, path):
        self.category = category
        self.path = path

    def __str__(self):
        return '%s(%s)' % (self.path, self.category)


class VirtualAssets:
    """
    A Container for :term:`virtual assets <virtual asset>`, i.e. assets that
    have a :term:`path <asset path>`, but are not actually files. Virtual
    assets are instead registered with a generator function that generates
    its content. To be precise, each virtual asset consists of the following
    properties:

    - an :term:`asset path`,
    - a callback function that generates its content and
    - a hashing function that will generate the same string, as long as the
      content of the asset stays the same.

    The most convenient way to use this class is via an automatic
    :meth:`.decorator`.
    """

    def __init__(self):
        self.assets = {}

    def register(self, path, callback, hasher=None):
        """
        Registers a new :term:`virtual asset` beneath the provided *path*. The
        *callback* will be used to generate the content of the asset.

        The optional *hasher* callback must return the same string as long as
        the *callback* generates the same content. If no *hasher* is provided,
        one will be generated automatically that hashes the generated content.
        """
        assert path not in self.assets
        if hasher is None:
            def hasher():
                result = callback()
                if isinstance(result, str):
                    result = result.encode('UTF-8')
                sha = hashlib.sha256()
                sha.update(result)
                return sha.hexdigest()
        self.assets[path] = (callback, hasher)

    def paths(self):
        """
        Returns an iterator of all registered asset paths.
        """
        return self.assets.keys()

    def render(self, path):
        """
        Invokes the callback of the asset with given *path* and returns its
        result.
        """
        return self.assets[path][0]()

    def hash(self, path):
        """
        Invokes the hashing function of the asset with given *path* and
        returns its result.
        """
        return self.assets[path][1]()

    def decorator(self, suffix):
        """
        Creates a decorator that can be used to register callbacks
        conveniently:

        >>> v = VirtualAssets()
        >>> virtualcss = v.decorator('css')
        >>> @virtualcss
        ... def textcolor():
        ...   return 'body {color: black}'
        ...
        >>> @virtualcss('background-color.css')
        ... def bgcolor():
        ...   return 'body {background-color: white}'
        ...
        >>> def hasher():
        ...   try:
        ...     return os.path.getmtime('parrot.png')
        ...   except FileNotFoundError:
        ...     return 'dead'
        ...
        >>> @virtualcss('parrot.css', hasher)
        ... def parrot():
        ...   url = 'parrot.png?_=%s' % hasher()
        ...   return '.parrot {background-image: url(%s)}' % url
        ...
        >>> list(v.paths())
        ['textcolor.css', 'background-color.css', 'parrot.css']
        """
        class Decorator:

            def __new__(cls, *args):
                if callable(args[0]):
                    name = '%s.%s' % (args[0].__name__, suffix)
                    self.register(name, args[0])
                    return args[0]
                o = super().__new__(cls)
                o.name = args[0]
                o.hasher = None
                if len(args) > 1:
                    o.hasher = args[1]
                return o

            def __call__(o, callback):
                self.register(o.name, callback, o.hasher)

        return Decorator
