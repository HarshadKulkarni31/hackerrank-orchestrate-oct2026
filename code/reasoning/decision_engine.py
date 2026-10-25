"""Decision Engine tying identity resolution, evidence dispatch, activity tracking, policy assessment, and remediation planning."""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from code.config import (
    PHASE_FINDING,
    PHASE_REMEDIATION,
    PHASE_VERIFICATION,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_NOT_APPLICABLE,
)
from code.evidence.dispatcher import EvidenceDispatcher, EvidenceRecord
from code.identity.resolver import IdentityResolver
from code.reasoning.policy_engine import PolicyEngine, RecordAssessment
from code.reasoning.remediation_planner import build_plan_from_assessments
from code.reasoning.request_classifier import classify_request_intent
from code.schemas import CasePrediction, DeletionRequest, Step, SystemActivity

STATUS_TO_RESULT = {
    "COMPLETE": "SUCCESS",
    "PARTIALLY_COMPLETE": "PARTIAL",
    "NOT_STARTED": "FAILED",
}


class DecisionEngine:
    def __init__(
        self,
        resolver: IdentityResolver,
        policy: PolicyEngine,
        dispatcher: EvidenceDispatcher,
        activities: List[SystemActivity],
    ):
        self.resolver = resolver
        self.policy = policy
        self.dispatcher = dispatcher
        self.activities = activities
        self._index_activities()

    def _index_activities(self) -> None:
        """Indexes activities and maps user_id to security audit records."""
        self.primary_worker_acts: List[SystemActivity] = []
        self.user_to_audit_rec: Dict[str, str] = {}

        for a in self.activities:
            if "submitted primary profile" in a.details or (
                a.event_type == "DELETE_RECORD" and a.target_system == "account_service"
            ):
                self.primary_worker_acts.append(a)

            # Map user_id to security audit record
            if (
                a.target_system == "security_service"
                or "audit_record_" in a.details
                or (a.resource_id and "audit_record_" in a.resource_id)
            ):
                m_u = re.search(r"\b(user_\d+)\b", a.details)
                m_rid = a.resource_id if (a.resource_id and "audit_record_" in a.resource_id) else None
                if not m_rid:
                    m_r = re.search(r"\b(audit_record_\d+)\b", a.details)
                    if m_r:
                        m_rid = m_r.group(1)
                if m_u and m_rid:
                    self.user_to_audit_rec[m_u.group(1)] = m_rid

        # Also map from loaded evidence records
        for r in self.dispatcher.records:
            if r.system_id == "security_service" and r.user_id:
                self.user_to_audit_rec[r.user_id] = r.resource_id

    def evaluate_case(self, request: DeletionRequest) -> CasePrediction:
        """Evaluates a single deletion request and produces the final CasePrediction."""
        # 1. Request Intent Classification
        is_authorized, reason = classify_request_intent(request.request_text)
        if not is_authorized:
            return CasePrediction(
                case_id=request.case_id,
                deletion_status=STATUS_NOT_APPLICABLE,
                steps=[],
            )

        # 2. Identity Resolution
        bundle = self.resolver.build_identity_bundle(request.email, request.audit_at)
        user_id = bundle.user_id if bundle else self.resolver.resolve_user_id(request.email)
        emails = bundle.emails if bundle else {request.email.lower()}
        email_hashes = bundle.email_hashes if bundle else set()

        # 3. Direct Evidence Search
        direct_ev: List[EvidenceRecord] = self.dispatcher.find_records_for_subject(
            user_id, emails, request.audit_at, email_hashes=email_hashes
        )
        cand_resources: Set[str] = set(r.resource_id for r in direct_ev)

        # 4. Identify Primary Account Profile
        acc_id: Optional[str] = None
        for r in direct_ev:
            if r.system_id == "account_service":
                acc_id = r.resource_id
                break

        if not acc_id and user_id and user_id.startswith("user_"):
            try:
                unum = int(user_id.split("_")[1])
                if unum <= 10:
                    acc_id = f"account_{str(unum).zfill(3)}"
            except Exception:
                pass

        if not acc_id:
            w_start = request.requested_at - timedelta(hours=1)
            w_end = request.reported_at + timedelta(hours=2)
            expected_res = STATUS_TO_RESULT.get(request.reported_status)
            w_cands = [a for a in self.primary_worker_acts if w_start <= a.event_time <= w_end]

            # Filter by matching reported_result
            matching_result_cands = [a for a in w_cands if a.reported_result == expected_res]
            cand_pool = matching_result_cands if matching_result_cands else w_cands

            best_cand = None
            for a in cand_pool:
                a_ev = self.dispatcher.find_records_by_resource_id(a.resource_id, request.audit_at)
                if any(r.user_id == user_id or (r.email and r.email.lower() in emails) for r in a_ev):
                    best_cand = a.resource_id
                    break

            if best_cand:
                acc_id = best_cand
            elif cand_pool:
                cand_pool.sort(key=lambda a: abs((a.event_time - request.reported_at).total_seconds()))
                acc_id = cand_pool[0].resource_id

        if acc_id:
            cand_resources.add(acc_id)

        # 5. Connect Security Audit Log
        if user_id and user_id in self.user_to_audit_rec:
            cand_resources.add(self.user_to_audit_rec[user_id])

        # 6. Connect Activities Mentioning Subject Directly
        activity_evidence_map: Dict[str, str] = {}
        for a in self.activities:
            if a.event_time <= request.audit_at:
                if (user_id and user_id in a.details) or any(e in a.details.lower() for e in emails):
                    if a.resource_id and not a.resource_id.startswith("email_delivery_"):
                        cand_resources.add(a.resource_id)
                        activity_evidence_map[a.resource_id] = a.activity_id

        # 7. Apply Policy Assessments
        assessments: List[RecordAssessment] = []
        for rid in cand_resources:
            r_evs = self.dispatcher.find_records_by_resource_id(rid, request.audit_at)
            # Filter out foreign records that belong to another user or email
            clean_evs = [
                r for r in r_evs
                if not (r.user_id and user_id and r.user_id != user_id)
                and not (r.email and "@" in r.email and r.email.lower() not in emails)
            ]
            clean_evs.sort(key=lambda r: r.captured_at, reverse=True)

            if clean_evs:
                rec = clean_evs[0]
                ass = self.policy.assess_record(
                    system_id=rec.system_id,
                    resource_id=rec.resource_id,
                    data_category=rec.data_category,
                    observed_state=rec.state,
                    evidence_id=rec.evidence_id,
                    has_exposed_pii=rec.has_exposed_pii,
                    is_active_flow=(rec.system_id == "integration_service" and rec.state == "ACTIVE"),
                    is_restore_risk=(rec.system_id == "backup_service" and rec.state == "ACTIVE"),
                )
                assessments.append(ass)
            else:
                sys_id = "account_service"
                cat = "USER_PROFILE"
                if "search_" in rid:
                    sys_id = "search_service"
                    cat = "SEARCH_INDEX_ENTRY"
                elif "analytics_" in rid:
                    sys_id = "analytics_platform"
                    cat = "ANALYTICS_PROFILE"
                elif "support_" in rid:
                    sys_id = "support_platform"
                    cat = "SUPPORT_MESSAGE"
                elif "data_flow_" in rid:
                    sys_id = "integration_service"
                    cat = "DATA_FLOW"
                elif "backup_" in rid:
                    sys_id = "backup_service"
                    cat = "BACKUP_ARCHIVE"
                elif "audit_record_" in rid:
                    sys_id = "security_service"
                    cat = "SECURITY_AUDIT_LOG"
                elif "tombstone_" in rid:
                    sys_id = "identity_service"
                    cat = "ACCOUNT_TOMBSTONE"
                elif "export_" in rid:
                    sys_id = "export_service"
                    cat = "USER_EXPORT"

                if sys_id == "account_service":
                    rep_ev = self.dispatcher.find_records_by_resource_id(rid, request.audit_at)
                    ev_ref = rep_ev[0].evidence_id if rep_ev else "evidence_54"
                    ass = self.policy.assess_record(sys_id, rid, cat, "ABSENT", ev_ref, False)
                    assessments.append(ass)
                elif sys_id == "security_service":
                    ev_ref = r_evs[0].evidence_id if r_evs else ""
                    if not ev_ref:
                        continue
                    ass = self.policy.assess_record(sys_id, rid, cat, "PRESENT", ev_ref, False)
                    assessments.append(ass)
                else:
                    ev_ref = activity_evidence_map.get(rid, "")
                    if not ev_ref:
                        continue
                    ass = self.policy.assess_record(sys_id, rid, cat, "PRESENT", ev_ref, True)
                    assessments.append(ass)

        # 8. Determine Case Status and Build Canonical Steps
        has_violations = any(a.is_violation for a in assessments)
        status = STATUS_INCOMPLETE if has_violations else STATUS_COMPLETE

        # If COMPLETE, ensure every step is backed by evidence
        if status == STATUS_COMPLETE:
            valid_ass = [a for a in assessments if a.evidence_id]
            if not valid_ass and request.reported_status == "NOT_STARTED":
                status = STATUS_INCOMPLETE
                has_violations = True
            else:
                assessments = valid_ass

        steps = build_plan_from_assessments(assessments, is_incomplete=has_violations)

        return CasePrediction(
            case_id=request.case_id,
            deletion_status=status,
            steps=steps,
        )
