.. module:: score.webassets
.. role:: confkey
.. role:: confdefault

***************
score.webassets
***************

The aim of this module is to provide an infrastructure for handling assets in
a web project. An :term:`asset` is a supplementary resource required by the web
application, like a javascript file, or css definitions.

Quickstart
==========

Configure a folder, where this module should store all created :term:`bundles
<asset bundle>` and the provide a list of modules, to provide as web assets:

.. code-block:: ini

    [score.init]
    modules =
        score.ctx
        score.http
        score.css
        score.js
        score.webassets

    [webassets]
    rootdir = ${here}/_bundles
    modules =
        css
        js

You can now include your css and javascript assets in your html templates. The
next fragment is in jinja2 format:

.. code-block:: jinja

    <html>
        <head>

            <style>
                {# Will render the content of the given css file #}
                {{ webassets_content('css', 'above-the-fold.css') }}
            </style>

            {# Will load *all* css files  with a <link> tag #}
            {{ webassets_link('css') }}

            {# Will load a bundle consiting of two javascript files #}
            {{ webassets_link('js', 'file1.js', 'file2.js') }}

        </head>
        ...

.. comment:

Configuration
=============

.. autofunction:: init

Details
=======


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

If we instead add a "version string" to the URL, we can tell the browser to
cache this resource forever. When the resource changes, we change the URL and
point to the new URL in our HTML.

The initial "version" of the resource might now have the URL
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

This feature is automatically enabled, although it does not use incremental
values as "version strings", as in the examples above. Instead, it operates
using hashes of the asset contents. That's why they are referred to as
:term:`asset hashes <asset hash>` throughout the documentation.


.. _webassets_freezing:

Asset Freezing
--------------

Normally, the webassets module will determine the asset hash based on the
asset's content. Unfortunately, this method is very slow: whenever we need the
hash of an asset, we will need to render the content of the asset.

To avoid such expensive operations during deployment, the module has two
different modes for freezing the asset hashes. You can configure
score.webassets to remember the hash of each asset by passing ``True`` in the
module's ``freeze`` configuration. This ensures that hashes are calculated at
most once.

.. code-block:: ini

    [webassets]
    freeze = True


If you have a deployment script, it is even better to pre-calculate the hash
and to provide that value in the module configuration:

.. code-block:: console

    $ score webassets freeze
    b18ed2b601ab3850

.. code-block:: ini

    [webassets]
    freeze = b18ed2b601ab3850


.. _webassets_proxy:

Proxy
-----

.. note::

    The intended audience of this section is module developers. This is the
    reason the next few suggestions may seem a bit too abstract for day to day
    usage.

Every module that wants to provide web assets through this module must
return a sub-class of :class:`WebassetsProxy` from the configured module's
``score_webassets_proxy()`` function.

As an example, we will assume that we want to build a module called
"myobjects", that can grant access to javascript objects stored in JSON files.
We will be accessing the objects one by one, but may occasionally need to
retrieve multiple objects at once.

To provide these objects as web assets, we need to create a proxy object. We
will use the simpler :class:`TemplateWebassetsProxy` to keep the example code
short:

.. code-block:: python

    from score.webassets import TemplateWebassetsProxy

    class MyobjectsWebassets(TemplateWebassetsProxy):

        def __init__(self, tpl):
            super().__init__(tpl, 'application/json')

        def render_url(self, url):
            return '''
                <script>
                    (function() {
                        var url = JSON.decode(%s);
                        fetch(url).then(function(response) {
                            return response.json();
                        }).then(function(result) {
                            myGlobalObjectStorage.add(result);
                        });
                    })();
                </script>
            ''' % (json.dumps(url),)

        def create_bundle(self, paths):
            return ''.join(map(self.render, paths))

Your configured module must now return an instance of this class in its
``score_webassets_proxy()`` method:

.. code-block:: python

    from score.init import ConfiguredModule

    class ConfiguredMyobjectsModule(ConfiguredModule)

        def __init__(self, tpl):
            self.tpl = tpl  # a score.tpl dependency
            super().__init__('myobjects')

        def score_webassets_proxy(self):
            return MyobjectsWebassets(self.tpl)

After configuring score.webassets to include this module, you can make use of
your new module inside html templates. The next fragment is in jinja2 format:

.. code-block:: jinja

    <html>
        <head>

            <script>
                // some code initializing myGlobalObjectStorage
            </script>

            {# lazy-loading all assets #}
            {{ webassets_link('myobjects') }}

            {# embedding asset content directly #}
            <script>
                (function() {
                    myGlobalObjectStorage.add(JSON.decode(
                        {{ webassets_content('myobjects') }}
                    ));
                })();
            </script>

        </head>
        ...

API
===

Configuration
-------------

.. autofunction:: init

.. autoclass:: ConfiguredWebassetsModule()
    :members:

Helpers
-------

.. class:: Request

    A :func:`collections.namedtuple` describing the parts of HTTP request, that
    are required for :meth:`ConfiguredWebassetsModule.get_request_response` to
    work. It consists of these 3 values:

    - **path**: The path_ section of the requested URL.
    - **GET**: Parsed `dict` of the query part.
    - **headers**: Another `dict` containing all headers, the client provided.

    .. _path: https://en.wikipedia.org/wiki/URL#Syntax

.. autoclass:: WebassetsProxy
    :members:

.. autoclass:: TemplateWebassetsProxy

.. autoexception:: AssetNotFound()
