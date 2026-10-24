"""CSV loader and validator for dataset files."""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from code.schemas import (
    DeletionRequest,
    UserIdentity,
    UserAuditEntry,
    SystemActivity,
    DeletionRule,
    EvidenceFileInfo,
)
from code.config import (
    DELETION_REQUESTS_PATH,
    USER_IDENTITIES_PATH,
    USER_AUDIT_LOG_PATH,
    SYSTEM_ACTIVITY_PATH,
    DELETION_RULES_PATH,
    EVIDENCE_FILES_PATH,
)


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parses an ISO 8601 datetime string into a timezone-aware datetime."""
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)


def load_deletion_requests(path: Optional[Path] = None) -> List[DeletionRequest]:
    p = path or DELETION_REQUESTS_PATH
    requests = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            requests.append(
                DeletionRequest(
                    case_id=row["case_id"].strip(),
                    email=row["email"].strip().lower(),
                    requested_at=parse_iso_datetime(row["requested_at"]),
                    reported_status=row["reported_status"].strip(),
                    reported_at=parse_iso_datetime(row["reported_at"]),
                    audit_at=parse_iso_datetime(row["audit_at"]),
                    request_text=row["request_text"].strip(),
                )
            )
    return requests


def load_user_identities(path: Optional[Path] = None) -> List[UserIdentity]:
    p = path or USER_IDENTITIES_PATH
    identities = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            identities.append(
                UserIdentity(
                    user_id=row["user_id"].strip(),
                    name=row["name"].strip(),
                    email=row["email"].strip().lower(),
                    phone=row["phone"].strip(),
                    email_hash=row["email_hash"].strip(),
                    updated_at=parse_iso_datetime(row["updated_at"]),
                )
            )
    return identities


def load_user_audit_entries(path: Optional[Path] = None) -> List[UserAuditEntry]:
    p = path or USER_AUDIT_LOG_PATH
    entries = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                UserAuditEntry(
                    audit_id=row["audit_id"].strip(),
                    user_id=row["user_id"].strip(),
                    event_time=parse_iso_datetime(row["event_time"]),
                    field_name=row["field_name"].strip(),
                    old_value=row["old_value"].strip(),
                    new_value=row["new_value"].strip(),
                )
            )
    return entries


def load_system_activities(path: Optional[Path] = None) -> List[SystemActivity]:
    p = path or SYSTEM_ACTIVITY_PATH
    activities = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            activities.append(
                SystemActivity(
                    activity_id=row["activity_id"].strip(),
                    event_time=parse_iso_datetime(row["event_time"]),
                    event_type=row["event_type"].strip(),
                    source_system=row["source_system"].strip(),
                    target_system=row["target_system"].strip(),
                    resource_id=row["resource_id"].strip(),
                    reported_result=row["reported_result"].strip(),
                    details=row["details"].strip(),
                )
            )
    return activities


def load_deletion_rules(path: Optional[Path] = None) -> List[DeletionRule]:
    p = path or DELETION_RULES_PATH
    rules = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rules.append(
                DeletionRule(
                    rule_id=row["rule_id"].strip(),
                    data_category=row["data_category"].strip(),
                    condition=row["condition"].strip(),
                    required_action=row["required_action"].strip(),
                )
            )
    return rules


def load_evidence_manifest(path: Optional[Path] = None) -> List[EvidenceFileInfo]:
    p = path or EVIDENCE_FILES_PATH
    manifest = []
    with open(p, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            manifest.append(
                EvidenceFileInfo(
                    file_id=row["file_id"].strip(),
                    file_path=row["file_path"].strip(),
                    origin=row["origin"].strip(),
                    captured_at=parse_iso_datetime(row["captured_at"]),
                )
            )
    return manifest
