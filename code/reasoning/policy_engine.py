"""Policy engine for applying deletion_rules.csv to candidate records."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from code.schemas import DeletionRule


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
        return CATEGORY_ACTION_MAP.get(data_category, "DELETE")

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
        action = self.get_required_action(data_category)

        # Case 1: Active data flow
        if is_active_flow or (system_id == "integration_service" and observed_state == "ACTIVE"):
            return RecordAssessment(
                system_id=system_id,
                resource_id=resource_id,
                data_category=data_category,
                required_action="DISABLE",
                observed_state="ACTIVE",
                is_violation=True,
                evidence_id=evidence_id,
                violation_operation="REPORT_ACTIVE_DATA_FLOW",
                remediation_operation="DISABLE_DATA_FLOW",
                verification_operation="VERIFY_DATA_FLOW_DISABLED",
            )

        # Case 2: Restore risk
        if is_restore_risk or (system_id == "backup_service" and observed_state == "ACTIVE"):
            return RecordAssessment(
                system_id=system_id,
                resource_id=resource_id,
                data_category=data_category,
                required_action="BLOCK",
                observed_state="ACTIVE",
                is_violation=True,
                evidence_id=evidence_id,
                violation_operation="REPORT_RESTORE_RISK",
                remediation_operation="BLOCK_RESTORE",
                verification_operation="VERIFY_RESTORE_BLOCKED",
            )

        # Case 3: Action DELETE
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

        # Case 4: Action REDACT
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

        # Case 5: Action ANONYMIZE
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

        # Case 6: Action RETAIN
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
