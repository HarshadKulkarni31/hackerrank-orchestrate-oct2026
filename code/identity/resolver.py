"""Identity resolver for mapping emails to full subject identity bundles."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from code.schemas import UserIdentity, UserAuditEntry, IdentityBundle

logger = logging.getLogger("ghost_data_audit.identity")


class IdentityResolver:
    def __init__(
        self, identities: List[UserIdentity], audit_entries: List[UserAuditEntry]
    ):
        self.identities_by_id: Dict[str, UserIdentity] = {u.user_id: u for u in identities}
        self.identities = identities
        self.audit_entries = audit_entries

        # Index audit log by user_id
        self.audit_by_user: Dict[str, List[UserAuditEntry]] = {}
        for entry in audit_entries:
            self.audit_by_user.setdefault(entry.user_id, []).append(entry)

    def resolve_user_id(
        self, email: str, audit_at: Optional[datetime] = None
    ) -> Optional[str]:
        """Resolves an email address to a user_id strictly respecting audit_at cutoff.
        Detects duplicate or ambiguous email mappings across users."""
        norm_email = email.strip().lower()
        candidate_users: Set[str] = set()

        # 1. Check current identity snapshots that were updated at or before audit_at
        for u in self.identities:
            if u.email.strip().lower() == norm_email:
                if audit_at is None or u.updated_at <= audit_at:
                    candidate_users.add(u.user_id)

        # 2. Check audit log entries at or before audit_at
        for entry in self.audit_entries:
            if audit_at is not None and entry.event_time > audit_at:
                continue
            if entry.field_name == "email":
                if entry.old_value and entry.old_value.strip().lower() == norm_email:
                    candidate_users.add(entry.user_id)
                if entry.new_value and entry.new_value.strip().lower() == norm_email:
                    candidate_users.add(entry.user_id)

        # 3. Handle duplicate / ambiguous mappings
        if len(candidate_users) > 1:
            logger.warning(
                "Ambiguous email mapping detected for '%s' at cutoff %s: %s",
                norm_email,
                audit_at,
                candidate_users,
            )
            # Disambiguate by selecting candidate with most recent event before audit_at
            best_user = None
            latest_time = None
            for uid in candidate_users:
                u_entries = [
                    e for e in self.audit_by_user.get(uid, [])
                    if audit_at is None or e.event_time <= audit_at
                ]
                if u_entries:
                    u_entries.sort(key=lambda e: e.event_time, reverse=True)
                    t = u_entries[0].event_time
                else:
                    ident = self.identities_by_id.get(uid)
                    t = ident.updated_at if ident else None

                if t and (latest_time is None or t > latest_time):
                    latest_time = t
                    best_user = uid
            return best_user

        if len(candidate_users) == 1:
            return next(iter(candidate_users))

        # Fallback if no candidate before audit_at: check if snapshot matches
        for u in self.identities:
            if u.email.strip().lower() == norm_email:
                return u.user_id

        return None

    def build_identity_bundle(
        self, email: str, audit_at: datetime
    ) -> Optional[IdentityBundle]:
        """Constructs an IdentityBundle containing all verified identifiers up to audit_at."""
        norm_email = email.strip().lower()
        user_id = self.resolve_user_id(norm_email, audit_at)
        if not user_id:
            return None

        bundle = IdentityBundle(user_id=user_id, request_email=norm_email)
        bundle.user_ids.add(user_id)
        bundle.emails.add(norm_email)

        # Add identity snapshot only if updated at or before audit_at
        current = self.identities_by_id.get(user_id)
        if current and current.updated_at <= audit_at:
            if current.email:
                bundle.emails.add(current.email.strip().lower())
            if current.name:
                bundle.names.add(current.name.strip())
            if current.phone:
                bundle.phones.add(current.phone.strip())
            if current.email_hash:
                bundle.email_hashes.add(current.email_hash.strip().lower())

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
                        bundle.email_hashes.add(entry.old_value.strip().lower())
                    if entry.new_value:
                        bundle.email_hashes.add(entry.new_value.strip().lower())

        return bundle
