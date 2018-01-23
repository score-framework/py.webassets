import click
import xxhash
from urllib.parse import urlparse, parse_qsl
from ._init import Request
import email
import io


@click.group()
def main():
    """
    Manages webassets.
    """
    pass


@main.command('asset-hash')
@click.argument('module', required=False)
@click.argument('paths', nargs=-1)
@click.pass_context
def asset_hash(clickctx, module, paths):
    """
    Provides the real asset hashes.
    """
    webassets = clickctx.obj['conf'].load('webassets')
    if module:
        modules = (module,)
    else:
        modules = webassets.modules
    for module in modules:
        if paths:
            path_iter = paths
        else:
            proxy = webassets._get_proxy(module)
            path_iter = proxy.iter_default_paths()
        for path in path_iter:
            hash = webassets.get_asset_hash(module, path)
            print('%s/%s %s' % (module, path, hash))


@main.command('asset-url')
@click.argument('module', required=False)
@click.argument('paths', nargs=-1)
@click.pass_context
def asset_url(clickctx, module, paths):
    """
    Provides asset URLs
    """
    webassets = clickctx.obj['conf'].load('webassets')
    if module:
        modules = (module,)
    else:
        modules = webassets.modules
    for module in modules:
        if paths:
            path_iter = paths
        else:
            proxy = webassets._get_proxy(module)
            path_iter = proxy.iter_default_paths()
        for path in path_iter:
            print(webassets.get_asset_url(module, path))


@main.command('request-response')
@click.option('-H', '--header', 'headers', multiple=True)
@click.argument('url')
@click.pass_context
def request_response(clickctx, url, headers):
    """
    Provides the content of an asset
    """
    webassets = clickctx.obj['conf'].load('webassets')
    parsed = urlparse(url)
    if headers:
        headers = email.message_from_file(io.StringIO('\n'.join(headers)))
    else:
        headers = {}
    request = Request(
        parsed.path,
        dict(parse_qsl(parsed.query)),
        headers)
    status, headers, body = webassets.get_request_response(request)
    print(status)
    for key, value in headers.items():
        print('%s: %s' % (key, value))
    print('')
    if body:
        print(body)


@main.command('bundle-url')
@click.argument('module')
@click.argument('paths', nargs=-1)
@click.pass_context
def bundle_url(clickctx, module, paths):
    """
    Provides the real bundle hashes.
    """
    webassets = clickctx.obj['conf'].load('webassets')
    print(webassets.get_bundle_url(module, paths or None))


@main.command('bundle-hash')
@click.argument('module', required=False)
@click.argument('paths', nargs=-1)
@click.pass_context
def bundle_hash(clickctx, module, paths):
    """
    Provides the real bundle hashes.
    """
    webassets = clickctx.obj['conf'].load('webassets')
    if module:
        modules = (module,)
    else:
        modules = webassets.modules
    for module in modules:
        if paths:
            path_list = paths
        else:
            proxy = webassets._get_proxy(module)
            path_list = list(proxy.iter_default_paths())
        name = webassets.get_bundle_name(module, path_list)
        module_hash = webassets.get_bundle_hash(module, path_list)
        print('%s/%s %s' % (module, name, module_hash))


@main.command()
@click.pass_context
def freeze(clickctx):
    """
    Provides the real bundle hashes.
    """
    webassets = clickctx.obj['conf'].load('webassets')
    webassets.freeze = False
    modules = webassets.modules
    hash = xxhash.xxh64()
    for module in modules:
        proxy = webassets._get_proxy(module)
        path_list = list(proxy.iter_default_paths())
        hash.update(webassets.get_bundle_hash(module, path_list))
    print(hash.hexdigest())


if __name__ == '__main__':
    main()
