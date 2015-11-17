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

"""
This package :ref:`integrates <framework_integration>` the module with
pyramid.

It registers a handler for the exception :exc:`AssetNotFound
<score.webassets.AssetNotFound>`, which returns the HTTP status code
``404 - Not found``.
"""

import os
from pyramid.request import Request
import score.webassets
import time


def assetnotfound(exc, request):
    """
    Returns an HTTP response with status code 404. This method is registered
    in the pyramid-specific :func:`init` function.
    """
    request.response.status = 404
    return request.response


def init(confdict, configurator, netfs_conf=None):
    """
    Performs the following steps:

    - Wraps the versionmanager in a PyramidVersionManager object to provide
      additional features.
    - Generates a dummy pyramid request (see below) and adds it to the
      configuration object as ``dummy_request``.
    - Registers the view assetnotfound for a handler to the
      :exc:`AssetNotFound` Exception.

    In addition to the configuration keys of the generic :func:`initializer
    function <score.webassets.init>`, this function additionally handles the
    following configuration keys:

    :confkey:`dummy_request` :faint:`[optional]`
        A pyramid request that can will be used to create URLs to assets. If
        this value is missing, a new :class:`DummyRequest` will be created
        automatically.
    """
    webconf = score.webassets.init(confdict, netfs_conf)
    webconf.versionmanager = PyramidVersionManager(webconf.versionmanager)
    if 'dummy_request' in confdict:
        assert isinstance(confdict['dummy_request'], Request)
        webconf.dummy_request = confdict['dummy_request']
    else:
        webconf.dummy_request = DummyRequest.blank('/', base_url='')
    webconf.dummy_request.registry = configurator.registry
    configurator.add_view(assetnotfound, context=score.webassets.AssetNotFound)
    return webconf


class DummyRequest(Request):
    """
    Derives from :class:`pyramid.request.Request` to override url generating
    functions. By default, this class will omit the schema/domain of the url,
    making all URLs relative to the current host. This behaviour can be changed
    by setting the attribute ``app_url`` on the request object:

    >>> d = DummyRequest.blank('/')
    >>> d.route_url('somewhere')
    /somewhere
    >>> d.app_url = 'http://foo.bar'
    >>> d.route_url('somewhere')
    http://foo.bar/somewhere
    """

    def __init__(self, *args, **kwargs):
        self.app_url = ''
        Request.__init__(self, *args, **kwargs)

    def route_url(self, route_name, *elements, **kw):
        if '_app_url' not in kw:
            kw['_app_url'] = self.app_url
        return super().route_url(route_name, *elements, **kw)


class PyramidVersionManager:
    """
    A wrapper for other :class:`VersionManagers <VersionManager>` that adds a
    function for handling version hashes in the request url.
    """

    def __init__(self, versionmanager):
        self.versionmanager = versionmanager

    def __getattr__(self, attr):
        return getattr(self.versionmanager, attr)

    def handle_pyramid_request(self, category, path, request):
        """
        Tries to populate the :attr:`response
        <pyramid.request.Request.response>` of the pyramid request with the
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
        if 'If-None-Match' in request.headers:
            hash = request.headers['If-None-Match'].strip('"')
            cachefile = self._cache_file(category, path, hash)
            if os.path.isfile(cachefile):
                request.response.status = 304
                return request.response
        if 'If-Modified-Since' in request.headers:
            import email.utils as eut
            t = time.mktime(eut.parsedate(request.headers['If-Modified-Since']))
            folder = os.path.join(self.cachedir, category, path)
            for f in os.listdir(folder):
                if os.path.getmtime(f) > t:
                    modified = True
                    break
            if not modified:
                request.response.status = 304
                return True
        if '_v' in request.GET:
            hash = request.GET['_v']
            result = self.versionmanager.load(category, path, hash)
            if result:
                body, age = result
                request.response.body = body
                request.response.max_age = str(60 * 60 * 24 * 30 * 12)  # 1 year
                request.response.age = age
                request.response.etag = hash
                return True
        return False
