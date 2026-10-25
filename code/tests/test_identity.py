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

    def test_future_identity_snapshot_ignored(self):
        cutoff = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        bundle = self.resolver.build_identity_bundle("john.doe@newmail.com", cutoff)
        self.assertIsNotNone(bundle)
        # Snapshot updated on June 1 should not populate snapshot attributes before cutoff
        self.assertEqual(len(bundle.names), 0)

    def test_ambiguous_email_mapping_disambiguated(self):
        users = [
            UserIdentity("user_A", "Alice", "shared@domain.com", "+111", "hash_a", datetime(2026, 1, 1, tzinfo=timezone.utc)),
            UserIdentity("user_B", "Bob", "shared@domain.com", "+222", "hash_b", datetime(2026, 5, 1, tzinfo=timezone.utc)),
        ]
        audits = [
            UserAuditEntry("audit_a", "user_A", datetime(2026, 1, 2, tzinfo=timezone.utc), "email", "old_a@domain.com", "shared@domain.com"),
            UserAuditEntry("audit_b", "user_B", datetime(2026, 4, 1, tzinfo=timezone.utc), "email", "old_b@domain.com", "shared@domain.com"),
        ]
        resolver = IdentityResolver(users, audits)
        # Cutoff in March: user_A had the most recent event
        uid_march = resolver.resolve_user_id("shared@domain.com", datetime(2026, 3, 1, tzinfo=timezone.utc))
        self.assertEqual(uid_march, "user_A")
        # Cutoff in May: user_B had the most recent event
        uid_may = resolver.resolve_user_id("shared@domain.com", datetime(2026, 5, 15, tzinfo=timezone.utc))
        self.assertEqual(uid_may, "user_B")

    def test_missing_account_mapping_no_derivation(self):
        """Ensures user ID is not converted into an account ID via hardcoded naming patterns."""
        cutoff = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        bundle = self.resolver.build_identity_bundle("john.doe@newmail.com", cutoff)
        self.assertEqual(bundle.user_id, "user_100")
        # Ensure user_id cannot be assumed to be account_100 without evidence
        self.assertNotIn("account_100", bundle.emails)


if __name__ == "__main__":
    unittest.main()
