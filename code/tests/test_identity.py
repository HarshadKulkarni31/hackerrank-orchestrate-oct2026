"""Unit tests for IdentityResolver."""

from datetime import datetime, timezone
import unittest

from code.identity.resolver import IdentityResolver
from code.schemas import UserAuditEntry, UserIdentity


class TestIdentityResolver(unittest.TestCase):
    def setUp(self):
        self.users = [
            UserIdentity(
                user_id="user_100",
                name="John Doe",
                email="john.doe@newmail.com",
                phone="+15551234567",
                email_hash="hash_new_123",
                updated_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            )
        ]
        self.audits = [
            UserAuditEntry(
                audit_id="audit_01",
                user_id="user_100",
                event_time=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                field_name="email",
                old_value="johnny@oldmail.com",
                new_value="john.doe@newmail.com",
            )
        ]
        self.resolver = IdentityResolver(self.users, self.audits)

    def test_resolve_from_current_email(self):
        cutoff = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        bundle = self.resolver.build_identity_bundle("john.doe@newmail.com", cutoff)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.user_id, "user_100")
        self.assertIn("john.doe@newmail.com", bundle.emails)
        self.assertIn("johnny@oldmail.com", bundle.emails)

    def test_resolve_from_historical_email(self):
        cutoff = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        bundle = self.resolver.build_identity_bundle("johnny@oldmail.com", cutoff)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.user_id, "user_100")
        self.assertIn("johnny@oldmail.com", bundle.emails)

    def test_cutoff_ignores_future_audit_changes(self):
        cutoff = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        # Prior to May 1 2026, historical audit entry didn't exist yet
        bundle = self.resolver.build_identity_bundle("john.doe@newmail.com", cutoff)
        self.assertIsNotNone(bundle)
        self.assertNotIn("johnny@oldmail.com", bundle.emails)


if __name__ == "__main__":
    unittest.main()
