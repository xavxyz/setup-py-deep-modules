"""Fixture project used to prove the deep-module boundary rules.

Its immediate subpackages (``billing``, ``notifications``) are the deep-module
tier: each exposes a small public surface through its ``__init__.py`` and keeps
its implementation in an underscore-prefixed subpackage.
"""
