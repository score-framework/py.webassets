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

from score.init import (
    init_object, init_cache_folder, ConfiguredModule, parse_bool)
from .versioning import Netfs as NetfsVersionManager
from webob.exc import HTTPNotFound

defaults = {
    'cachedir': None,
    'versionmanager': 'score.webassets.versioning.Dummy',
    'netfs': True,
}


def init(confdict, http=None, netfs=None):
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
    if http:
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
