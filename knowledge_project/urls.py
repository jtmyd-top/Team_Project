"""Compatibility URLConf for the former project-wide route aggregator.

Domain URL entrypoints now live in ``Team_Project.urls`` and include each app
directly. Keep this module importable for deployments or tests that still
reference ``knowledge_project.urls``.
"""

urlpatterns = []
