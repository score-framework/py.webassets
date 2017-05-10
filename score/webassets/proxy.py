import abc
from score.tpl import TemplateNotFound
import hashlib


class WebassetsProxy(abc.ABC):

    @abc.abstractmethod
    def iter_paths(self):
        pass

    def validate_path(self, path):
        return any((path == valid) for valid in self.iter_paths())

    @abc.abstractmethod
    def hash(self, path):
        pass

    @abc.abstractmethod
    def render(self, path):
        pass

    @abc.abstractmethod
    def mimetype(self, path):
        pass

    @abc.abstractmethod
    def render_url(self, url):
        pass

    @abc.abstractmethod
    def create_bundle(self, paths):
        pass

    def bundle_hash(self, paths):
        hashes = []
        for path in sorted(paths):
            hashes.append(self.hash(path))
        return hashlib.sha256('\0'.join(hashes).encode('UTF-8')).hexdigest()

    @abc.abstractmethod
    def bundle_mimetype(self, paths):
        pass


class TemplateWebassetsProxy(WebassetsProxy):

    def __init__(self, tpl, mimetype):
        self.tpl = tpl
        self._mimetype = mimetype

    def iter_paths(self):
        return self.tpl.iter_paths(mimetype=self._mimetype)

    def hash(self, path):
        return self.tpl.hash(path)

    def render(self, path):
        try:
            return self.tpl.render(path)
        except TemplateNotFound:
            from ._init import AssetNotFound
            raise AssetNotFound(path)

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
