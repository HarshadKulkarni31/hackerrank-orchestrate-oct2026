"""Schemas and data models for Ghost Data Still Exists."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Set


@dataclass
class Step:
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_no": self.step_no,
            "phase": self.phase,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "evidence_id": self.evidence_id,
        }


@dataclass
class CasePrediction:
    case_id: str
    deletion_status: str
    steps: List[Step] = field(default_factory=list)


@dataclass
class DeletionRequest:
    case_id: str
    email: str
    requested_at: datetime
    reported_status: str
    reported_at: datetime
    audit_at: datetime
    request_text: str


@dataclass
class UserIdentity:
    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: datetime


@dataclass
class UserAuditEntry:
    audit_id: str
    user_id: str
    event_time: datetime
    field_name: str
    old_value: str
    new_value: str


@dataclass
class IdentityBundle:
    user_id: str
    request_email: str
    emails: Set[str] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    email_hashes: Set[str] = field(default_factory=set)
    user_ids: Set[str] = field(default_factory=set)


@dataclass
class SystemActivity:
    activity_id: str
    event_time: datetime
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str
    details: str


@dataclass
class DeletionRule:
    rule_id: str
    data_category: str
    condition: str
    required_action: str


@dataclass
class EvidenceFileInfo:
    file_id: str
    file_path: str
    origin: str
    captured_at: datetime
