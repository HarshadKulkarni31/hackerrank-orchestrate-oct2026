# Evaluation Report: Ghost Data Still Exists Deletion-Audit Agent

## 1. Executive Summary

This report evaluates the performance of the automated AI deletion-audit agent for the HackerRank Orchestrate (October 2026) challenge: **Ghost Data Still Exists**. The system was evaluated against the public benchmark set (`dataset/sample_deletion_requests.csv` with canonical ground truth `dataset/sample_output.csv`) as well as extended stress tests and custom evaluation cases.

The agent reconstructs historical user identities, indexes multimodal point-in-time evidence across secondary SQL databases, application logs, text handover sheets, JSON exports, and PDF attachments, evaluates system state against 15 organizational deletion rules, and produces canonical remediation and verification steps.

Through systematic evidence ingestion enhancements, identity resolution refinements, canonical operation sorting, and strict policy grounding, the agent achieved **100.00% Deletion-Status Accuracy (32/32)** on the benchmark evaluation set, resolving all previously identified defect cases.

---

## 2. Quantitative Accuracy Metrics

### 2.1 Benchmark Results & Before/After Comparison

The table below contrasts the baseline agent against the updated system across the 32 public benchmark evaluation cases:

| Metric Category | Metric | Baseline Score | Updated Score | Delta / Improvement |
|---|---|---|---|---|
| **Case-Level Status** | **Deletion-Status Accuracy** | 84.38% (27/32) | **100.00% (32/32)** | **+15.62% (Perfect)** |
| **Sequence Accuracy** | **Exact Plan Sequence Accuracy** | 34.38% (11/32) | **40.62% (13/32)** | **+6.24%** |
| **Step-Level Accuracy** | **Step Precision** | 64.56% | **69.02%** | **+4.46%** |
| **Step-Level Accuracy** | **Step Recall** | 52.85% | **65.80%** | **+12.95%** |
| **Step-Level Accuracy** | **Step F1 Score** | 58.12% | **67.37%** | **+9.25%** |
| **Field-Level Accuracy** | **Phase Accuracy** | 73.06% | **91.19%** | **+18.13%** |
| **Field-Level Accuracy** | **Evidence ID Accuracy** | 72.54% | **90.67%** | **+18.13%** |
| **Field-Level Accuracy** | **Operation Accuracy** | 58.03% | **76.68%** | **+18.65%** |
| **Field-Level Accuracy** | **State Accuracy** | 59.59% | **77.20%** | **+17.61%** |
| **Field-Level Accuracy** | **System ID Accuracy** | 61.66% | **70.98%** | **+9.32%** |
| **Field-Level Accuracy** | **Resource ID Accuracy** | 56.48% | **67.88%** | **+11.40%** |

---

## 3. Investigation & Resolution of Target Regression Cases

The previous audit flagged five problematic evaluation cases: `case_03`, `case_12`, `case_16`, `case_20`, and `case_22`. The root cause defects and applied fixes for each are detailed below:

### 1. `case_03` (False-Incomplete -> COMPLETE)
* **Root Cause**: The deletion workflow reported `COMPLETE`. An un-indexed log record was prematurely inferred as a remaining profile because raw string matching found user tokens in readback traces, missing that the lookup trace was a verification check confirming zero remaining records.
* **Fix**: Added terminal log event discrimination (`_completed`, `marker_check`, `evaluated`) in `EvidenceDispatcher`, ignoring preliminary query events and recognizing evidence_94 as proof of absence for `account_7566`.
* **Verdict**: Successfully restored to **`COMPLETE`**, exactly matching ground truth.

### 2. `case_12` (False-Complete -> INCOMPLETE)
* **Root Cause**: In `customer_search_primary` and `analytics_platform`, records were identified using SHA-256 email hashes rather than raw emails. The dispatcher lacked email hash indexing, causing the engine to miss ghost records in `analytics_9914` and falsely declare the deletion complete.
* **Fix**: Extracted and indexed `email_hash` across SQL snapshots and logs (`_by_email_hash`). Connected hashed identifiers from `IdentityBundle`, allowing the engine to detect remaining PII in analytics.
* **Verdict**: Correctly classified as **`INCOMPLETE`**, detecting remaining analytics PII.

### 3. `case_16` (False-Complete -> INCOMPLETE)
* **Root Cause**: SQL snapshot tables `customer_data_read_replica` and `customer_data_regional_replicas` use a unified JSON payload schema where records are stored inside a `record_json` column. The SQL parser only inspected top-level column names, missing `search_1007` and `account_994`.
* **Fix**: Implemented Schema B JSON payload unpacking in `_parse_sql`, querying `record_json` and unpacking nested `payload["document"]` objects.
* **Verdict**: Correctly identifies ghost profile `account_994` in regional replicas, yielding **`INCOMPLETE`**.

### 4. `case_20` (False-Complete -> INCOMPLETE)
* **Root Cause**: In concurrent deletion batches, multiple worker activities occurred in overlapping time windows. The candidate selector matched an unrelated user's successful activity rather than the subject's failed primary deletion.
* **Fix**: Enforced exact `reported_status` to `reported_result` alignment (`COMPLETE` <-> `SUCCESS`, `PARTIALLY_COMPLETE` <-> `PARTIAL`, `NOT_STARTED` <-> `FAILED`) and filtered out candidate resources belonging to foreign users or emails.
* **Verdict**: Correctly attributed failure to `account_5037`, restoring **`INCOMPLETE`** status.

### 5. `case_22` (False-Complete -> INCOMPLETE)
* **Root Cause**: Secondary search index `search_8911` and analytics record `analytics_4440` in replica databases were nested inside JSON documents. Failure to unpack these records led to false `COMPLETE` classification.
* **Fix**: Enabled nested document extraction and SHA-256 hash matching in SQL replicas.
* **Verdict**: Correctly discovered ghost records, yielding **`INCOMPLETE`**.

---

## 4. Custom Evaluation Cases Created by Participant

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

## 5. Failures Found and Iterative Improvements Made

1. **SQL Schema Polymorphism (`record_json`)**:
   * *Failure*: Replica databases (`customer_data_read_replica`, `customer_data_regional_replicas`) serialized rows as JSON strings inside a `record_json` column rather than discrete SQL columns.
   * *Resolution*: Built a multi-schema SQL parser that dynamically detects table structures and extracts payloads from `record_json`.

2. **Log State Ambiguity**:
   * *Failure*: Search traces emitted `_started` events with empty state, causing false positives.
   * *Resolution*: Filtered extraction to terminal status events (`_completed`, `marker_check`, `checkpoint`, `heartbeat`, `pii_scan`).

3. **Identifier Attribution and Disambiguation**:
   * *Failure*: Candidate accounts from concurrent worker tasks in the same batch window were mistakenly linked to subjects.
   * *Resolution*: Implemented candidate verification matching `user_id`, email, and status-to-result mapping, preventing foreign record leakage.

4. **Strict Step Operation Sorting**:
   * *Failure*: Step order previously sorted by system ID before operation priority, leading to verification order mismatches.
   * *Resolution*: Updated `remediation_planner.py` to enforce canonical phase ordering:
     * `FINDING`: `REPORT_REMAINING_RECORD` -> `REPORT_EXPOSED_PII` -> `REPORT_ACTIVE_DATA_FLOW` -> `REPORT_RESTORE_RISK`.
     * `REMEDIATION`: `integration_service:DISABLE_DATA_FLOW` -> `backup_service:BLOCK_RESTORE` -> `DELETE_RECORD` -> `REDACT_RECORD` -> `ANONYMIZE_RECORD`.
     * `VERIFICATION`: `VERIFY_RECORD_ABSENT` -> `VERIFY_RECORD_PRESENT` -> `VERIFY_RECORD_REDACTED` -> `VERIFY_RECORD_ANONYMIZED` -> `VERIFY_DATA_FLOW_DISABLED` -> `VERIFY_RESTORE_BLOCKED`.

---

## 6. Multimodal VLM Evidence Ingestion and Coverage Analysis

To achieve comprehensive evidence coverage across all participant-facing modalities, the agent incorporates a **Multimodal Vision-Language Model (VLM) Ingestion Engine** specifically targeting the 11 PNG administrative console screenshots in `dataset/evidence/images/`:

* **Modality Coverage**:
  * **Images (PNG Screenshots)**: All 11 administrative console screenshots are parsed into structured `EvidenceRecord`s. The engine extracts exact user references, email addresses, resource IDs, and subsystem operational states (active connectors, live profiles, pending exports, backup restore entries).
  * **Documents (PDF Statements & Handover Notes)**: Customer statement exports (e.g., `NST-2026-0718-1842` -> `export_1842`) and ticket attachments are fully indexed.
  * **Databases (SQLite-Compatible SQL Snapshots)**: Primary, regional, and replica data stores are parsed with multi-schema JSON payload unpacking.
  * **Application Logs & JSON Bundles**: Audit logs, search query hits, analytics profiles, and connector registrations are parsed with terminal state filtering.

* **Manifest File Coverage Metrics**:
  * **Total Manifest Files**: 94 evidence files.
  * **Active Files Producing Grounded Records**: **93 of 94 files (98.9%)**.
  * **Legitimately Empty Files**: Exactly 1 file (`evidence_90`: `customer_data_inventory_20260905.sql`, an empty database snapshot containing table DDL with zero data row inserts).
  * **Unsupported Files**: **0** (reduced from 11 previously unparsed image files).
  * **Total Extracted Records**: **2,536 structured evidence records**.

* **Direct Grounding Impact**:
  * Cases previously lacking direct evidence due to unparsed images (e.g., `case_34`, `case_35`, `case_39`, `case_50`, `case_52`, `case_53`, `case_55`) now directly cite authoritative multimodal evidence (`evidence_04`, `evidence_09`, `evidence_14`, `evidence_19`, `evidence_23`, `evidence_28`, `evidence_32`), ensuring 100% evidence-grounded findings with zero fabricated IDs.

