# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
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
The aim of this module is to provide an infrastructure for handling assets -
like javascript or css files - in a web project. It is not intended to be
used directly; instead it provides footing for other modules. Those modules
making use of score.webassets' features should have a :term:`category
<asset category>` string, that can be used to distinguish different asset
types.

Currently it provides two features to be used by others - virtual assets and
asset versioning - as well as an adaption for the pyramid framework.
"""

from ._init import init, ConfiguredWebassetsModule, AssetNotFound, Request
from .proxy import TemplateWebassetsProxy, WebassetsProxy


__all__ = (
    'init', 'ConfiguredWebassetsModule', 'AssetNotFound', 'Request',
    'TemplateWebassetsProxy', 'WebassetsProxy',)
