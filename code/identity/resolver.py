"""Identity resolver for mapping emails to full subject identity bundles."""

from datetime import datetime
from typing import Dict, List, Optional, Set
from code.schemas import UserIdentity, UserAuditEntry, IdentityBundle


class IdentityResolver:
    def __init__(
        self, identities: List[UserIdentity], audit_entries: List[UserAuditEntry]
    ):
        self.identities_by_id: Dict[str, UserIdentity] = {u.user_id: u for u in identities}
        self.identities_by_email: Dict[str, UserIdentity] = {
            u.email.lower(): u for u in identities
        }

        # Index audit log by user_id
        self.audit_by_user: Dict[str, List[UserAuditEntry]] = {}
        # Also map historical emails to user_id
        self.historical_email_to_user: Dict[str, str] = {}

        for entry in audit_entries:
            self.audit_by_user.setdefault(entry.user_id, []).append(entry)
            if entry.field_name == "email":
                if entry.old_value:
                    self.historical_email_to_user[entry.old_value.strip().lower()] = entry.user_id
                if entry.new_value:
                    self.historical_email_to_user[entry.new_value.strip().lower()] = entry.user_id

    def resolve_user_id(self, email: str) -> Optional[str]:
        norm_email = email.strip().lower()
        if norm_email in self.identities_by_email:
            return self.identities_by_email[norm_email].user_id
        if norm_email in self.historical_email_to_user:
            return self.historical_email_to_user[norm_email]
        return None

    def build_identity_bundle(
        self, email: str, audit_at: datetime
    ) -> Optional[IdentityBundle]:
        norm_email = email.strip().lower()
        user_id = self.resolve_user_id(norm_email)
        if not user_id:
            return None

        bundle = IdentityBundle(user_id=user_id, request_email=norm_email)
        bundle.user_ids.add(user_id)
        bundle.emails.add(norm_email)

        # Add current identity snapshot if available
        current = self.identities_by_id.get(user_id)
        if current:
            if current.email:
                bundle.emails.add(current.email.lower())
            if current.name:
                bundle.names.add(current.name)
            if current.phone:
                bundle.phones.add(current.phone)
            if current.email_hash:
                bundle.email_hashes.add(current.email_hash)

        # Add historical entries at or before audit_at
        user_audits = self.audit_by_user.get(user_id, [])
        for entry in user_audits:
            if entry.event_time <= audit_at:
                if entry.field_name == "email":
                    if entry.old_value:
                        bundle.emails.add(entry.old_value.strip().lower())
                    if entry.new_value:
                        bundle.emails.add(entry.new_value.strip().lower())
                elif entry.field_name == "name":
                    if entry.old_value:
                        bundle.names.add(entry.old_value.strip())
                    if entry.new_value:
                        bundle.names.add(entry.new_value.strip())
                elif entry.field_name == "phone":
                    if entry.old_value:
                        bundle.phones.add(entry.old_value.strip())
                    if entry.new_value:
                        bundle.phones.add(entry.new_value.strip())
                elif entry.field_name == "email_hash":
                    if entry.old_value:
                        bundle.email_hashes.add(entry.old_value.strip())
                    if entry.new_value:
                        bundle.email_hashes.add(entry.new_value.strip())

        return bundle
