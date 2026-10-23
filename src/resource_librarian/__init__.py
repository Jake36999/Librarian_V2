"""Librarian: a local research library and co-work Core.

A second, standalone version of the Resource Library, built to be deployed into
a new vault and to scale with it. See PLAN - Librarian V2.md.
"""
# The distribution retains ``resource-librarian`` as a compatibility alias;
# the product shown to people is simply Librarian.  Protocol changes are
# intentionally independent of package SemVer so adapters can decide whether
# a mounted Core is safe to use before rendering a UI.
__version__ = "2.1.0.dev0"
PROTOCOL_VERSION = "2"
ADAPTER_PROTOCOL_RANGE = ">=2,<3"
