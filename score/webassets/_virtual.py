import hashlib


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
            def hasher(ctx):
                result = callback(ctx)
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

    def render(self, ctx, path):
        """
        Invokes the callback of the asset with given *path* and returns its
        result.
        """
        return self.assets[path][0](ctx)

    def hash(self, ctx, path):
        """
        Invokes the hashing function of the asset with given *path* and
        returns its result.
        """
        return self.assets[path][1](ctx)

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
