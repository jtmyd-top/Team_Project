"""Compatibility package for legacy ``knowledge_project.views.*`` imports.

Domain views now live in their owning apps (accounts, notes, messaging, vault,
ops, etc.). Legacy submodules in this package remain as thin aliases where
tests or old integrations still import them directly.
"""
