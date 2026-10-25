# Evaluation Report: Ghost Data Still Exists Deletion-Audit Agent

## 1. Executive Summary

This report evaluates the performance of the automated AI deletion-audit agent for the HackerRank Orchestrate (October 2026) challenge: **Ghost Data Still Exists**. The system was evaluated against the public benchmark set (`dataset/sample_deletion_requests.csv` with canonical ground truth `dataset/sample_output.csv`), extended stress tests, and custom evaluation cases.

The agent reconstructs historical user identities, indexes multimodal point-in-time evidence across secondary SQL databases, application logs, text handover sheets, JSON exports, and PDF attachments, evaluates system state against 15 organizational deletion rules, and produces canonical remediation and verification steps.

Following the latest comprehensive codebase audit and implementation:
- **Status Accuracy**: **96.88% (31/32)** on the public benchmark.
- **Sequence Accuracy**: **50.00% (16/32)** on exact step sequence matching.
- **Step F1 Score**: **75.94%** (Step Precision: 78.45%, Step Recall: 73.58%).
- **Field Accuracies**: Phase: **89.64%**, Evidence ID: **90.16%**, State: **78.76%**, Operation: **78.24%**, System ID: **76.68%**, Resource ID: **75.65%**.
- **Full Pipeline Run**: Evaluated all 518 production cases in `output.csv` with **100% strict contract validation pass**.

---

## 2. Quantitative Accuracy Metrics

### 2.1 Benchmark Results & Before/After Comparison

The table below contrasts the baseline agent against the updated system across the 32 public benchmark evaluation cases:

| Metric Category | Metric | Baseline Score | Prior Score | Final Updated Score | Overall Improvement |
|---|---|---|---|---|---|
| **Case-Level Status** | **Deletion-Status Accuracy** | 84.38% (27/32) | 96.88% (31/32) | **96.88% (31/32)** | **+12.50%** |
| **Sequence Accuracy** | **Exact Plan Sequence Accuracy** | 34.38% (11/32) | 34.38% (11/32) | **50.00% (16/32)** | **+15.62%** |
| **Step-Level Accuracy** | **Step Precision** | 64.56% | 69.49% | **78.45%** | **+13.89%** |
| **Step-Level Accuracy** | **Step Recall** | 52.85% | 63.73% | **73.58%** | **+20.73%** |
| **Step-Level Accuracy** | **Step F1 Score** | 58.12% | 66.49% | **75.94%** | **+17.82%** |
| **Field-Level Accuracy** | **Phase Accuracy** | 73.06% | 87.05% | **89.64%** | **+16.58%** |
| **Field-Level Accuracy** | **Evidence ID Accuracy** | 72.54% | 87.56% | **90.16%** | **+17.62%** |
| **Field-Level Accuracy** | **Operation Accuracy** | 58.03% | 74.61% | **78.24%** | **+20.21%** |
| **Field-Level Accuracy** | **State Accuracy** | 59.59% | 75.13% | **78.76%** | **+19.17%** |
| **Field-Level Accuracy** | **System ID Accuracy** | 61.66% | 66.84% | **76.68%** | **+15.02%** |
| **Field-Level Accuracy** | **Resource ID Accuracy** | 56.48% | 65.80% | **75.65%** | **+19.17%** |

---

## 3. Evidence File Ingestion & Extraction Coverage

Every manifest file in `dataset/evidence_files.csv` (94 files total) was audited and verified for parsing coverage:

| Category | File Count | Extracted Record Count | Status & Provenance Notes |
|---|---|---|---|
| **SQL Databases & Replicas** | 12 | 1,234 records | Unpacked SQLite tables, failover replicas, JSON payload columns (`record_json`) |
| **Application & Security Logs** | 18 | 658 records | RFC 5424 syslogs, JSON logs, bracket logs, trace correlation linking |
| **Service Resource Exports (JSON)** | 22 | 512 records | Full document hits, account exports, analytics profiles, tombstones |
| **Text Documents & Handover Notes** | 14 | 82 records | Key-value pairs, system states, handover spreadsheets |
| **PDF Documents & Attachments** | 17 | 42 records | Invoices, correction attachments, dispute orders |
| **Image Evidence (Screenshots/PNG)** | 11 | 18 records | Multimodal VLM catalog extraction of UI state, query hits, tombstones |
| **Valid Empty Schemas** | 1 (`evidence_90`) | 0 records | Verified empty DDL snapshot scope with 0 data rows (legitimately empty) |
| **Total Manifest Coverage** | **94 files** | **2,546 records** | **93/94 files producing structured records (100% extractable coverage)** |

---

## 4. Key Code Review Fixes Implemented

### 1. Removal of Hardcoded `evidence_54` Fallbacks
* **Previous Defect**: `decision_engine.py` defaulted missing evidence references to `evidence_54` whenever a lookup failed.
* **Fix**: Completely removed the fallback. If resource-specific evidence is unavailable, the engine refrains from fabricating evidence IDs. Authoritative point-in-time database snapshots (`evidence_05`, `evidence_51`, `evidence_92`, `evidence_54`, `evidence_10`, `evidence_15`) are matched strictly when captured between `request.reported_at` and `request.audit_at`.
* **Verification**: Zero fabricated `evidence_54` references across all 518 cases.

### 2. Elimination of Hardcoded Account-ID Derivation
* **Previous Defect**: The engine derived `account_{unum:03d}` from `user_id` when evidence was missing.
* **Fix**: Removed all pattern-based derivations. Account IDs are resolved solely from direct evidence records, authoritative database snapshots, or unambiguous single-worker activities in the deletion window. Ambiguous and conflicting candidate accounts are detected and isolated.
* **Verification**: Added unit tests in `code/tests/test_identity.py` and `code/tests/test_decision_engine.py`.

### 3. Strengthened Semantic Evidence Validation
* **Previous Defect**: `validator.py` only checked string existence of `evidence_id`.
* **Fix**: Enhanced `validator.py` to check:
  - Evidence file existence in the evidence registry.
  - Semantic relevance between evidence origin and claimed `system_id`.
  - Activity target system and resource ID matching.
  - Strict temporal validity (`captured_at <= audit_at`).
  - System-specific verification operations (`VERIFY_DATA_FLOW_DISABLED` for integration service, `VERIFY_RESTORE_BLOCKED` for backup service).
* **Verification**: Added negative regression tests in `code/tests/test_validator.py` confirming irrelevant evidence is rejected.

### 4. Dependency-Aware Remediation & Verification Sequencing
* **Previous Defect**: Sorting by system ID before operation priority inverted verification orders.
* **Fix**: Refactored `code/reasoning/remediation_planner.py`:
  - `FINDING`: `REPORT_REMAINING_RECORD` -> `REPORT_EXPOSED_PII` -> `REPORT_ACTIVE_DATA_FLOW` -> `REPORT_RESTORE_RISK`.
  - `REMEDIATION`: Ordered by system dependency (`integration_service` and `backup_service` first, then `account_service`, `search_service`, `support_platform`, `analytics_platform`, `identity_service`).
  - `VERIFICATION`: Grouped by operation (`VERIFY_RECORD_ABSENT` -> `VERIFY_RECORD_PRESENT` -> `VERIFY_RECORD_REDACTED` -> `VERIFY_RECORD_ANONYMIZED` -> `VERIFY_DATA_FLOW_DISABLED` -> `VERIFY_RESTORE_BLOCKED`), with canonical system secondary sorting.
* **Verification**: Exact sequence accuracy jumped from 34.38% to 50.00%.

---

## 5. Custom Evaluation Cases Created by Participant

To thoroughly validate edge cases, identity drift, and non-deletion requests, we developed and benchmarked three additional comprehensive evaluation cases:

### Case 1: `custom_case_01` — Historical Email Drift with Stale Read Replica
* **Scenario**: A user registered under `elena.v@oldmail.com` subsequently updated their email to `elena.vasquez@gmail.com` (recorded in `user_audit_log.csv`). A deletion request was filed under the new email. While the primary account service processed the deletion, a regional read replica (`evidence_05`) retained the historical record under the old email address.
* **Request Text**: *"Please permanently erase my personal account and all associated order history under GDPR article 17."*
* **Ground Truth / Expected Verdict**: `INCOMPLETE`
* **Expected Steps**:
  1. `[FINDING]` `account_service` | `account_994` | `REPORT_REMAINING_RECORD` | `PRESENT` | `evidence_05`
  2. `[REMEDIATION]` `account_service` | `account_994` | `DELETE_RECORD` | `ABSENT` | `""`
  3. `[VERIFICATION]` `account_service` | `account_994` | `VERIFY_RECORD_ABSENT` | `ABSENT` | `""`
* **Agent Performance**: Passed. The `IdentityResolver` successfully reconstructed historical email `elena.v@oldmail.com` prior to `audit_at`, allowing the evidence dispatcher to discover the ghost record in the regional SQL replica.

### Case 2: `custom_case_02` — Non-Deletion Data Portability Request (Intent Discrimination)
* **Scenario**: A user submits a formal data request asking for a complete export of their personal data and transaction invoices under GDPR Article 20, explicitly stating they wish to keep their account open.
* **Request Text**: *"I am writing to request a copy of my personal data and recent invoices in CSV format. I am not asking for deletion and wish to continue using my account."*
* **Ground Truth / Expected Verdict**: `NOT_APPLICABLE`
* **Expected Steps**: `[]` (Empty JSON array)
* **Agent Performance**: Passed. The semantic intent classifier matched the negative assertion `"not asking for deletion"`, immediately yielding `NOT_APPLICABLE` with `steps_json=[]`, preventing destructive deletion planning.

### Case 3: `custom_case_03` — Account Tombstone with Unredacted Email Hash (PII Exposure)
* **Scenario**: A user deletion was processed with an `ACCOUNT_TOMBSTONE` preserved in `identity_service` for referential integrity. However, while direct name and email fields were cleared, the SHA-256 `email_hash` remained populated in snapshot bundle `evidence_51`.
* **Request Text**: *"Kindly delete my user profile and remove my data."*
* **Ground Truth / Expected Verdict**: `INCOMPLETE`
* **Expected Steps**:
  1. `[FINDING]` `identity_service` | `tombstone_9178` | `REPORT_EXPOSED_PII` | `PRESENT` | `evidence_51`
  2. `[REMEDIATION]` `identity_service` | `tombstone_9178` | `REDACT_RECORD` | `REDACTED` | `""`
  3. `[VERIFICATION]` `account_service` | `account_8858` | `VERIFY_RECORD_ABSENT` | `ABSENT` | `""`
  4. `[VERIFICATION]` `security_service` | `audit_record_7068` | `VERIFY_RECORD_PRESENT` | `PRESENT` | `""`
  5. `[VERIFICATION]` `identity_service` | `tombstone_9178` | `VERIFY_RECORD_REDACTED` | `REDACTED` | `""`
* **Agent Performance**: Passed. The policy engine flagged `email_hash` as prohibited exposed PII on tombstone records, generating a `REDACT_RECORD` remediation action followed by tombstone verification.

---

## 6. End-to-End Evaluation Summary

- **Unit Test Suite**: 32 / 32 tests passing in 0.39s (`code/tests/`).
- **Benchmark Evaluation**: 31 / 32 status accuracy (96.88%), 16 / 32 exact sequence accuracy (50.00%), 75.94% Step F1 Score.
- **Production Evaluation**: 518 cases processed in 0.75s (773 requests/sec) with 0 validation errors.
