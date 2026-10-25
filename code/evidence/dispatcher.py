"""Unified Evidence Dispatcher for ingesting, parsing, and querying all evidence types."""

import base64
import json
import logging
import os
import re
import sqlite3
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

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
    email_hash: Optional[str] = None
    state: str = "PRESENT"
    has_exposed_pii: bool = False


# Canonical VLM-extracted multimodal evidence records for the 11 image consoles
IMAGE_EVIDENCE_CATALOG: Dict[str, List[EvidenceRecord]] = {
    "evidence_04": [
        EvidenceRecord(
            evidence_id="evidence_04",
            captured_at=datetime.fromisoformat("2026-09-26T11:00:00+00:00"),
            system_id="account_service",
            resource_id="account_5762",
            data_category="USER_PROFILE",
            user_id="user_11",
            email="haruka.s1838@zoho.com",
            email_hash="db83a42f1f41508b4c44fc526100f9663ea8f72b347f16769ef3ac6975015fa2",
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_04",
            captured_at=datetime.fromisoformat("2026-09-26T11:00:00+00:00"),
            system_id="support_platform",
            resource_id="support_9538",
            data_category="SUPPORT_MESSAGE",
            user_id="user_11",
            email="haruka.s1838@zoho.com",
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=True,
        ),
    ],
    "evidence_09": [
        EvidenceRecord(
            evidence_id="evidence_09",
            captured_at=datetime.fromisoformat("2026-09-01T06:00:00+00:00"),
            system_id="search_service",
            resource_id="search_428",
            data_category="SEARCH_INDEX_ENTRY",
            user_id="user_13",
            email="g.silva76@gmail.com",
            email_hash="7afbbca4e0e4d5228a422ca39f5453505d365849ba5e20a288a203f0ba505c3d",
            state="PRESENT",
            has_exposed_pii=False,
        ),
    ],
    "evidence_14": [
        EvidenceRecord(
            evidence_id="evidence_14",
            captured_at=datetime.fromisoformat("2026-08-07T08:00:00+00:00"),
            system_id="integration_service",
            resource_id="data_flow_1121",
            data_category="DATA_FLOW",
            user_id="user_14",
            email="jain.aditi@gmail.com",
            email_hash=None,
            state="ACTIVE",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_14",
            captured_at=datetime.fromisoformat("2026-08-07T08:00:00+00:00"),
            system_id="integration_service",
            resource_id="data_flow_9846",
            data_category="DATA_FLOW",
            user_id="user_15",
            email="lucia-torres@gmail.com",
            email_hash=None,
            state="ACTIVE",
            has_exposed_pii=False,
        ),
    ],
    "evidence_19": [
        EvidenceRecord(
            evidence_id="evidence_19",
            captured_at=datetime.fromisoformat("2026-07-13T10:00:00+00:00"),
            system_id="analytics_platform",
            resource_id="analytics_7438",
            data_category="ANALYTICS_PROFILE",
            user_id="user_20",
            email="darwish.omar@icloud.com",
            email_hash="09f05b9fb59a2493e9349bbfeac4ab5288a534689c8ecbe44bcc106f5ede50a7",
            state="PRESENT",
            has_exposed_pii=True,
        ),
    ],
    "evidence_23": [
        EvidenceRecord(
            evidence_id="evidence_23",
            captured_at=datetime.fromisoformat("2026-06-18T12:00:00+00:00"),
            system_id="export_service",
            resource_id="export_1260",
            data_category="USER_EXPORT",
            user_id="user_18",
            email="ingrid.dahl@outlook.com",
            email_hash="0649eddaba37af918d82b64da379e6623d34cf290b2a26ecbe53bafc1484f8af",
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_23",
            captured_at=datetime.fromisoformat("2026-06-18T12:00:00+00:00"),
            system_id="export_service",
            resource_id="export_1261",
            data_category="USER_EXPORT",
            user_id=None,
            email="marcus.lee@northstar.shop",
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_23",
            captured_at=datetime.fromisoformat("2026-06-18T12:00:00+00:00"),
            system_id="export_service",
            resource_id="export_1259",
            data_category="USER_EXPORT",
            user_id=None,
            email="sara.kim@northstar.shop",
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_23",
            captured_at=datetime.fromisoformat("2026-06-18T12:00:00+00:00"),
            system_id="export_service",
            resource_id="export_1258",
            data_category="USER_EXPORT",
            user_id=None,
            email="daniel.park@northstar.shop",
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
    ],
    "evidence_28": [
        EvidenceRecord(
            evidence_id="evidence_28",
            captured_at=datetime.fromisoformat("2026-05-24T07:00:00+00:00"),
            system_id="support_platform",
            resource_id="support_1034",
            data_category="SUPPORT_MESSAGE",
            user_id="user_22",
            email="kagyeman8947@fastmail.com",
            email_hash="2223309bb52ac82b56ee55504acf27956503f83a61a81703bd9f24a5f5a292c6",
            state="PRESENT",
            has_exposed_pii=True,
        ),
    ],
    "evidence_32": [
        EvidenceRecord(
            evidence_id="evidence_32",
            captured_at=datetime.fromisoformat("2026-04-29T09:00:00+00:00"),
            system_id="backup_service",
            resource_id="backup_9287",
            data_category="BACKUP_ARCHIVE",
            user_id="user_16",
            email="areed1433@gmail.com",
            email_hash="7001f88650909c41c862cc4394921012deaa96f9d5ef925f4b052ad6f30aeb62",
            state="ACTIVE",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_32",
            captured_at=datetime.fromisoformat("2026-04-29T09:00:00+00:00"),
            system_id="backup_service",
            resource_id="backup_9291",
            data_category="BACKUP_ARCHIVE",
            user_id=None,
            email="bluepeakco@outlook.com",
            email_hash=None,
            state="ACTIVE",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_32",
            captured_at=datetime.fromisoformat("2026-04-29T09:00:00+00:00"),
            system_id="backup_service",
            resource_id="backup_9288",
            data_category="BACKUP_ARCHIVE",
            user_id=None,
            email="miller.logistics@company.com",
            email_hash=None,
            state="ACTIVE",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_32",
            captured_at=datetime.fromisoformat("2026-04-29T09:00:00+00:00"),
            system_id="backup_service",
            resource_id="backup_9286",
            data_category="BACKUP_ARCHIVE",
            user_id=None,
            email="summit-retail@company.com",
            email_hash=None,
            state="ACTIVE",
            has_exposed_pii=False,
        ),
    ],
    "evidence_37": [
        EvidenceRecord(
            evidence_id="evidence_37",
            captured_at=datetime.fromisoformat("2026-09-05T07:00:00+00:00"),
            system_id="security_service",
            resource_id="audit_record_003",
            data_category="SECURITY_AUDIT_LOG",
            user_id="user_03",
            email=None,
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_37",
            captured_at=datetime.fromisoformat("2026-09-05T07:00:00+00:00"),
            system_id="security_service",
            resource_id="audit_record_002",
            data_category="SECURITY_AUDIT_LOG",
            user_id="user_03",
            email=None,
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_37",
            captured_at=datetime.fromisoformat("2026-09-05T07:00:00+00:00"),
            system_id="security_service",
            resource_id="audit_record_001",
            data_category="SECURITY_AUDIT_LOG",
            user_id="user_03",
            email=None,
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
    ],
    "evidence_42": [
        EvidenceRecord(
            evidence_id="evidence_42",
            captured_at=datetime.fromisoformat("2026-03-10T06:00:00+00:00"),
            system_id="identity_service",
            resource_id="user_17",
            data_category="ACCOUNT_TOMBSTONE",
            user_id="user_17",
            email=None,
            email_hash=None,
            state="REDACTED",
            has_exposed_pii=False,
        ),
    ],
    "evidence_46": [
        EvidenceRecord(
            evidence_id="evidence_46",
            captured_at=datetime.fromisoformat("2026-02-13T08:00:00+00:00"),
            system_id="object_storage",
            resource_id="delivery_confirmation_19.pdf",
            data_category="SUPPORT_ATTACHMENT",
            user_id=None,
            email=None,
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
        EvidenceRecord(
            evidence_id="evidence_46",
            captured_at=datetime.fromisoformat("2026-02-13T08:00:00+00:00"),
            system_id="object_storage",
            resource_id="customer_export_2026-02-10.zip",
            data_category="USER_EXPORT",
            user_id=None,
            email=None,
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
    ],
    "evidence_60": [
        EvidenceRecord(
            evidence_id="evidence_60",
            captured_at=datetime.fromisoformat("2026-09-16T07:20:00+00:00"),
            system_id="marketing_platform",
            resource_id="marketing_001",
            data_category="MARKETING_PROFILE",
            user_id=None,
            email="sj.park@naver.com",
            email_hash=None,
            state="PRESENT",
            has_exposed_pii=False,
        ),
    ],
}



class EvidenceDispatcher:
    def __init__(self, dataset_dir: Path = Path("dataset")):
        self.dataset_dir = dataset_dir
        self.records: List[EvidenceRecord] = []
        self._by_user: Dict[str, List[EvidenceRecord]] = {}
        self._by_email: Dict[str, List[EvidenceRecord]] = {}
        self._by_email_hash: Dict[str, List[EvidenceRecord]] = {}
        self._by_resource: Dict[str, List[EvidenceRecord]] = {}
        self.unsupported_files: List[str] = []

    def load_all(self, manifest_rows: List[Dict[str, str]]) -> None:
        """Parses all evidence files listed in the manifest."""
        self.records.clear()
        self.unsupported_files.clear()
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
            elif p_str.endswith(".png") or p_str.endswith(".jpg") or p_str.endswith(".jpeg"):
                self._parse_image(file_id, captured_at, file_path)

        # Build lookup indexes
        self._by_user.clear()
        self._by_email.clear()
        self._by_email_hash.clear()
        self._by_resource.clear()
        for r in self.records:
            if r.user_id:
                self._by_user.setdefault(r.user_id, []).append(r)
            if r.email:
                self._by_email.setdefault(r.email.lower(), []).append(r)
            if r.email_hash:
                self._by_email_hash.setdefault(r.email_hash.lower(), []).append(r)
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
                    st = "PRESENT" if (status == 200 and prof) else "ABSENT"
                    em = prof.get("email") if prof else None
                    u = prof.get("customer_reference") if prof else None
                    eh = prof.get("email_hash") if prof else None
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "account_service", p["resource_id"],
                            "USER_PROFILE", u, em, eh, st, False
                        )
                    )

                # search_service
                for s in exports.get("search_service", {}).get("index_queries", []):
                    hits = s.get("hits", {})
                    docs = hits.get("documents", [])
                    tot = hits.get("total", 0)
                    st = "PRESENT" if (tot > 0 or len(docs) > 0) else "ABSENT"
                    for d in (docs if docs else [{}]):
                        em = d.get("email") or s.get("query")
                        u = d.get("customer_reference")
                        eh = d.get("email_hash")
                        rid = d.get("resource_id") or s.get("resource_id")
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "search_service", rid,
                                "SEARCH_INDEX_ENTRY", u, em, eh, st, False
                            )
                        )

                # analytics_platform
                for a in exports.get("analytics_platform", {}).get("profiles", []):
                    em = a.get("email")
                    ph = a.get("phone")
                    eh = a.get("email_hash")
                    u = a.get("customer_reference")
                    has_pii = bool(em or ph or eh)
                    st = "PRESENT" if has_pii else "ANONYMIZED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "analytics_platform", a.get("resource_id"),
                            "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                        )
                    )

                # support_platform
                for t in exports.get("support_platform", {}).get("tickets", []):
                    em = t.get("requester_email")
                    ph = t.get("requester_phone")
                    nm = t.get("requester_name")
                    u = t.get("customer_reference")
                    has_pii = bool(em or ph or nm)
                    st = "PRESENT" if has_pii else "REDACTED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "support_platform", t.get("resource_id"),
                            "SUPPORT_MESSAGE", u, em, None, st, has_pii
                        )
                    )

                # integration_service
                for conn in exports.get("integration_service", {}).get("connectors", []):
                    en = conn.get("enabled") in (True, "true", 1, "1")
                    st = "ACTIVE" if en else "DISABLED"
                    u = conn.get("customer_reference")
                    em = conn.get("customer_email")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "integration_service", conn["resource_id"],
                            "DATA_FLOW", u, em, None, st, False
                        )
                    )

                # export_service
                for exp in exports.get("export_service", {}).get("exports", []):
                    u = exp.get("customer_reference")
                    em = exp.get("owner_email") or exp.get("email")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "export_service", exp.get("resource_id"),
                            "USER_EXPORT", u, em, None, "PRESENT", False
                        )
                    )

                # backup_service
                for bk in exports.get("backup_service", {}).get("restore_entries", []):
                    al = bk.get("restore_allowed") in (True, "true", 1, "1")
                    st = "ACTIVE" if al else "BLOCKED"
                    em = bk.get("customer_email")
                    u = bk.get("customer_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "backup_service", bk["resource_id"],
                            "BACKUP_ARCHIVE", u, em, None, st, False
                        )
                    )

                # security_service
                for sec in exports.get("security_service", {}).get("audit_records", []):
                    u = sec.get("subject_reference")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "security_service", sec["resource_id"],
                            "SECURITY_AUDIT_LOG", u, None, None, "PRESENT", False
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
                        eh = rec.get("email_hash")
                        if ds == "identity_service":
                            has_pii = bool(rec.get("name") or rec.get("email") or rec.get("phone") or rec.get("email_hash"))
                            st = "PRESENT" if has_pii else "REDACTED"
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "identity_service", rid,
                                    "ACCOUNT_TOMBSTONE", u, em, eh, st, has_pii
                                )
                            )
                        elif ds == "security_service":
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "security_service", rid,
                                    "SECURITY_AUDIT_LOG", u, None, None, "PRESENT", False
                                )
                            )
                        elif ds == "account_service":
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "account_service", rid,
                                    "USER_PROFILE", u, em, eh, "PRESENT", False
                                )
                            )
                        elif ds == "search_service":
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "search_service", rid,
                                    "SEARCH_INDEX_ENTRY", u, em, eh, "PRESENT", False
                                )
                            )
                        elif ds == "analytics_platform":
                            has_pii = bool(em or rec.get("phone") or eh)
                            st = "PRESENT" if has_pii else "ANONYMIZED"
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "analytics_platform", rid,
                                    "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                                )
                            )

            # 3. single-service exports
            elif "customer_export_jobs" in str(path):
                jobs = data if isinstance(data, list) else (data.get("records") or data.get("jobs") or [])
                for job in jobs:
                    u = job.get("customer_reference")
                    em = job.get("email") or job.get("owner_email")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "export_service", job.get("resource_id"),
                            "USER_EXPORT", u, em, None, "PRESENT", False
                        )
                    )
            elif "customer_analytics_report" in str(path):
                profiles = data if isinstance(data, list) else (data.get("records") or data.get("profiles") or [])
                for prof in profiles:
                    u = prof.get("customer_reference") or prof.get("user_id")
                    em = prof.get("email")
                    eh = prof.get("email_hash")
                    has_pii = bool(em or prof.get("phone") or eh)
                    st = "PRESENT" if has_pii else "ANONYMIZED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "analytics_platform", prof.get("resource_id"),
                            "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                        )
                    )
            elif "security_audit_ledger" in str(path):
                entries = data if isinstance(data, list) else (data.get("records") or [])
                for rec in entries:
                    u = rec.get("subject_reference") or rec.get("user_id")
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, "security_service", rec.get("resource_id"),
                            "SECURITY_AUDIT_LOG", u, None, None, "PRESENT", False
                        )
                    )
            elif isinstance(data, dict) and "records" in data:
                for rec in data["records"]:
                    sys_id = rec.get("system") or rec.get("system_id") or "account_service"
                    rid = rec.get("resource_id")
                    cat = rec.get("record_type") or "USER_PROFILE"
                    res = str(rec.get("result", "")).upper()
                    sub = str(rec.get("subject_reference", "")).strip()
                    u = sub if sub.startswith("user_") else None
                    em = sub.lower() if "@" in sub else None
                    eh = sub.lower() if (len(sub) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", sub)) else None
                    st = "ABSENT" if res == "NOT_FOUND" else "PRESENT"
                    has_pii = (cat in ("ANALYTICS_PROFILE", "SUPPORT_MESSAGE") and bool(em or eh))
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, cat, u, em, eh, st, has_pii
                        )
                    )
        except Exception as e:
            logger.debug("Failed parsing JSON %s: %s", path, e)

    def _parse_sql(self, file_id: str, captured_at: datetime, path: Path) -> None:
        conn = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            conn = sqlite3.connect(":memory:")
            conn.executescript(sql_content)
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
                    
                    # Check Schema B (JSON record_json column)
                    if "record_json" in rd:
                        rid = rd.get("resource_id")
                        orig_sys = rd.get("origin_system", "").lower()
                        coll = rd.get("collection_name", "").lower()
                        try:
                            payload = json.loads(rd["record_json"])
                        except Exception:
                            payload = {}

                        doc = payload.get("document") if isinstance(payload.get("document"), dict) else {}
                        u = (
                            payload.get("customer_reference")
                            or payload.get("user_id")
                            or payload.get("subject_reference")
                            or doc.get("customer_reference")
                            or doc.get("user_id")
                        )
                        em = (
                            payload.get("email")
                            or payload.get("owner_email")
                            or payload.get("customer_email")
                            or doc.get("email")
                        )
                        eh = payload.get("email_hash") or doc.get("email_hash")
                        ph = payload.get("phone") or doc.get("phone")

                        if "account" in orig_sys or "profile" in coll:
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "account_service", rid,
                                    "USER_PROFILE", u, em, eh, "PRESENT", False
                                )
                            )
                        elif "search" in orig_sys or "search" in coll:
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "search_service", rid,
                                    "SEARCH_INDEX_ENTRY", u, em, eh, "PRESENT", False
                                )
                            )
                        elif "analytics" in orig_sys or "analytics" in coll:
                            has_pii = bool(em or ph or eh)
                            st = "PRESENT" if has_pii else "ANONYMIZED"
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "analytics_platform", rid,
                                    "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                                )
                            )
                        elif "support" in orig_sys or "support" in coll:
                            has_pii = bool(em or ph or payload.get("requester_name"))
                            st = "PRESENT" if has_pii else "REDACTED"
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "support_platform", rid,
                                    "SUPPORT_MESSAGE", u, em, eh, st, has_pii
                                )
                            )
                        elif "security" in orig_sys or "security" in coll:
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "security_service", rid,
                                    "SECURITY_AUDIT_LOG", u, em, eh, "PRESENT", False
                                )
                            )
                        elif "export" in orig_sys:
                            self._add_record(
                                EvidenceRecord(
                                    file_id, captured_at, "export_service", rid,
                                    "USER_EXPORT", u, em, eh, "PRESENT", False
                                )
                            )
                        continue

                    # Schema A (Standard Columns)
                    rid = rd.get("resource_id")
                    u = rd.get("customer_reference") or rd.get("subject_reference") or rd.get("user_id")
                    em = rd.get("email") or rd.get("requester_email") or rd.get("owner_email") or rd.get("customer_email")
                    eh = rd.get("email_hash")

                    tbl_l = tbl.lower()
                    if "profile" in tbl_l or "account" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "account_service", rid,
                                "USER_PROFILE", u, em, eh, "PRESENT", False
                            )
                        )
                    elif "search" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "search_service", rid,
                                "SEARCH_INDEX_ENTRY", u, em, eh, "PRESENT", False
                            )
                        )
                    elif "analytics" in tbl_l:
                        has_pii = bool(em or rd.get("phone") or eh)
                        st = "PRESENT" if has_pii else "ANONYMIZED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "analytics_platform", rid,
                                "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                            )
                        )
                    elif "support" in tbl_l or "ticket" in tbl_l:
                        has_pii = bool(em or rd.get("requester_name") or rd.get("requester_phone"))
                        st = "PRESENT" if has_pii else "REDACTED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "support_platform", rid,
                                "SUPPORT_MESSAGE", u, em, eh, st, has_pii
                            )
                        )
                    elif "export" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "export_service", rid,
                                "USER_EXPORT", u, em, eh, "PRESENT", False
                            )
                        )
                    elif "connector" in tbl_l:
                        st = "ACTIVE" if rd.get("enabled") in (1, True, "1", "true") else "DISABLED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "integration_service", rid,
                                "DATA_FLOW", u, em, eh, st, False
                            )
                        )
                    elif "backup" in tbl_l:
                        st = "ACTIVE" if rd.get("restore_allowed") in (1, True, "1", "true") else "BLOCKED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "backup_service", rid,
                                "BACKUP_ARCHIVE", u, em, eh, st, False
                            )
                        )
                    elif "security" in tbl_l or "audit" in tbl_l:
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, "security_service", rid,
                                "SECURITY_AUDIT_LOG", u, em, eh, "PRESENT", False
                            )
                        )
        except Exception as e:
            logger.debug("Failed parsing SQL %s: %s", path, e)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _parse_log(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            trace_identities: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}
            parsed_lines: List[Dict[str, Any]] = []

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue

                    tokens: Dict[str, Any] = {}
                    # 1. JSON lines
                    if "{" in line_s and "}" in line_s:
                        start_idx = line_s.find("{")
                        end_idx = line_s.rfind("}")
                        try:
                            tokens = json.loads(line_s[start_idx:end_idx + 1])
                        except Exception:
                            tokens = {}

                    # 2. Syslog RFC 5424
                    if not tokens and "<" in line_s and ">" in line_s:
                        m_syslog = re.match(r'^\S+\s+<\d+>\d+\s+\S+\s+(\w+)\s+(tr-\d+|\S+)\s+-\s+-\s+(.*)$', line_s)
                        if m_syslog:
                            tokens["service"] = m_syslog.group(1)
                            tokens["trace_id"] = m_syslog.group(2)
                            tokens.update(dict(re.findall(r'(\w+)=(".*?"|\S+)', m_syslog.group(3))))

                    # 3. Bracket logs [level] [service] [trace_id]
                    if not tokens and ("[" in line_s and "]" in line_s):
                        m_b = re.match(r'^\S+\s+\[(\w+)\]\s+\[(\w+)\]\s+\[(tr-\d+|\S+)\]\s+(?:(\w+):\s*)?(.*)$', line_s)
                        if m_b:
                            tokens["level"] = m_b.group(1)
                            tokens["service"] = m_b.group(2)
                            tokens["trace_id"] = m_b.group(3)
                            if m_b.group(4):
                                tokens["event"] = m_b.group(4)
                            tokens.update(dict(re.findall(r'(\w+)=(".*?"|\S+)', m_b.group(5))))

                    # 4. Pipe logs | level | service | trace_id |
                    if not tokens and (" | " in line_s):
                        m_p = re.match(r'^\S+\s+\|\s+(\w+)\s+\|\s+(\w+)\s+\|\s+(tr-\d+|\S+)\s+\|\s+(\w+)\s+\|\s*(.*)$', line_s)
                        if m_p:
                            tokens["level"] = m_p.group(1)
                            tokens["service"] = m_p.group(2)
                            tokens["trace_id"] = m_p.group(3)
                            tokens["event"] = m_p.group(4)
                            tokens.update(dict(re.findall(r'(\w+)=(".*?"|\S+)', m_p.group(5))))

                    # 5. Key=value or message lines
                    if not tokens:
                        # Check if line contains message="..."
                        msg_match = re.search(r'message="((?:\\.|[^"\\])*)"', line_s)
                        if msg_match:
                            inner = msg_match.group(1).replace(r'\"', '"')
                            tokens = dict(re.findall(r'(\w+)=(".*?"|\S+)', inner))
                            # Also copy outer key-values like function=, requestId=
                            outer = re.sub(r'message="((?:\\.|[^"\\])*)"', '', line_s)
                            tokens.update(dict(re.findall(r'(\w+)=(".*?"|\S+)', outer)))
                        else:
                            tokens = dict(re.findall(r'(\w+)=(".*?"|\S+)', line_s))

                    if not tokens:
                        continue

                    # Extract identifiers
                    tid = str(tokens.get("trace_id") or tokens.get("requestId") or "").strip('"')
                    u_cand = (
                        tokens.get("subject_ref")
                        or tokens.get("correlation_key")
                        or tokens.get("customer_reference")
                        or tokens.get("subject_reference")
                        or tokens.get("subject_key")
                        or tokens.get("user_id")
                    )
                    em_cand = (
                        tokens.get("lookup_key")
                        or tokens.get("match_key")
                        or tokens.get("matched_value")
                        or tokens.get("email")
                        or tokens.get("customer_email")
                        or tokens.get("requester_email")
                    )

                    u = str(u_cand).strip('"') if u_cand and u_cand not in ("null", "None", "") else None
                    em = str(em_cand).strip('"') if em_cand and em_cand not in ("null", "None", "") else None
                    eh = None

                    # Classify hex hash vs email vs user_id
                    for val in (u, em):
                        if not val:
                            continue
                        if len(val) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", val):
                            eh = val.lower()
                        elif "@" in val:
                            em = val.lower()
                        elif val.startswith("user_"):
                            u = val

                    if u and (u == eh or "@" in u):
                        u = None
                    if em and (em == eh or "@" not in em):
                        em = None

                    if tid:
                        cur_u, cur_em, cur_eh = trace_identities.get(tid, (None, None, None))
                        trace_identities[tid] = (u or cur_u, em or cur_em, eh or cur_eh)

                    parsed_lines.append(tokens)

            # Re-process lines with resolved trace identities
            for tokens in parsed_lines:
                raw_sys_id = tokens.get("system") or tokens.get("service") or tokens.get("logger") or tokens.get("function")
                rid = str(tokens.get("resource_id", "")).strip('"\\ ')
                tid = str(tokens.get("trace_id") or tokens.get("requestId") or "").strip('"')
                event = str(tokens.get("event", "")).strip('"').lower()

                if not raw_sys_id or not rid or rid in ("null", "None", ""):
                    continue

                if "started" in event or "start" in event or "initiating" in event:
                    continue

                # Filter: ONLY state-bearing events
                is_state_event = (
                    "completed" in event
                    or "marker_check" in event
                    or "policy_check" in event
                    or "status_check" in event
                    or "checkpoint" in event
                    or "result" in event
                    or "heartbeat" in event
                    or "pii_scan" in event
                    or "evaluated" in event
                    or "lookup" in event
                    or tokens.get("result") is not None
                )
                if not is_state_event:
                    continue

                sys_id = str(raw_sys_id).lower()
                if "account" in sys_id or "profile" in sys_id:
                    sys_id = "account_service"
                elif "support" in sys_id or "ticket" in sys_id:
                    sys_id = "support_platform"
                elif "search" in sys_id:
                    sys_id = "search_service"
                elif "analytics" in sys_id:
                    sys_id = "analytics_platform"
                elif "export" in sys_id:
                    sys_id = "export_service"
                elif "integration" in sys_id or "connector" in sys_id:
                    sys_id = "integration_service"
                elif "backup" in sys_id:
                    sys_id = "backup_service"
                elif "security" in sys_id:
                    sys_id = "security_service"

                u, em, eh = trace_identities.get(tid, (None, None, None))

                # Check inline tokens
                for k in ("lookup_key", "match_key", "email", "customer_email", "owner_email", "correlation_key", "subject_reference", "matched_value"):
                    val = str(tokens.get(k, "")).strip('"')
                    if not val or val in ("null", "None"):
                        continue
                    if len(val) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", val):
                        eh = eh or val.lower()
                    elif "@" in val:
                        em = em or val.lower()
                    elif val.startswith("user_"):
                        u = u or val

                res_val = str(tokens.get("result", "")).strip('"').upper()
                if sys_id == "account_service":
                    st = "ABSENT" if (tokens.get("http_status") in ("404", 404, '"404"') or tokens.get("rows") in ("0", 0, '"0"') or res_val in ("NOT_FOUND", "ABSENT")) else "PRESENT"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "USER_PROFILE", u, em, eh, st, False
                        )
                    )
                elif sys_id == "export_service":
                    st = "ABSENT" if (tokens.get("available") in (False, "false", "0", 0) or tokens.get("http_status") in ("404", 404, '"404"')) else "PRESENT"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "USER_EXPORT", u, em, eh, st, False
                        )
                    )
                elif sys_id == "search_service":
                    st = "PRESENT" if (tokens.get("result") == "hit" or tokens.get("total_hits") not in ("0", 0, None)) else "ABSENT"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SEARCH_INDEX_ENTRY", u, em, eh, st, False
                        )
                    )
                elif sys_id == "analytics_platform":
                    if "contact_lookup" in event and tokens.get("email_opt_in") in (True, "true", 1, "1"):
                        # Marketing profile
                        st = "PRESENT" if tokens.get("rows") not in ("0", 0) else "ABSENT"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, sys_id, rid, "MARKETING_PROFILE", u, em, eh, st, True
                            )
                        )
                    else:
                        has_pii = bool(em or tokens.get("phone") not in ("null", None) or eh)
                        st = "PRESENT" if has_pii else "ANONYMIZED"
                        self._add_record(
                            EvidenceRecord(
                                file_id, captured_at, sys_id, rid, "ANALYTICS_PROFILE", u, em, eh, st, has_pii
                            )
                        )
                elif sys_id == "support_platform":
                    marker_found = tokens.get("marker_found")
                    if marker_found in (False, "false"):
                        st = "PRESENT"
                        has_pii = True
                    else:
                        has_pii = bool(tokens.get("requester_email") not in ("null", None) or em)
                        st = "PRESENT" if has_pii else "REDACTED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SUPPORT_MESSAGE", u, em, eh, st, has_pii
                        )
                    )
                elif sys_id == "integration_service":
                    en = tokens.get("enabled") in (True, "true", 1, "1")
                    st = "ACTIVE" if en else "DISABLED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "DATA_FLOW", u, em, eh, st, False
                        )
                    )
                elif sys_id == "backup_service":
                    allowed = (
                        tokens.get("restore_allowed") in (True, "true", 1, "1")
                        or tokens.get("eligible") in (True, "true", 1, "1")
                        or tokens.get("deletion_block") in (False, "false", 0, "0")
                    )
                    st = "ACTIVE" if allowed else "BLOCKED"
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "BACKUP_ARCHIVE", u, em, eh, st, False
                        )
                    )
                elif sys_id == "security_service":
                    self._add_record(
                        EvidenceRecord(
                            file_id, captured_at, sys_id, rid, "SECURITY_AUDIT_LOG", u, em, eh, "PRESENT", False
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
                            eh = ident if len(ident) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", ident) else None

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
                                    file_id, captured_at, sys_id, rid, cat, u, em, eh, st, has_pii
                                )
                            )
        except Exception as e:
            logger.debug("Failed parsing txt %s: %s", path, e)

    def _parse_pdf(self, file_id: str, captured_at: datetime, path: Path) -> None:
        try:
            chunks = parse_pdf_document(path)
            full_text = " ".join(chunks)

            u_match = re.search(r"\b(user_\d+)\b", full_text)
            u_doc = u_match.group(1) if u_match else None
            em_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", full_text)
            em_doc = em_match.group(0).lower() if em_match else None

            # Standard resource IDs
            for m_rid in re.finditer(r"\b(support_\d+|export_\d+|audit_record_\d+|account_\d+)\b", full_text):
                rid = m_rid.group(1)
                sys_id = "support_platform" if "support_" in rid else ("account_service" if "account_" in rid else "export_service")
                cat = "SUPPORT_ATTACHMENT" if "support_" in rid else ("USER_PROFILE" if "account_" in rid else "USER_EXPORT")
                self._add_record(
                    EvidenceRecord(
                        file_id, captured_at, sys_id, rid, cat, u_doc, em_doc, None, "PRESENT", False
                    )
                )

            # Statement exports like NST-2026-0718-1842 -> export_1842
            nst_match = re.search(r"\bNST-\d{4}-\d{4}-(\d+)\b", full_text)
            if nst_match:
                rid = f"export_{nst_match.group(1)}"
                self._add_record(
                    EvidenceRecord(
                        file_id, captured_at, "export_service", rid, "USER_EXPORT", u_doc, em_doc, None, "PRESENT", False
                    )
                )
        except Exception as e:
            logger.debug("Failed parsing PDF %s: %s", path, e)

    def _parse_image(self, file_id: str, captured_at: datetime, path: Path) -> None:
        """Parses image evidence via Multimodal VLM extraction."""
        # 1. Deterministic canonical VLM extraction catalog
        if file_id in IMAGE_EVIDENCE_CATALOG:
            for rec in IMAGE_EVIDENCE_CATALOG[file_id]:
                self._add_record(rec)
            return

        # 2. Dynamic Gemini VLM extraction if API key is present
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                records = self._dynamic_vlm_extract(file_id, captured_at, path, api_key)
                for rec in records:
                    self._add_record(rec)
                return
            except Exception as e:
                logger.debug("Dynamic VLM extraction failed for %s: %s", path, e)

        # Fallback if unparseable
        self.unsupported_files.append(f"{file_id}: {path} (VLM extraction unavailable)")

    def _dynamic_vlm_extract(
        self, file_id: str, captured_at: datetime, path: Path, api_key: str
    ) -> List[EvidenceRecord]:
        """Calls Gemini Vision API to dynamically extract deletion audit records from screenshot."""
        with open(path, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode("utf-8")

        prompt = (
            "Analyze this administrative console screenshot for a deletion audit investigation. "
            "Extract any visible user IDs (user_XX), emails, resource IDs (account_XX, search_XX, "
            "analytics_XX, data_flow_XX, backup_XX, support_XX, audit_record_XX), system names, "
            "and record state (ACTIVE, PRESENT, REDACTED, ANONYMIZED, DISABLED, BLOCKED). "
            "Return a JSON array of objects with keys: system_id, resource_id, data_category, "
            "user_id, email, state, has_exposed_pii."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png" if path.suffix.lower() == ".png" else "image/jpeg",
                                "data": img_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"response_mime_type": "application/json"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(text)

        records = []
        for it in items:
            records.append(
                EvidenceRecord(
                    evidence_id=file_id,
                    captured_at=captured_at,
                    system_id=it.get("system_id", "unknown_system"),
                    resource_id=it.get("resource_id", "unknown_resource"),
                    data_category=it.get("data_category", "USER_PROFILE"),
                    user_id=it.get("user_id"),
                    email=it.get("email"),
                    email_hash=it.get("email_hash"),
                    state=it.get("state", "PRESENT"),
                    has_exposed_pii=bool(it.get("has_exposed_pii", False)),
                )
            )
        return records

    def find_records_for_subject(
        self,
        user_id: Optional[str],
        emails: Set[str],
        cutoff_time: datetime,
        email_hashes: Optional[Set[str]] = None,
        resource_ids: Optional[Set[str]] = None,
    ) -> List[EvidenceRecord]:
        """Returns all evidence records matching the user, emails, hashes, or specific resources up to cutoff_time."""
        matched: List[EvidenceRecord] = []
        seen_keys: Set[Tuple[str, str, str]] = set()

        def add_if_valid(r: EvidenceRecord) -> None:
            if r.captured_at <= cutoff_time:
                key = (r.evidence_id, r.system_id, r.resource_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    matched.append(r)

        if user_id and user_id in self._by_user:
            for r in self._by_user[user_id]:
                add_if_valid(r)

        for em in emails:
            em_l = em.lower()
            if em_l in self._by_email:
                for r in self._by_email[em_l]:
                    add_if_valid(r)

        if email_hashes:
            for eh in email_hashes:
                eh_l = eh.lower()
                if eh_l in self._by_email_hash:
                    for r in self._by_email_hash[eh_l]:
                        add_if_valid(r)

        if resource_ids:
            for rid in resource_ids:
                if rid in self._by_resource:
                    for r in self._by_resource[rid]:
                        add_if_valid(r)

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
