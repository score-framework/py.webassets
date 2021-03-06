# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
# Copyright © 2018-2020 Necdet Can Ateşman, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in
# the file named COPYING.LESSER.txt.
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
# the discretion of STRG.AT GmbH also the competent court, in whose district
# the Licensee has his registered seat, an establishment or assets.

import abc
from score.tpl import TemplateNotFound
import xxhash
import re


class WebassetsProxy(abc.ABC):
    """
    A proxy object defining the behaviour of a type of web asset.
    """

    @abc.abstractmethod
    def iter_default_paths(self):
        """
        Provide a generator iterating over the paths, that should be used if no
        explicit path list was given.
        """

    def iter_default_bundle_paths(self):
        """
        Provide a generator iterating over the paths, that should be used for a
        bundle if no explicit path list was given.
        """
        return self.iter_default_paths()

    @abc.abstractmethod
    def validate_path(self, path):
        """
        Test if a *path* is valid, i.e. if it can be passed to :meth:`render`.
        """

    @abc.abstractmethod
    def hash(self, path):
        """
        Returns a hash for *path*, that will change whenever the rendered
        content of the asset changes.
        """

    @abc.abstractmethod
    def render(self, path):
        """
        Provides the content of the asset with given *path*.
        """

    @abc.abstractmethod
    def mimetype(self, path):
        """
        Returns the mime type of the asset with given *path*.
        """

    @abc.abstractmethod
    def render_url(self, url):
        """
        Returns the string to embed in an HTML document to load given *url*.
        This might be a <link> tag for css assets, or a <script> tag for
        javascript assets.
        """

    @abc.abstractmethod
    def create_bundle(self, paths):
        """
        Returns a string containing the contents of multiple assets identified
        by their given *paths*.
        """

    def bundle_hash(self, paths):
        """
        Provides the hash of the bundle with given *paths*.
        """
        hash = xxhash.xxh64()
        for path in sorted(paths):
            part = self.hash(path)
            if part:
                hash.update(part.encode('UTF-8'))
            hash.update(b'\0')
        return hash.hexdigest()

    @abc.abstractmethod
    def bundle_mimetype(self, paths):
        """
        Returns the mime type of the bundle consisting of given *paths*.
        """


class TemplateWebassetsProxy(WebassetsProxy):
    """
    A type of :class:`WebassetsProxy` that treats templates like assets. It
    accepts a configured :mod:`score.tpl` module and a mime type string and
    will provide almost all templates, that the tpl module knows of, as assets.
    If the tpl module knows of css files, for example, this class can be used
    to provide these css files as assets.

    The default path list--as returned by :meth:`iter_default_paths
    <WebassetsProxy.iter_default_paths>`--will omit all files starting with
    underscore and all files inside folders that start with an underscore.
    Assuming the tpl module lists the following template paths ...

    ::

        banana.css
        _orange.css
        fresh/
            banana.css
            _apple.css
        _old/
            pear.css
            passion-fruit.css

    ... only ``banana.css`` and ``fresh/banana.css`` will be returned by
    :meth:`iter_default_paths <WebassetsProxy.iter_default_paths>`.
    """

    def __init__(self, tpl, mimetype):
        self.tpl = tpl
        self._mimetype = mimetype
        self.postprocessors_hash = xxhash.xxh64()
        postprocessors = tpl.filetypes[self._mimetype].postprocessors
        # TODO: the next line just includes the number of postprocessors, it
        # should somehow base the hash on the postprocessor instances, not just
        # the sheer amount
        self.postprocessors_hash.update(bytes([len(postprocessors)]))

    def iter_default_paths(self):
        hidden_regex = re.compile(r'(^|/)_')
        yield from sorted(
            path
            for path in self.tpl.iter_paths(mimetype=self._mimetype)
            if not hidden_regex.search(path))

    def validate_path(self, path):
        try:
            return self.tpl.mimetype(path) == self._mimetype
        except TemplateNotFound:
            return False

    def bundle_hash(self, paths):
        """
        Provides the hash of the bundle with given *paths*.
        """
        hash = self.postprocessors_hash.copy()
        for path in sorted(paths):
            hash.update(self.tpl.hash(path))
            hash.update(b'\0')
        return hash.hexdigest()

    def hash(self, path):
        hash = self.postprocessors_hash.copy()
        hash.update(self.tpl.hash(path))
        return hash.hexdigest()

    def render(self, path):
        try:
            return self.tpl.render(path)
        except TemplateNotFound:
            from ._init import AssetNotFound
            # TODO:  The following call should be replaced.
            # The first parameter to AssetNotFound should actually be the
            # module name, but we do not know have that information at this
            # point. Fix this when there is a good solution.
            raise AssetNotFound('???', path)

    def mimetype(self, path):
        return self._mimetype

    def bundle_mimetype(self, paths):
        return self._mimetype

    @abc.abstractmethod
    def render_url(self, url):
        pass

    @abc.abstractmethod
    def create_bundle(self, paths):
        pass
