"""Unified Evidence Dispatcher for ingesting, parsing, and querying all evidence types."""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from code.evidence.parse_pdf import parse_pdf_document

logger = logging.getLogger(__name__)


@dataclass
class EvidenceRecord:
    evidence_id: str
    captured_at: datetime
    system_id: str
    resource_id: str
    data_category: str
    user_id: Optional[str]
    email: Optional[str]
    state: str
    has_exposed_pii: bool


class EvidenceDispatcher:
    def __init__(self, dataset_dir: Path = Path("dataset")):
        self.dataset_dir = dataset_dir
        self.records: List[EvidenceRecord] = []
        self._by_user: Dict[str, List[EvidenceRecord]] = {}
        self._by_email: Dict[str, List[EvidenceRecord]] = {}
        self._by_resource: Dict[str, List[EvidenceRecord]] = {}

    def load_all(self, manifest_rows: List[Dict[str, str]]) -> None:
        """Parses all evidence files listed in the manifest."""
        self.records.clear()
        for m in manifest_rows:
            file_id = m["file_id"]
            file_path = self.dataset_dir / m["file_path"]
            if not file_path.exists():
                continue

            cap_str = m["captured_at"]
            if cap_str.endswith("Z"):
                cap_str = cap_str[:-1] + "+00:00"
            captured_at = datetime.fromisoformat(cap_str)

            p_str = str(file_path).lower()
            if p_str.endswith(".json"):
                self._parse_json(file_id, captured_at, file_path)
            elif p_str.endswith(".sql"):
                self._parse_sql(file_id, captured_at, file_path)
            elif p_str.endswith(".log"):
                self._parse_log(file_id, captured_at, file_path)
            elif p_str.endswith(".txt"):
                self._parse_txt(file_id, captured_at, file_path)
            elif p_str.endswith(".pdf"):
                self._parse_pdf(file_id, captured_at, file_path)

        # Build lookup indexes
        self._by_user.clear()
        self._by_email.clear()
        self._by_resource.clear()
        for r in self.records:
            if r.user_id:
                self._by_user.setdefault(r.user_id, []).append(r)
            if r.email:
                self._by_email.setdefault(r.email.lower(), []).append(r)
            if r.resource_id:
                self._by_resource.setdefault(r.resource_id, []).append(r)

    def _add_record(self, record: EvidenceRecord) -> None:
        self.records.append(record)

    def _parse_json(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. service_exports bundle
            if "service_exports" in data:
                exports = data["service_exports"]

                # account_service
                for p in exports.get("account_service", {}).get("profile_lookups", []):
                    prof = p.get("profile")
                    status = p.get("status_code")
                    st = "PRESENT" if status == 200 and prof else "ABSENT"
                    em = prof.get("email") if prof else None
                    u = prof.get("customer_reference") if prof else None
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "account_service", p["resource_id"],
                            "USER_PROFILE", u, em, st, False
                        )
                    )

                # search_service
                for q in exports.get("search_service", {}).get("index_queries", []):
                    hits = q.get("hits", {}).get("total", 0)
                    st = "PRESENT" if hits > 0 else "ABSENT"
                    em = q.get("query")
                    docs = q.get("hits", {}).get("documents", [])
                    rid = docs[0].get("resource_id") if docs else q.get("resource_id")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "search_service", rid,
                            "SEARCH_INDEX_ENTRY", None, em, st, False
                        )
                    )

                # analytics_platform
                for an in exports.get("analytics_platform", {}).get("profiles", []):
                    em = an.get("email")
                    u = an.get("customer_reference")
                    has_pii = bool(em or an.get("phone") or an.get("email_hash"))
                    st = "PRESENT" if has_pii else "ANONYMIZED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "analytics_platform", an["resource_id"],
                            "ANALYTICS_PROFILE", u, em, st, has_pii
                        )
                    )

                # support_platform
                for tk in exports.get("support_platform", {}).get("tickets", []):
                    em = tk.get("requester_email")
                    u = tk.get("customer_reference")
                    has_pii = bool(em or tk.get("requester_name") or tk.get("requester_phone"))
                    st = "PRESENT" if has_pii else "REDACTED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "support_platform", tk["resource_id"],
                            "SUPPORT_MESSAGE", u, em, st, has_pii
                        )
                    )

                # export_service
                for exp in exports.get("export_service", {}).get("exports", []):
                    em = exp.get("owner_email")
                    u = exp.get("customer_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "export_service", exp["resource_id"],
                            "USER_EXPORT", u, em, "PRESENT", False
                        )
                    )

                # integration_service
                for conn in exports.get("integration_service", {}).get("connectors", []):
                    en = conn.get("enabled")
                    st = "ACTIVE" if en else "DISABLED"
                    em = conn.get("customer_email")
                    u = conn.get("customer_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "integration_service", conn["resource_id"],
                            "DATA_FLOW", u, em, st, False
                        )
                    )

                # backup_service
                for bk in exports.get("backup_service", {}).get("restore_entries", []):
                    allowed = bk.get("restore_allowed")
                    st = "ACTIVE" if allowed else "BLOCKED"
                    em = bk.get("customer_email")
                    u = bk.get("customer_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "backup_service", bk["resource_id"],
                            "BACKUP_ARCHIVE", u, em, st, False
                        )
                    )

                # security_service
                for sec in exports.get("security_service", {}).get("audit_records", []):
                    u = sec.get("subject_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "security_service", sec["resource_id"],
                            "SECURITY_AUDIT_LOG", u, None, "PRESENT", False
                        )
                    )

            # 2. snapshots bundle
            elif "snapshots" in data:
                for snap in data["snapshots"]:
                    ds = snap.get("data_store")
                    for rec in snap.get("records", []):
                        rid = rec.get("resource_id")
                        u = rec.get("subject_reference") or rec.get("customer_reference") or rec.get("user_id")
                        em = rec.get("email")
                        if ds == "identity_service":
                            has_pii = bool(rec.get("name") or rec.get("email") or rec.get("phone") or rec.get("email_hash"))
                            st = "PRESENT" if has_pii else "REDACTED"
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "identity_service", rid,
                                    "ACCOUNT_TOMBSTONE", u, em, st, has_pii
                                )
                            )
                        elif ds == "security_service":
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "security_service", rid,
                                    "SECURITY_AUDIT_LOG", u, None, "PRESENT", False
                                )
                            )
                        elif ds == "account_service":
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "account_service", rid,
                                    "USER_PROFILE", u, em, "PRESENT", False
                                )
                            )

            # 3. single-service exports
            elif "customer_export_jobs" in str(path):
                jobs = data if isinstance(data, list) else (data.get("records", []) or data.get("jobs", []))
                for job in jobs:
                    u = job.get("customer_reference")
                    em = job.get("email") or job.get("owner_email")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "export_service", job.get("resource_id"),
                            "USER_EXPORT", u, em, "PRESENT", False
                        )
                    )
            elif "customer_analytics_report" in str(path):
                profiles = data if isinstance(data, list) else data.get("profiles", [])
                for prof in profiles:
                    u = prof.get("customer_reference")
                    em = prof.get("email")
                    has_pii = bool(em or prof.get("phone") or prof.get("email_hash"))
                    st = "PRESENT" if has_pii else "ANONYMIZED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "analytics_platform", prof.get("resource_id"),
                            "ANALYTICS_PROFILE", u, em, st, has_pii
                        )
                    )
            elif "security_audit_ledger" in str(path):
                entries = data if isinstance(data, list) else data.get("records", [])
                for rec in entries:
                    u = rec.get("subject_reference") or rec.get("user_id")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "security_service", rec.get("resource_id"),
                            "SECURITY_AUDIT_LOG", u, None, "PRESENT", False
                        )
                    )
        except Exception as e:
            logger.debug("Failed parsing JSON %s: %s", path, e)

    def _parse_sql(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            conn = sqlite3.connect(":memory:")
            conn.executescript(open(path, "r", encoding="utf-8").read())
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]

            for tbl in tables:
                if tbl in ("snapshot_scope", "sqlite_sequence"):
                    continue
                cur.execute(f"SELECT * FROM {tbl}")
                cols = [c[0] for c in cur.description]
                for row in cur.fetchall():
                    rd = dict(zip(cols, row))
                    rid = rd.get("resource_id")
                    u = rd.get("customer_reference") or rd.get("subject_reference") or rd.get("user_id")
                    em = rd.get("email") or rd.get("requester_email") or rd.get("owner_email") or rd.get("customer_email")

                    tbl_l = tbl.lower()
                    if "profile" in tbl_l or "account" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "account_service", rid,
                                "USER_PROFILE", u, em, "PRESENT", False
                            )
                        )
                    elif "search" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "search_service", rid,
                                "SEARCH_INDEX_ENTRY", u, em, "PRESENT", False
                            )
                        )
                    elif "analytics" in tbl_l:
                        has_pii = bool(em or rd.get("phone") or rd.get("email_hash"))
                        st = "PRESENT" if has_pii else "ANONYMIZED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "analytics_platform", rid,
                                "ANALYTICS_PROFILE", u, em, st, has_pii
                            )
                        )
                    elif "support" in tbl_l or "ticket" in tbl_l:
                        has_pii = bool(em or rd.get("requester_name") or rd.get("requester_phone"))
                        st = "PRESENT" if has_pii else "REDACTED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "support_platform", rid,
                                "SUPPORT_MESSAGE", u, em, st, has_pii
                            )
                        )
                    elif "export" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "export_service", rid,
                                "USER_EXPORT", u, em, "PRESENT", False
                            )
                        )
                    elif "connector" in tbl_l:
                        st = "ACTIVE" if rd.get("enabled") in (1, True, "1", "true") else "DISABLED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "integration_service", rid,
                                "DATA_FLOW", u, em, st, False
                            )
                        )
                    elif "backup" in tbl_l:
                        st = "ACTIVE" if rd.get("restore_allowed") in (1, True, "1", "true") else "BLOCKED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "backup_service", rid,
                                "BACKUP_ARCHIVE", u, em, st, False
                            )
                        )
                    elif "security" in tbl_l or "audit" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "security_service", rid,
                                "SECURITY_AUDIT_LOG", u, em, "PRESENT", False
                            )
                        )
            conn.close()
        except Exception as e:
            logger.debug("Failed parsing SQL %s: %s", path, e)

    def _parse_log(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            # Map traces to identities
            trace_identities: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
            lines = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    tokens = dict(re.findall(r'(\w+)=(".*?"|\S+)', line))
                    tid = tokens.get("trace_id", "").strip('"')
                    u = (
                        tokens.get("subject_ref", "").strip('"')
                        or tokens.get("correlation_key", "").strip('"')
                        or tokens.get("customer_reference", "").strip('"')
                        or tokens.get("subject_reference", "").strip('"')
                    )
                    em = (
                        tokens.get("lookup_key", "").strip('"')
                        or tokens.get("match_key", "").strip('"')
                        or tokens.get("matched_value", "").strip('"')
                        or tokens.get("subject_key", "").strip('"')
                        or tokens.get("email", "").strip('"')
                    )
                    u = None if u in ("null", "") else u
                    em = None if em in ("null", "") else em
                    if u and u.startswith("user_"):
                        pass
                    elif u and "@" in u:
                        em, u = u, None

                    if tid:
                        cur_u, cur_em = trace_identities.get(tid, (None, None))
                        trace_identities[tid] = (u or cur_u, em or cur_em)

                    lines.append(tokens)

            # Re-process lines with resolved trace identities
            for tokens in lines:
                raw_sys_id = tokens.get("service")
                rid = tokens.get("resource_id", "").strip('"')
                tid = tokens.get("trace_id", "").strip('"')
                if not raw_sys_id or not rid or rid == "null":
                    continue

                # Normalize service name
                sys_id = raw_sys_id
                if "account" in raw_sys_id:
                    sys_id = "account_service"
                elif "support" in raw_sys_id:
                    sys_id = "support_platform"
                elif "search" in raw_sys_id:
                    sys_id = "search_service"
                elif "analytics" in raw_sys_id:
                    sys_id = "analytics_platform"
                elif "integration" in raw_sys_id or "connector" in raw_sys_id:
                    sys_id = "integration_service"
                elif "backup" in raw_sys_id:
                    sys_id = "backup_service"
                elif "security" in raw_sys_id:
                    sys_id = "security_service"

                u, em = trace_identities.get(tid, (None, None))
                # Also check inline tokens for email / user if not found in trace
                if not em:
                    inline_em = tokens.get("lookup_key", "").strip('"') or tokens.get("match_key", "").strip('"') or tokens.get("email", "").strip('"')
                    if inline_em and "@" in inline_em:
                        em = inline_em
                if not u:
                    inline_u = tokens.get("subject_ref", "").strip('"') or tokens.get("customer_reference", "").strip('"') or tokens.get("subject_reference", "").strip('"')
                    if inline_u and inline_u.startswith("user_"):
                        u = inline_u

                if sys_id == "account_service":
                    st = "ABSENT" if tokens.get("http_status") == "404" or tokens.get("rows") == "0" else "PRESENT"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "USER_PROFILE", u, em, st, False
                        )
                    )
                elif sys_id == "search_service":
                    st = "PRESENT" if tokens.get("result") == "hit" or tokens.get("total_hits") not in ("0", None) else "ABSENT"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SEARCH_INDEX_ENTRY", u, em, st, False
                        )
                    )
                elif sys_id == "analytics_platform":
                    has_pii = bool(em or tokens.get("phone") not in ("null", None))
                    st = "PRESENT" if has_pii else "ANONYMIZED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "ANALYTICS_PROFILE", u, em, st, has_pii
                        )
                    )
                elif sys_id == "support_platform":
                    marker_found = tokens.get("marker_found")
                    if marker_found == "false":
                        st = "PRESENT"
                        has_pii = False
                    else:
                        has_pii = bool(tokens.get("requester_email") not in ("null", None) or em)
                        st = "PRESENT" if has_pii else "REDACTED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SUPPORT_MESSAGE", u, em, st, has_pii
                        )
                    )
                elif sys_id == "integration_service":
                    en = tokens.get("enabled") == "true"
                    st = "ACTIVE" if en else "DISABLED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "DATA_FLOW", u, em, st, False
                        )
                    )
                elif sys_id == "backup_service":
                    allowed = tokens.get("restore_allowed") == "true"
                    st = "ACTIVE" if allowed else "BLOCKED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "BACKUP_ARCHIVE", u, em, st, False
                        )
                    )
                elif sys_id == "security_service":
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SECURITY_AUDIT_LOG", u, em, "PRESENT", False
                        )
                    )
        except Exception as e:
            logger.debug("Failed parsing log %s: %s", path, e)

    def _parse_txt(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("-") and "|" in line:
                        parts = [p.strip() for p in line.lstrip("-").split("|")]
                        if len(parts) >= 6:
                            sys_id = parts[1]
                            rid = parts[2]
                            cat = parts[3]
                            status_word = parts[4].upper()
                            ident = parts[5]
                            u = ident if ident.startswith("user_") else None
                            em = ident if "@" in ident else None

                            if status_word == "NOT_FOUND":
                                st = "ABSENT"
                                has_pii = False
                            elif status_word in ("IDENTIFIABLE", "ATTRIBUTABLE", "EXPOSED_PII"):
                                st = "PRESENT"
                                has_pii = True
                            elif status_word in ("FOUND", "PRESENT"):
                                st = "PRESENT"
                                has_pii = False
                            elif status_word == "ANONYMIZED":
                                st = "ANONYMIZED"
                                has_pii = False
                            elif status_word == "REDACTED":
                                st = "REDACTED"
                                has_pii = False
                            elif status_word == "ACTIVE":
                                st = "ACTIVE"
                                has_pii = False
                            elif status_word == "DISABLED":
                                st = "DISABLED"
                                has_pii = False
                            elif status_word == "BLOCKED":
                                st = "BLOCKED"
                                has_pii = False
                            else:
                                st = "PRESENT"
                                has_pii = False

                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, sys_id, rid, cat, u, em, st, has_pii
                                )
                            )
        except Exception as e:
            logger.debug("Failed parsing txt %s: %s", path, e)

    def _parse_pdf(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            chunks = parse_pdf_document(path)
            full_text = " ".join(chunks)

            # Extract resource_id
            rid_match = re.search(r"\b(support_\d+|export_\d+|audit_record_\d+|account_\d+)\b", full_text)
            rid = rid_match.group(1) if rid_match else None

            # Extract email
            em_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)
            em = em_match.group(0) if em_match else None

            # Extract user_id
            u_match = re.search(r"\b(user_\d+)\b", full_text)
            u = u_match.group(1) if u_match else None

            if rid:
                sys_id = "support_platform" if "support_" in rid else "account_service"
                cat = "SUPPORT_ATTACHMENT" if "support_" in rid else "USER_PROFILE"
                self._add_record(
                    EvidenceRecord(
                        file_id, captured_at, sys_id, rid, cat, u, em, "PRESENT", False
                    )
                )
        except Exception as e:
            logger.debug("Failed parsing PDF %s: %s", path, e)

    def find_records_for_subject(
        self,
        user_id: Optional[str],
        emails: Set[str],
        cutoff_time: datetime,
    ) -> List[EvidenceRecord]:
        """Returns all evidence records matching the user or any email up to cutoff_time."""
        matched = []
        user_lower_emails = {e.lower() for e in emails}

        if user_id and user_id in self._by_user:
            for r in self._by_user[user_id]:
                if r.captured_at <= cutoff_time:
                    matched.append(r)

        for em in user_lower_emails:
            if em in self._by_email:
                for r in self._by_email[em]:
                    if r.captured_at <= cutoff_time and r not in matched:
                        matched.append(r)

        return matched

    def find_records_by_resource_id(
        self,
        resource_id: str,
        cutoff_time: datetime,
    ) -> List[EvidenceRecord]:
        """Returns records for a specific resource_id up to cutoff_time."""
        if resource_id not in self._by_resource:
            return []
        return [r for r in self._by_resource[resource_id] if r.captured_at <= cutoff_time]
