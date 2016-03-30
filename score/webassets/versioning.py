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
import email
import fcntl
import hashlib
import io
import logging
import os
import re
import shutil
import textwrap
import time
import subprocess


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
            result = self.load(category, path, hash)
            if result:
                body, age = result
                ctx.http.response.body = body
                ctx.http.response.cache_control.max_age = \
                    str(60 * 60 * 24 * 30 * 12)  # ~1 year
                ctx.http.response.age = age
                ctx.http.response.etag = hash
                return True
        return False


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


class Frozen(VersionManager):
    """
    A caching version manager that generates file hashes only once and returns
    the same value on consecutive calls. See its :meth:`.create_file_hasher`
    function.

    Note: This object never clears is targeted at environments that do not
    change during runtime (hence its name). It never clears its internal
    cache, for example. Use this class only if you have such an environment.
    """

    def __init__(self, folder):
        super().__init__(folder)
        self.hashers = {}

    def create_file_hasher(self, files):
        """
        Overridden to cache the result of the hasher returned by the parent.
        """
        if isinstance(files, str) or not hasattr(files, '__iter__'):
            files = files,
        if not len(files):
            return lambda: None
        files = tuple(files)
        if files not in self.hashers:
            hash = self._gen_hash(files)
            self.hashers[files] = lambda: hash
        return self.hashers[files]

    def _gen_hash(self, files):
        hasher = super().create_file_hasher(files)
        return hasher()


class Repository(Frozen):
    """
    A special typo of :class:`.Frozen` VersionManager that uses the last
    changeset hash where files were last modified in given mercurial or git
    *repositories*, instead of the last local modification timestamp. This
    method will thus generate the same timestamp on two different machines,
    provided they are accessing the same repositories.
    """

    def __init__(self, folder, repositories):
        super().__init__(folder)
        self.repositories = []
        for repo in repositories:
            self.repositories += self._init_repo(repo)
        self.repositories.sort(key=lambda r: len(r[1]))

    def _init_repo(self, repo):
        """
        Finds all subrepositories of given *repo* and recurses through them.
        """
        repo = os.path.abspath(repo)
        if os.path.exists(repo + '/.hg'):
            return self._init_hg_repo(repo)
        elif os.path.exists(repo + '/.git'):
            return self._init_git_repo(repo)
        raise Exception('Not a repository: ' + repo)

    def _init_hg_repo(self, repo):
        file = '%s/.hgsub' % repo
        if not os.path.exists(file):
            return []
        subrepos = [('hg', repo)]
        for line in open(file).read().split('\n'):
            line = re.sub('#.*', '', line).strip()
            if not line:
                continue
            subrepo = '%s/%s' % (repo, line.split('=')[0].strip())
            subrepos += self._init_repo(subrepo)
        return subrepos

    def _init_git_repo(self, repo):
        subrepos = [('git', repo)]
        cmd = ['git', 'submodule', 'status']
        status = str(subprocess.check_output(cmd, cwd=repo), 'ASCII')
        for line in filter(None, status.split('\n')):
            subrepo = repo + '/' + line.split(' ')[2]
            subrepos += self._init_repo(subrepo)
        return subrepos

    def _gen_hash(self, files):
        """
        Returns the most-recent changeset hash for the list of given files.
        """
        repo2files = {}
        files = list(files)
        for file in files[:]:
            absfile = os.path.realpath(file)
            for repo in self.repositories:
                # FIXME: we're just checking if the file is in a sub-folder, but
                # it might actually be an untracked file.
                if absfile.startswith(repo[1]):
                    try:
                        repo2files[repo].append(absfile)
                    except KeyError:
                        repo2files[repo] = [absfile]
                    files.remove(file)
                    break
        hashes = []
        if files:
            # These files are outside of repositories, we will hash their
            # content, as the last modification timestamps on different machines
            # might differ.
            log.info('Using MD5 for these files outside of configured '
                     'repositories:\n - ' + '\n - '.join(files))
            for file in files:
                md5 = hashlib.md5()
                with open(file, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        md5.update(chunk)
                hashes.append(md5.hexdigest())
        for repo, files in repo2files.items():
            if repo[0] == 'hg':
                hashes.append(self._gen_hg_hash(repo[1], files))
            else:
                hashes.append(self._gen_git_hash(repo[1], files))
        return hashlib.sha256(' '.join(hashes).encode('UTF-8')).hexdigest()

    def _gen_hg_hash(self, repo, files):
        # FIXME: The method used here does not detect any changes that were
        # *merged* into the current branch. Here is a related SO question:
        # http://stackoverflow.com/questions/6134476/get-all-changed-files-for-a-given-directory-in-a-branch
        cmd = ['hg', 'log', '--limit=1', '--template="{node}"'] + files
        result = str(subprocess.check_output(cmd, cwd=repo), 'ASCII')
        return result[:-1]

    def _gen_git_hash(self, repo, files):
        cmd = ['git', 'log', '--format=format:%H', '--max-count=1'] + files
        result = str(subprocess.check_output(cmd, cwd=repo), 'ASCII')
        return result[:-1]


# for backward compatibility
Mercurial = Repository


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
