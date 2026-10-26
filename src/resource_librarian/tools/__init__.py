"""Importing this package registers every tool with the registry."""
from . import authoring, batch, browse, capabilities, communities, core, delegate, desk, extract, intake, lenses, library, macros, model_catalog, model_expectations, pdf, ranking, results, sandbox, scout, sessions, staging, taxonomy, upkeep, v1_migration, vault, web, work_search, workbench, workflows  # noqa: F401,E501
from . import pace  # noqa: F401,E402  (the lead's own effort, up to the person's)
from . import resolve  # noqa: F401,E402  (argument resolvers, R2)
