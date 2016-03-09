.. module:: score.webassets
.. role:: faint
.. role:: confkey

***************
score.webassets
***************

Introduction
============

The aim of this module is to provide an infrastructure for handling assets in
a web project. An :term:`asset` is a static resource that is required by the
web application, like a javascript file, or css definitions.

Assets
------

Assets always fall into a :term:`category <asset category>`, which classifies
a resource. Each category must have a unique name describing it. The module
handling cascading style sheets, for example, refers to its assets' category
with the string "css". The one for javascript files, on the other hand, uses
"js".

Apart from a *category*, an asset also has a :term:`path <asset path>`. Such
a path is very much like a file system path with the following restrictions:

- file and folder names *must* only contain alphanumeric characters,
  underscores and hyphens
- the directory separator is always a slash,
- it *must not* be absolute (i.e. cannot start with a slash), and 
- it *must not* contain references to upper folders (like
  :file:`spam/../bacon.css`).

Each asset category should have a defined *root* folder, where all assets of
that type reside. This means, for example, that there must be one and only one
folder containing *css* resources.

When the definition of the *root* folder is in place, individual files can be
referenced with relative paths to the files. If, for example, we have the
following file system layout … ::

    css/
      reset.css
      frontpage.scss
      article/
        main.css.jinja2

… and have defined the folder :file:`css` as the *root* of all assets
belonging to the category "css", we could reference three distinct assets with
the following paths:

- ``reset.css``
- ``frontpage.scss``
- ``article/main.css.jinja2``

As we can see in this example, assets do not have to have a uniform file
extension.

.. _virtual_assets:

Virtual Assets
--------------

Not all assets need to reside on the file system. So called
:term:`virtual assets <virtual asset>` are assets that have a *category* and a
*path*, as usual, but no corresponding file in the *root* folder of the
category they belong to.

Instead, they are registered in source code with a *callback* function that
generates the content of the asset whenever necessary. This allows developers
to provide highly flexible assets, that cannot be written in a static manner.

If, for example, one must implement a web application where the colors in the
frontend are partially defined by editors in the backend, one might use a
virtual css file for generating the color definitions using a database
connection or a local `dict` object:

>>> def generator():
...     definitions = []
...     for article, color in colormap.items():
...         definitions.append('.article-%d: %s' % (article.id, color))
...     return '\n'.join(definitions)
... 
>>> virtualassets.register('article-colors.css', generator)

The class :class:`score.webassets.VirtualAssets` provides a container for the
virtual assets of a given category.

Hidden Assets
-------------

An *asset*, whether *virtual* or not, is considered *hidden*, if its file name
starts with an underscore. It is also considered *hidden*, if it resides in a
folder that is hidden.

*Hidden* assets behave exactly like ordinary [virtual] assets, but functions
operating on *all* assets of a given type will skip *hidden* assets by
default.

This feature can be exploited to mark assets that are only required in certain
circumstances. One good example are Internet Explorer-Specific style sheets.
When using our :mod:`score.css` module, for example, one might write::

    <html>
        <head>
            <!-- The next line includes *all* css files, except those
                 that are *hidden*, as described above -->
            {{ css() }}
            <!--[if IE]>
                <!-- The next line only includes the file "_ie/common.css",
                     which was skipped above, because it is considered
                     *hidden*, as it resides in a hidden folder (i.e. one
                     whose name starts with an underscore) -->
                {{ css('_ie/common.css') }}
            <![endif]-->
        </head>

.. _webassets_versioning:

Asset Versioning
----------------

Most of a web applications assets rarely change. At least they stay exactly
the same for long periods of time. A common technique for helping browsers
cache these assets more efficiently is the exposure of versioning information
of assets within their URLs.

Let us assume we have a css asset called ``colors.css``, which has the
following content at its first deployment::

    h1.article-heading {
        background-color: #E3D9C6;
    }

The URL of this resource might be http://example.com/css/colors.css. If we
would use just this URL, the browser would need to check back every once in a
while to see if this resource has changed. It would thus request the resource
much more often than necessary.

If we instead add a version string to the URL, we can tell the browser to
cache this resource forever. When the resource changes, we change the URL and
point to the new URL in our HTML.

The initial version of the resource might now have the URL
http://example.com/css/colors.css?version=1. When a browser requests this URL,
we send all required HTTP headers that tell the browser that the resource
found in this URL will *never* change.

If we add a definition to our css asset at a later point …

::

    h1.article-heading {
        background-color: #E3D9C6;
    }
    h2.article-heading {
        background-color: #DDC49A;
    }

… we immediately change the URL of that resource to
http://example.com/css/colors.css?version=2. The browser sees a new URL and
assumes that it must be a different asset (which it technically is) and
requests its contents. We, again, tell it to keep this file forever and to
never ask the web server again for this exact URL.

This feature is implemented in the class
:class:`score.webassets.versioning.VersionManager`. It does not use incremental
values as version strings, though, as the class cannot know when the number
needs to be incremented. Instead, it operates on hashed value, like the hashed
timestamps of the asset files.

Configuration
=============

.. autofunction:: score.webassets.init

.. autoclass:: score.webassets.ConfiguredWebassetsModule()

    .. attribute:: cachedir

        The cache folder that can be used by other modules. A Module using
        this value should first create a sub-folder with its
        :term:`category string <asset category>`.

    .. attribute:: versionmanager

        The :class:`score.webassets.versioning.VersionManager` object to use
        for asset versioning.

.. autoexception:: score.webassets.AssetNotFound

Virtual Assets
==============

.. autoclass:: score.webassets.VirtualAssets
    :members:

Version Management
==================

The asset versioning is implemented in the package
`score.webassets.versioning`.

.. automodule:: score.webassets.versioning

.. autoclass:: score.webassets.versioning.VersionManager
    :members:

.. autoclass:: score.webassets.versioning.Dummy()

.. autoclass:: score.webassets.versioning.Frozen

.. autoclass:: score.webassets.versioning.Repository

