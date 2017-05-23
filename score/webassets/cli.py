import click


@click.group('conf')
def main():
    """
    Manages webassets.
    """
    pass


@main.command('bundle')
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


if __name__ == '__main__':
    main()
