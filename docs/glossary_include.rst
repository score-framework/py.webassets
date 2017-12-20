.. _webassets_glossary:

.. glossary::

    asset
        A resource that is a mostly static part of a web application. Examples
        include, but are not limited to:

        - cascading style sheets
        - javascript files
        - icons and other images that are part of the layout (i.e. those that
          were integrated by designers, not those uploaded by users)

    asset module
        The name of the module providing an asset. This is part of an asset's
        unique identifier: Various functions in this module need a combination
        of a module name and a :term:`path <asset path>` to identify an asset.

    asset path
        A relative file path to an asset. This can be an arbitrary string, but
        usually looks very much like a path on a file system, since assets are
        usually stored as files.
        
    asset hash
        A random string that changes whenever the contents of an asset changes.
        This value is useful for implementing client-side caching. Example URL
        with appended asset hash: ``/css/reset.css?version=ca29f34cbfd2``

        The same concept applies for :term:`bundles <asset bundle>`, as well.

        See the :ref:`narrative documentation of webasset versioning
        <webassets_versioning>` for an in-depth explanation.

    asset bundle
        A file containing the content of multiple assets. This might be as
        simple as a string concatenation of css files, or as complex as an
        externally built browserify_ javascript bundle.

        .. _browserify: http://browserify.org/
