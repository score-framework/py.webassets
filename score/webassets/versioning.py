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
This package allows generating hashes for web assets. These hashes should be
attached to the URLs pointing to those assets. They can then be used to
reduce network traffic by sending smaller HTTP responses (i.e. 304 - not
modified) or sending the response directly from the configured cache folder.
"""
import fcntl
import hashlib
import io
import logging
import os
import re
import shutil
import textwrap
import time


log = logging.getLogger(__name__)


class VersionManager:
    """
    A handler for asset versioning via :term:`version strings
    <version string>`. The :func:`module initialization <score.webassets.init>`
    will instantiate an object of this class or a sub-class.

    The constructor argument *folder* must point to a valid path on the file
    system, which should **not** be regarded as a cache! Instances of this
    class will write files into this folder that will be needed during later
    HTTP requests.

    The only two relevant functions for the usage of this class are
    :meth:`.store` and :meth:`.load`.
    """

    hashregex = re.compile('^[0-9A-Fa-f]+$')

    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        warning = os.path.join(folder, 'README.txt')
        open(warning, 'w').write(textwrap.dedent(
            'This folder is managed by a VersionManager '
            'of the python module score.webassets.\n\n'
            'Do not alter/delete any files!'
        ).strip())

    def store(self, category, path, hashers, content_generator):
        """
        Stores a version of an asset. The asset is specified as a 2-tuple of
        :term:`category <asset category>` and :term:`path <asset path>`,
        as usual.

        The hash functions, provided as parameter *hashers*, need to generate
        the exact same hashes as long as the content of this asset remains the
        same. If the *hashers* generate a previously generated hash, the
        function will return early. Otherwise the *content_generator* will be
        used to store the content of this version of the asset. That content
        will then be returned in consecutive calls to :meth:`.load`.

        See the :mod:`pyramid <score.webassets.pyramid>` package for an example
        use of this function.
        """
        if not hasattr(hashers, '__iter__'):
            hashers = hashers,
        hashes = []
        for hasher in hashers:
            hash = hasher()
            if hash:
                hashes.append(hash)
        if not len(hashes):
            return
        hash = hashlib.sha256(''.join(hashes).encode('UTF-8')).hexdigest()
        cachefile = self._cache_file(category, path, hash)
        if not os.path.isfile(cachefile):
            os.makedirs(os.path.dirname(cachefile), exist_ok=True)
            content = content_generator()
            open(cachefile, 'wb').write(content)
        return hash

    def load(self, category, path, hash):
        """
        Loads a previously stored hash of an asset described by
        :term:`category <asset category>` and :term:`path <asset path>`. This
        function will return a 2-tuple consisting of the content
        :term:`version <version string>` (denoted by the *hash*) and the age
        of the version.

        If the requested :term:`version <version string>` does not exist, this
        function will return `None` instead.

        See the :mod:`pyramid <score.webassets.pyramid>` package for an example
        use of this function.
        """
        cachefile = self._cache_file(category, path, hash)
        if not os.path.isfile(cachefile):
            return None
        content = open(cachefile, 'rb').read()
        return (content, time.time() - os.path.getmtime(cachefile))

    def create_file_hasher(self, files):
        """
        Returns a function that will generate a hash using the moste recent
        modification time in the *files* list.
        """
        if isinstance(files, str) or not hasattr(files, '__iter__'):
            files = files,
        if not len(files):
            return lambda: None
        return lambda: str(max(os.path.getmtime(f) for f in files))

    def _cache_file(self, category, path, hash):
        """
        Returns the file on the file system storing the content version of an
        asset.
        """
        assert VersionManager.hashregex.match(hash), "Invalid hash: %s" % hash
        return os.path.join(self.folder, category, path, hash)


class Dummy(VersionManager):
    """
    A Passthrough VersionManager that has no actual implementation. This class
    is the default VersionManager, if no other was configured.
    """

    def __init__(self, *args, **kwargs):
        pass

    def store(self, *args, **kwargs):
        pass

    def load(self, *args, **kwargs):
        pass


class Mercurial(VersionManager):
    """
    A version manager that ignores provided hashers and just uses the current
    changeset hashes of provided *repositories* folders.
    """

    def __init__(self, folder, repositories):
        super().__init__(folder)
        self.hashers = list(map(self.create_repo_hasher, repositories))

    def store(self, category, path, hashers, content_generator):
        # ignore *hashers*, use *self.hashers* instead
        return super().store(category, path, self.hashers, content_generator)

    def create_repo_hasher(self, repository):
        """
        Creates a hashing function for given mercurial *repository* folder.
        """
        def hasher():
            # the old implementation was using an external call to `hg`, which
            # was quite slow. now reading repository data directly, below.
            #   args = ['hg', '--debug', 'identify', '--id']
            #   process = subprocess.Popen(
            #       args,
            #       cwd=os.path.abspath(repository),
            #       stdin=subprocess.PIPE,
            #       stdout=subprocess.PIPE,
            #       stderr=subprocess.PIPE)
            #   stdout, stderr = process.communicate()
            #   if stderr:
            #       log.error('Error retrieving repository hash: %s' % stderr)
            #       return None
            #   return stdout[:-1]
            file = open(os.path.join(repository, '.hg', 'dirstate'), 'rb')
            bin = file.read(20)
            return hex(int.from_bytes(bin, 'big'))
        return hasher


class Netfs:
    """
    Wraps an existing VersionManager and uploads all files to :mod:`netfs
    <score.netfs>` to make asset versions available to peers.
    """

    # TODO: this is a bit of a mess. it should rather be implemented as some
    # kind of "backend" to a VersionManager.

    @staticmethod
    def _netfspath(category, path, hash):
        return 'webassets/%s/%s/%s' % (category, path, hash)

    def __init__(self, versionmanager, netfs):
        self.netfs = netfs
        self.versionmanager = versionmanager

    def __getattr__(self, attr):
        return getattr(self.versionmanager, attr)

    def store(self, category, path, hashers, content_generator):
        if not hasattr(hashers, '__iter__'):
            hashers = hashers,
        hashes = []
        for hasher in hashers:
            hash = hasher()
            if hash:
                hashes.append(hash)
        if not len(hashes):
            return
        hash = hashlib.sha256(''.join(hashes).encode('UTF-8')).hexdigest()
        cachepath = self._cache_file(category, path, hash)
        if os.path.isfile(cachepath):
            return hash
        os.makedirs(os.path.dirname(cachepath), exist_ok=True)
        tmppath = cachepath + '.tmp'
        from score.netfs import DownloadFailed
        try:
            tmpfile = open(tmppath, 'wb')
            connection = self.netfs.connect()
            fcntl.flock(tmpfile, fcntl.LOCK_EX)
            if os.path.exists(cachepath):
                # another process downloaded the file
                return hash
            time = connection.download(self._netfspath(category, path, hash),
                                       tmpfile)
            os.utime(tmppath, (time, time))
            shutil.move(tmppath, cachepath)
        except DownloadFailed:
            # generate content and upload
            content = content_generator()
            open(cachepath, 'wb').write(content)
            netfspath = self._netfspath(category, path, hash)
            connection.upload(netfspath, io.BytesIO(content))
            connection.commit()
            return hash
        finally:
            fcntl.flock(tmpfile, fcntl.LOCK_UN)
            tmpfile.close()
            os.unlink(tmppath)
        return hash

    def load(self, category, path, hash):
        content = self.versionmanager.load(category, path, hash)
        if content is not None:
            return content
        cachepath = self._cache_file(category, path, hash)
        os.makedirs(os.path.dirname(cachepath), exist_ok=True)
        tmppath = cachepath + '.tmp'
        from score.netfs import DownloadFailed
        try:
            tmpfile = open(tmppath, 'wb')
            fcntl.flock(tmpfile, fcntl.LOCK_EX)
            if os.path.exists(cachepath):
                # another process downloaded the file
                return self.versionmanager.load(category, path, hash)
            time = self.netfs.connect().download(
                self._netfspath(category, path, hash), tmpfile)
            os.utime(tmppath, (time, time))
            shutil.move(tmppath, cachepath)
        except DownloadFailed:
            return
        finally:
            fcntl.flock(tmpfile, fcntl.LOCK_UN)
            tmpfile.close()
            os.unlink(tmppath)
        return self.versionmanager.load(category, path, hash)
