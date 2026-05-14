"""Tests for the BSData freshness audit module."""

from __future__ import annotations

import unittest


class AuditImportTests(unittest.TestCase):

    def test_audit_module_imports_clean(self):
        # Should not raise at import time.
        from code.bsdata import audit  # noqa: F401
        self.assertTrue(hasattr(audit, "audit_codex_coverage"))

    def test_audit_codex_coverage_currently_clean(self):
        # Every cached .cat file should be registered in CODEX_TO_FACTION.
        from code.bsdata.audit import audit_codex_coverage
        self.assertEqual(audit_codex_coverage(), [])


if __name__ == "__main__":
    unittest.main()
