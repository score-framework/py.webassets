.. _webassets_glossary:

.. glossary::

    asset
        A resource that is a mostly static part of a web application. Examples
        include, but are not limited to:

        - cascading style sheets
        - javascript files
        - icons and other images that are part of the layout (i.e. those that
          were integrated by designers, not those uploaded by users)

    asset category
        A string describing an asset type. Various functions in this module
        need a combination of a category string and a :term:`path
        <asset path>` to prevent name collisions. The category string of the
        module handling javascript files, for example, is "``js``", that for
        cascading stylesheets is "``css``".

    asset group
        A :term:`virtual asset` combining the contents of various other
        assets. Such an asset group could bundle `jQuery UI`_ and all its
        module files into a single asset, for example.

        .. _jQuery UI: http://jqueryui.com

    asset path
        The relative file path to an asset. If the root folder for css files
        is :file:`/usr/share/css`, for example, the *path* "spam.css" denotes
        the file :file:`/usr/share/css/spam.css`. Paths are very much like
        file system paths, but have the following restrictions:

        - file and folder names *must* only contain alphanumeric characters,
          underscores and hyphens
        - the directory separator is always a slash,
        - it *must not* be absolute (i.e. cannot start with a slash), and 
        - it *must not* contain references to upper folders (like
          :file:`spam/../bacon.css`).

        Note that :term:`virtual assets <virtual asset>` also have a path, but
        do not point to an actual file on the file system.

    version string
        A string that is appended to a URL to control browser caching of
        assets. When using version strings, the browser can be instructed to
        cache the asset forever, as the URL will change, whenever the asset
        changes. Example URL with version string:
        ``/css/reset.css?version=ca29f34cbfd2``

        See the :ref:`narrative documentation of webasset versioning
        <webassets_versioning>` for an in-depth explanation.

    virtual asset
        A :term:`virtual asset` is one that has a :term:`path <asset path>`,
        but is actually not a file. These assets instead have a callback
        function that can generate the content when required.

        See the :ref:`narrative documentation of virtual assets
        <virtual_assets>` for an in-depth explanation.

