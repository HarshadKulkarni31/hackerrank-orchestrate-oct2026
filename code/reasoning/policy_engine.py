"""Policy engine for applying deletion_rules.csv to candidate records."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from code.schemas import DeletionRule

logger = logging.getLogger("ghost_data_audit.policy")

CATEGORY_ACTION_MAP = {
    "USER_PROFILE": "DELETE",
    "SECONDARY_IDENTIFIER": "DELETE",
    "SEARCH_INDEX_ENTRY": "DELETE",
    "CACHE_ENTRY": "DELETE",
    "SUPPORT_MESSAGE": "REDACT",
    "SUPPORT_ATTACHMENT": "DELETE",
    "ANALYTICS_PROFILE": "ANONYMIZE",
    "PRODUCT_TELEMETRY": "ANONYMIZE",
    "USER_EXPORT": "DELETE",
    "MARKETING_PROFILE": "DELETE",
    "EMAIL_DELIVERY_LOG": "REDACT",
    "SECURITY_AUDIT_LOG": "RETAIN",
    "LEGAL_HOLD_RECORD": "RETAIN",
    "BACKUP_ARCHIVE": "RETAIN",
    "ACCOUNT_TOMBSTONE": "REDACT",
    "DATA_FLOW": "DISABLE",
}


@dataclass
class RecordAssessment:
    system_id: str
    resource_id: str
    data_category: str
    required_action: str
    observed_state: str  # PRESENT, ABSENT, REDACTED, ANONYMIZED, ACTIVE, DISABLED, BLOCKED
    is_violation: bool
    evidence_id: str
    violation_operation: Optional[str] = None
    remediation_operation: Optional[str] = None
    verification_operation: Optional[str] = None


class PolicyEngine:
    def __init__(self, rules: List[DeletionRule]):
        self.rules = {r.data_category: r for r in rules}

    def get_required_action(self, data_category: str) -> str:
        if data_category in self.rules:
            return self.rules[data_category].required_action
        if data_category in CATEGORY_ACTION_MAP:
            return CATEGORY_ACTION_MAP[data_category]
        raise ValueError(f"Unknown data category: '{data_category}'")

    def assess_record(
        self,
        system_id: str,
        resource_id: str,
        data_category: str,
        observed_state: str,
        evidence_id: str,
        has_exposed_pii: bool = False,
        is_active_flow: bool = False,
        is_restore_risk: bool = False,
    ) -> RecordAssessment:
        # 1. Explicit Data Flow modeling (integration_service)
        if data_category == "DATA_FLOW" or system_id == "integration_service":
            if is_active_flow or observed_state == "ACTIVE":
                return RecordAssessment(
                    system_id="integration_service",
                    resource_id=resource_id,
                    data_category="DATA_FLOW",
                    required_action="DISABLE",
                    observed_state="ACTIVE",
                    is_violation=True,
                    evidence_id=evidence_id,
                    violation_operation="REPORT_ACTIVE_DATA_FLOW",
                    remediation_operation="DISABLE_DATA_FLOW",
                    verification_operation="VERIFY_DATA_FLOW_DISABLED",
                )
            else:
                return RecordAssessment(
                    system_id="integration_service",
                    resource_id=resource_id,
                    data_category="DATA_FLOW",
                    required_action="DISABLE",
                    observed_state="DISABLED",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_DATA_FLOW_DISABLED",
                )

        # 2. Explicit Restore Risk / Backup modeling (backup_service)
        if data_category == "BACKUP_ARCHIVE" or system_id == "backup_service":
            if is_restore_risk or observed_state == "ACTIVE":
                return RecordAssessment(
                    system_id="backup_service",
                    resource_id=resource_id,
                    data_category="BACKUP_ARCHIVE",
                    required_action="BLOCK",
                    observed_state="ACTIVE",
                    is_violation=True,
                    evidence_id=evidence_id,
                    violation_operation="REPORT_RESTORE_RISK",
                    remediation_operation="BLOCK_RESTORE",
                    verification_operation="VERIFY_RESTORE_BLOCKED",
                )
            elif observed_state == "BLOCKED":
                return RecordAssessment(
                    system_id="backup_service",
                    resource_id=resource_id,
                    data_category="BACKUP_ARCHIVE",
                    required_action="BLOCK",
                    observed_state="BLOCKED",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_RESTORE_BLOCKED",
                )
            else:
                return RecordAssessment(
                    system_id="backup_service",
                    resource_id=resource_id,
                    data_category="BACKUP_ARCHIVE",
                    required_action="RETAIN",
                    observed_state="PRESENT",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_RECORD_PRESENT",
                )

        # 3. Resolve required action with explicit unsupported handling
        try:
            action = self.get_required_action(data_category)
        except ValueError:
            logger.error(
                "Unsupported data category '%s' for resource '%s'",
                data_category,
                resource_id,
            )
            return RecordAssessment(
                system_id=system_id,
                resource_id=resource_id,
                data_category=data_category,
                required_action="UNSUPPORTED",
                observed_state="PRESENT",
                is_violation=True,
                evidence_id=evidence_id,
                violation_operation="REPORT_REMAINING_RECORD",
                remediation_operation="DELETE_RECORD",
                verification_operation="VERIFY_RECORD_ABSENT",
            )

        # 4. Action DELETE
        if action == "DELETE":
            if observed_state == "PRESENT":
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="DELETE",
                    observed_state="PRESENT",
                    is_violation=True,
                    evidence_id=evidence_id,
                    violation_operation="REPORT_REMAINING_RECORD",
                    remediation_operation="DELETE_RECORD",
                    verification_operation="VERIFY_RECORD_ABSENT",
                )
            else:
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="DELETE",
                    observed_state="ABSENT",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_RECORD_ABSENT",
                )

        # 5. Action REDACT (including ACCOUNT_TOMBSTONE and SUPPORT_MESSAGE)
        if action == "REDACT":
            if has_exposed_pii or observed_state == "PRESENT":
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="REDACT",
                    observed_state="PRESENT",
                    is_violation=True,
                    evidence_id=evidence_id,
                    violation_operation="REPORT_EXPOSED_PII",
                    remediation_operation="REDACT_RECORD",
                    verification_operation="VERIFY_RECORD_REDACTED",
                )
            else:
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="REDACT",
                    observed_state="REDACTED",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_RECORD_REDACTED",
                )

        # 6. Action ANONYMIZE
        if action == "ANONYMIZE":
            if has_exposed_pii or observed_state == "PRESENT":
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="ANONYMIZE",
                    observed_state="PRESENT",
                    is_violation=True,
                    evidence_id=evidence_id,
                    violation_operation="REPORT_EXPOSED_PII",
                    remediation_operation="ANONYMIZE_RECORD",
                    verification_operation="VERIFY_RECORD_ANONYMIZED",
                )
            else:
                return RecordAssessment(
                    system_id=system_id,
                    resource_id=resource_id,
                    data_category=data_category,
                    required_action="ANONYMIZE",
                    observed_state="ANONYMIZED",
                    is_violation=False,
                    evidence_id=evidence_id,
                    verification_operation="VERIFY_RECORD_ANONYMIZED",
                )

        # 7. Action RETAIN (SECURITY_AUDIT_LOG, LEGAL_HOLD_RECORD)
        if action == "RETAIN":
            return RecordAssessment(
                system_id=system_id,
                resource_id=resource_id,
                data_category=data_category,
                required_action="RETAIN",
                observed_state="PRESENT",
                is_violation=False,
                evidence_id=evidence_id,
                verification_operation="VERIFY_RECORD_PRESENT",
            )

        return RecordAssessment(
            system_id=system_id,
            resource_id=resource_id,
            data_category=data_category,
            required_action=action,
            observed_state=observed_state,
            is_violation=False,
            evidence_id=evidence_id,
            verification_operation="VERIFY_RECORD_ABSENT",
        )
