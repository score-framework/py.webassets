import click
import xxhash


@click.group('conf')
def main():
    """
    Manages webassets.
    """
    pass


@main.command
@click.option('--module', '-m', multiple=True)
@click.pass_context
def bundle(clickctx, module):
    """
    Create bundles.
    """
    webassets = clickctx.obj['conf'].load('webassets')
    modules = module
    if not modules:
        modules = webassets.modules
    for module in modules:
        webassets.get_bundle_url(module)


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
        for path in sorted(path_iter):
            hash = webassets.get_asset_hash(module, path)
            print('%s/%s %s' % (module, path, hash))


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
