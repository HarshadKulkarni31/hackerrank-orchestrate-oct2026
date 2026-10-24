# Evaluation Report: Ghost Data Still Exists Deletion-Audit Agent

## 1. Executive Summary

This report evaluates the performance of the automated AI deletion-audit agent for the HackerRank Orchestrate (October 2026) challenge: **Ghost Data Still Exists**. The system was evaluated against the public benchmark set (`dataset/sample_deletion_requests.csv` with canonical ground truth `dataset/sample_output.csv`) as well as extended stress tests and custom evaluation cases.

The agent reconstructs historical user identities, indexes multimodal point-in-time evidence across secondary SQL databases, application logs, text handover sheets, JSON exports, and PDF attachments, evaluates system state against 15 organizational deletion rules, and produces canonical remediation and verification steps.

---

## 2. Quantitative Accuracy Metrics

The agent achieved the following metrics across the 32 benchmark evaluation cases:

| Metric Category | Metric | Score | Performance Details |
|---|---|---|---|
| **Case-Level Status** | **Deletion-Status Accuracy** | **84.38%** | 27 / 32 exact matches (`COMPLETE` vs. `INCOMPLETE` vs. `NOT_APPLICABLE`) |
| **Sequence Accuracy** | **Exact Plan Sequence Accuracy** | **34.38%** | 11 / 32 cases with 100% exact matching steps and ordering |
| **Step-Level Accuracy** | **Step Precision** | **64.56%** | Ratio of valid predicted steps to total proposed steps |
| **Step-Level Accuracy** | **Step Recall** | **52.85%** | Ratio of ground-truth steps discovered by the agent |
| **Step-Level Accuracy** | **Step F1 Score** | **58.12%** | Harmonic mean of step precision and recall |
| **Field-Level Accuracy** | **Phase Accuracy** | **73.06%** | Correct assignment of `FINDING`, `REMEDIATION`, and `VERIFICATION` |
| **Field-Level Accuracy** | **Evidence ID Accuracy** | **72.54%** | Grounded citation of participant-visible evidence vs. empty string |
| **Field-Level Accuracy** | **System ID Accuracy** | **61.66%** | Correct identification of affected subsystems |
| **Field-Level Accuracy** | **Resource ID Accuracy** | **56.48%** | Discovered resource identifier accuracy |
| **Field-Level Accuracy** | **Operation Accuracy** | **58.03%** | Canonical operation selection from allowed challenge actions |
| **Field-Level Accuracy** | **State Accuracy** | **59.59%** | Correct observed and target state assignment |

---

## 3. Custom Evaluation Cases Created by Participant

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
* **Agent Performance**: Passed. The regex and semantic intent classifier matched the negative assertion `"not asking for deletion"`, immediately yielding `NOT_APPLICABLE` and avoiding destructive deletion planning.

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

## 4. Failures Found and Iterative Improvements Made

During development and benchmarking, several structural failure modes were identified and iteratively resolved:

1. **PDF Decoding Failures on Binary Document Streams**:
   * *Failure*: Standard zlib decompression failed on PDF documents because streams used Adobe ASCII85 encoding without standard `<~` / `~>` delimiters and embedded raw newlines.
   * *Resolution*: Implemented a clean stream normalizer in pure Python using `base64.a85decode(clean, adobe=True)` with automatic fallback to raw zlib decompression, successfully recovering customer support requests from PDF attachments (e.g. `evidence_58`).

2. **Handover Record Keyword Inconsistency**:
   * *Failure*: Initial text log parsers checked for status keywords `FOUND` and `EXPOSED_PII`. The handover record file (`evidence_03`) used the status word `IDENTIFIABLE` for PII violations and `NOT_FOUND` for absent profiles.
   * *Resolution*: Expanded parser status vocabulary to recognize `IDENTIFIABLE` as `REPORT_EXPOSED_PII` and `NOT_FOUND` as verified `ABSENT`, immediately fixing all 14 steps in `case_11`.

3. **Over-Broad Temporal Activity Matching**:
   * *Failure*: Initial prototypes attempted to associate resources by matching any activity within a +/- 2-hour window of `reported_at`. This pulled in unrelated concurrent users' accounts from background worker batches.
   * *Resolution*: Restricted candidate selection to strict identity matching (current user ID, historical emails, and direct batch trace correlation), eliminating false-positive findings.

4. **Service Name Alias Collisions in System Logs**:
   * *Failure*: Observability logs recorded services as `support_replica` and `customer_search_primary` rather than canonical subsystem IDs `support_platform` and `search_service`.
   * *Resolution*: Built a subsystem normalizer mapping cluster replicas and pods to canonical platform system IDs.
