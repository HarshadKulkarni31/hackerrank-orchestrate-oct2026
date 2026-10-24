# Antigravity Implementation Blueprint

## HackerRank Orchestrate --- October 2026

### Problem: Ghost Data Still Exists

**Purpose:** Give Antigravity an end-to-end engineering specification
for implementing, evaluating, and packaging a strong solution to the
official challenge. This document is a build plan and execution brief,
not a claim that the solution has already been implemented or evaluated.

**Official repository:**
https://github.com/interviewstreet/hackerrank-orchestrate-october26\
**Official challenge/submission URL:**
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

------------------------------------------------------------------------

# 1. Mission and success criteria

Build a reproducible AI-assisted deletion-audit agent that reads the
participant-facing dataset, determines whether each request authorizes
deletion, reconstructs the subject's current and historical identities,
inspects evidence across systems, applies the supplied deletion policy
at the request's `audit_at` cutoff, and emits a correctly ordered,
evidence-grounded prediction for every row in
`dataset/deletion_requests.csv`.

The primary objective is **prediction correctness under the hidden
grader**, not building a visually impressive product at the expense of
the required CSV. The user also requests a UI, so include a lightweight
local audit workbench as a secondary diagnostic interface. The UI must
call the same core pipeline as the CLI; it must not contain a second
implementation of the decision logic.

## Definition of done

1.  Running the documented command from the repository root reads the
    participant-facing dataset and writes root-level `output.csv`.
2.  Output has exactly the columns `case_id,deletion_status,steps_json`,
    in that order.
3.  There is exactly one row for each of the 518 requests, sorted
    lexicographically by `case_id`.
4.  Every status is one of `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`.
5.  Every `steps_json` parses as a JSON array; step numbers start at 1
    and are consecutive.
6.  Every operation, phase, state, and field is valid under the official
    problem contract.
7.  `NOT_APPLICABLE` has `[]`; `COMPLETE` contains verification steps
    only; `INCOMPLETE` contains findings, a complete remediation plan,
    and planned verification.
8.  Evidence references are valid and support the corresponding finding
    or completed-state verification. Proposed remediation and future
    verification use `evidence_id: ""`.
9.  Public sample cases are run through the same pipeline and compared
    against `dataset/sample_output.csv`; differences are reported and
    analyzed rather than silently ignored.
10. `code/evaluation/evaluation_report.md` and
    `code/evaluation/usage_report.md` are present and contain real
    measurements from the final full run.
11. The repo's `AGENTS.md` instructions are followed, including
    append-only transcript logging to root `log.txt`.
12. `code.zip` contains the runnable code, README,
    prompts/configuration, and evaluation reports, but excludes
    `dataset/`, nested archives, virtual environments, caches, and
    secrets.
13. The solution can be explained clearly in the AI Judge interview:
    architecture, identity resolution, temporal reasoning, evidence
    extraction, policy engine, ordering, evaluation, failure modes,
    token use, and cost.

------------------------------------------------------------------------

# 2. Challenge contract: exact requirements to implement

## 2.1 Input data

The official dataset is under `dataset/`. The received CSVs were
inspected and had these shapes at planning time:

  -----------------------------------------------------------------------------------
  File                                           Observed shape Role
  -------------------------------- ---------------------------- ---------------------
  `deletion_requests.csv`                  518 rows × 7 columns Cases to predict

  `sample_deletion_requests.csv`            32 rows × 7 columns Public test cases

  `sample_output.csv`                       32 rows × 3 columns Correct public sample
                                                                outputs

  `user_identities.csv`                    850 rows × 6 columns Current identity
                                                                snapshot

  `user_audit_log.csv`                     306 rows × 6 columns Historical identity
                                                                changes

  `system_activity.csv`                  4,011 rows × 8 columns Global activity
                                                                stream

  `deletion_rules.csv`                      15 rows × 4 columns Policy source of
                                                                truth

  `evidence_files.csv`                      94 rows × 4 columns Evidence manifest

  `output.csv`                         Empty, 3-column template Schema reference
  -----------------------------------------------------------------------------------

Counts are dataset observations, not hardcoded assumptions. The
implementation must read the actual files and validate their schemas. Do
not hardcode sample answers, case labels, resource IDs, evidence IDs, or
a fixed number of cases into the decision logic.

Request columns:
`case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`

Identity columns: `user_id,name,email,phone,email_hash,updated_at`

Identity audit columns:
`audit_id,user_id,event_time,field_name,old_value,new_value`

Activity columns:
`activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`

Rules columns: `rule_id,data_category,condition,required_action`

Evidence manifest columns: `file_id,file_path,origin,captured_at`

## 2.2 Required status meanings

-   `NOT_APPLICABLE`: the request text does not authorize deletion.
    `steps_json` must be `[]`. Do not carry out or propose deletion
    verification for this status.
-   `COMPLETE`: the required treatment is already satisfied at
    `audit_at`; no prohibited data remains, no active process can
    recreate it, and required retained records remain available. Include
    only verification steps proving the current state.
-   `INCOMPLETE`: there is at least one evidence-supported policy
    violation, exposed identifier, or active recreation/restore risk.
    Include findings, the complete ordered remediation plan, and the
    verification checks that must pass afterward.

The existing workflow's `reported_status` and event `reported_result`
are claims, not ground truth. Reconstruct state using the evidence and
the time cutoff.

## 2.3 Required step schema

Each object must have exactly these fields:

``` json
{
  "step_no": 1,
  "phase": "FINDING",
  "system_id": "account_service",
  "resource_id": "account_005",
  "operation": "REPORT_REMAINING_RECORD",
  "state": "PRESENT",
  "evidence_id": "evidence_01"
}
```

Allowed phases: `FINDING`, `REMEDIATION`, `VERIFICATION`.

Allowed operations and states:

  Phase          Operation                     State
  -------------- ----------------------------- --------------
  FINDING        `REPORT_REMAINING_RECORD`     `PRESENT`
  FINDING        `REPORT_EXPOSED_PII`          `PRESENT`
  FINDING        `REPORT_ACTIVE_DATA_FLOW`     `ACTIVE`
  FINDING        `REPORT_RESTORE_RISK`         `ACTIVE`
  REMEDIATION    `DISABLE_DATA_FLOW`           `DISABLED`
  REMEDIATION    `BLOCK_RESTORE`               `BLOCKED`
  REMEDIATION    `DELETE_RECORD`               `ABSENT`
  REMEDIATION    `REDACT_RECORD`               `REDACTED`
  REMEDIATION    `ANONYMIZE_RECORD`            `ANONYMIZED`
  VERIFICATION   `VERIFY_RECORD_ABSENT`        `ABSENT`
  VERIFICATION   `VERIFY_RECORD_PRESENT`       `PRESENT`
  VERIFICATION   `VERIFY_RECORD_REDACTED`      `REDACTED`
  VERIFICATION   `VERIFY_RECORD_ANONYMIZED`    `ANONYMIZED`
  VERIFICATION   `VERIFY_DATA_FLOW_DISABLED`   `DISABLED`
  VERIFICATION   `VERIFY_RESTORE_BLOCKED`      `BLOCKED`

Do not add custom output fields, extra operations, or extra states.
Diagnostic explanations can be stored in internal reports and UI, but
not in the grader's step objects.

## 2.4 Ordering contract

Always order steps by phase: findings, remediation, verification. Within
each phase, use the operation order listed in the official problem
statement, then `system_id` ascending, then `resource_id` ascending. For
remediation, also respect dependencies: disable a recreating data flow
and block unsafe restores before modifying dependent records; process
downstream copies before upstream sources when the dependency requires
it. Reconcile dependency ordering with the canonical phase/operation
ordering contract; implement a deterministic, documented ordering
function rather than sorting ad hoc.

Assign `step_no` only after final ordering, consecutively from 1. Do not
rely on dictionary insertion order for array ordering.

## 2.5 Evidence citation contract

-   Findings and completed-state verification steps must cite a valid
    participant-visible `file_id`, `activity_id`, or `audit_id`.
-   For an `INCOMPLETE` case, proposed remediation and future
    verification steps use an empty string for `evidence_id`.
-   For `COMPLETE`, cite the evidence that establishes the state at
    `audit_at`; do not cite only a workflow claim.
-   The manifest connects `file_id` to `file_path`, `origin`, and
    `captured_at`; it does not itself prove a case-specific finding.
-   Do not cite an evidence item created after the case's `audit_at` to
    prove state at that earlier cutoff.
-   Preserve provenance internally: extraction result, source path,
    evidence ID, capture timestamp, matching identifier, and a short
    supporting excerpt or structured location. Do not put extra fields
    into the final output step schema.

------------------------------------------------------------------------

# 3. Policy rules that must be data-driven

Load `deletion_rules.csv` and apply it to every relevant record. Do not
duplicate the policy as scattered `if` statements. Implement a policy
resolver that takes data category, condition evidence, record state, and
audit cutoff and returns the required treatment.

The supplied rules are:

  ------------------------------------------------------------------------
  Data category            Condition               Required action
  ------------------------ ----------------------- -----------------------
  `USER_PROFILE`           Always                  DELETE

  `SECONDARY_IDENTIFIER`   Always                  DELETE

  `SEARCH_INDEX_ENTRY`     Always                  DELETE

  `CACHE_ENTRY`            Always                  DELETE

  `SUPPORT_MESSAGE`        Conversation contains   REDACT
                           shared customer, agent, 
                           or order context that   
                           must be retained        

  `SUPPORT_ATTACHMENT`     Attachment belongs only DELETE
                           to the deletion subject 

  `ANALYTICS_PROFILE`      Record is still         ANONYMIZE
                           attributable to a user  

  `PRODUCT_TELEMETRY`      Record is still         ANONYMIZE
                           attributable to a user  

  `USER_EXPORT`            Always                  DELETE

  `MARKETING_PROFILE`      Always                  DELETE

  `EMAIL_DELIVERY_LOG`     Log contains a user     REDACT
                           email address           

  `SECURITY_AUDIT_LOG`     Record is within the    RETAIN
                           supplied retention      
                           period                  

  `LEGAL_HOLD_RECORD`      A supplied legal hold   RETAIN
                           is active               

  `BACKUP_ARCHIVE`         Restore access can be   RETAIN
                           blocked                 

  `ACCOUNT_TOMBSTONE`      Deleted account needs a REDACT
                           stable internal user    
                           reference for retained  
                           records                 
  ------------------------------------------------------------------------

Important interpretations: - A tombstone may retain `user_id`, but
direct identifiers such as name, email, phone, and email hash must be
removed when the rule requires redaction. - A support message with
shared context may need to remain but have the subject's identifying
fields redacted. A subject-only attachment can be deleted. - Analytics
and telemetry should be anonymized when they remain attributable to the
subject; do not treat a stable internal user reference as safe if it
still makes the data linkable. - Retention is conditional. Determine the
supplied retention period or legal-hold state from evidence; do not
retain every record in a category blindly. - A retained backup is not
automatically a failure if policy permits retaining it and restore
access is safely blocked. The restore path itself must be assessed. -
Unknown or conflicting evidence must not be converted into an
unsupported certainty. Use a conservative internal uncertainty flag,
seek corroborating sources, and avoid inventing unsupported output
operations. The final status still must conform to the required enum, so
document the deterministic tie-breaking rule and test it.

------------------------------------------------------------------------

# 4. Recommended architecture

Use a Python-first solution because the starter repository explicitly
expects `code/main.py`, the data is CSV/SQL/text heavy, and Python has
strong parsing and evaluation libraries. Keep the design modular so the
UI and CLI share the same engine.

``` text
Repository root
├── AGENTS.md                       # Official instructions; read first
├── log.txt                         # Append-only AI transcript
├── dataset/                        # Local input corpus; never package into code.zip
├── output.csv                      # Final prediction file at repo root
├── README.md                       # Repo-level instructions if useful
└── code/
    ├── main.py                     # Required entry point
    ├── config.py                   # Paths, model settings, thresholds
    ├── schemas.py                  # Typed internal models and output enums
    ├── ingestion/
    │   ├── csv_loader.py
    │   ├── manifest.py
    │   └── evidence_inventory.py
    ├── identity/
    │   ├── resolver.py
    │   └── history.py
    ├── evidence/
    │   ├── dispatcher.py
    │   ├── parse_text_logs.py
    │   ├── parse_json.py
    │   ├── parse_sqlite.py
    │   ├── parse_pdf.py
    │   ├── parse_images.py
    │   ├── normalize.py
    │   └── retrieval.py
    ├── reasoning/
    │   ├── request_classifier.py
    │   ├── temporal_state.py
    │   ├── policy_engine.py
    │   ├── dependency_graph.py
    │   ├── decision_engine.py
    │   ├── remediation_planner.py
    │   └── evidence_ranker.py
    ├── output/
    │   ├── serializer.py
    │   └── validator.py
    ├── evaluation/
    │   ├── main.py
    │   ├── sample_diff.py
    │   ├── metrics.py
    │   ├── custom_cases.py
    │   ├── evaluation_report.md
    │   └── usage_report.md
    ├── ui/
    │   ├── app.py                  # Optional local diagnostic workbench
    │   └── components.py
    ├── prompts/
    │   ├── request_intent.md
    │   ├── evidence_extraction.md
    │   └── conflict_resolution.md
    ├── tests/
    │   ├── test_identity.py
    │   ├── test_temporal.py
    │   ├── test_policy.py
    │   ├── test_ordering.py
    │   ├── test_serialization.py
    │   └── test_samples.py
    ├── requirements.txt
    ├── .env.example                # Names only; no secrets
    └── README.md                   # Setup, run, architecture, evaluation
```

This is a suggested logical layout. Antigravity should adapt to the
starter files that actually exist rather than overwriting working
starter code unnecessarily. Keep the mandatory entry point at
`code/main.py`; keep evaluation reports at `code/evaluation/`.

## 4.1 Data flow

1.  Validate input files and load the manifest.
2.  Parse request intent to determine whether deletion is authorized.
3.  Resolve the supplied email to the subject's stable `user_id` using
    current identities and historical audit values.
4.  Reconstruct all current and historical identifiers available by the
    case's cutoff.
5.  Retrieve candidate evidence from global activity and evidence files
    using identifiers, hashes, resource IDs, system names, and time
    windows.
6.  Parse relevant evidence into normalized records with provenance and
    observed timestamps.
7.  Determine resource states at `audit_at`, accounting for event
    chronology, snapshot capture time, conflicting replicas, and later
    events.
8.  Map each record to a data category and apply the supplied policy.
9.  Identify active synchronization/import/indexing/export/restore paths
    that can recreate prohibited data.
10. Decide status and build the complete
    findings/remediation/verification plan.
11. Sort steps deterministically, assign step numbers, validate each
    step, and serialize `steps_json`.
12. Write root-level `output.csv`.
13. Run schema checks, sample comparisons, regression tests, and
    full-dataset metrics.
14. Write evaluation and usage reports.
15. Package only approved source and documentation files.

## 4.2 Design principle: deterministic core, AI-assisted extraction

Use an LLM for tasks that require language understanding, multilingual
request interpretation, or interpretation of messy unstructured
evidence. Use deterministic Python for timestamps, identity graph
construction, policy rules, operation/state enums, step ordering, schema
validation, and CSV serialization.

Do not send all evidence for all 518 cases to an LLM in one giant
prompt. That is expensive, hard to debug, risks context truncation, and
makes provenance unreliable. First use cheap deterministic retrieval to
narrow the evidence, then use targeted model calls only when required.

The agent should not perform real destructive actions against any
service. It produces a proposed audit/remediation plan for the
benchmark.

------------------------------------------------------------------------

# 5. Identity resolution and historical identifiers

Implement identity resolution before evidence search. The request's
email can be current or historical.

## Required logic

1.  Normalize emails using conservative whitespace/case normalization;
    do not invent fuzzy email equivalences.
2.  Match request email against `user_identities.csv`.
3.  Search `user_audit_log.csv` for historical `old_value` and
    `new_value` values where `field_name` is `email`, and resolve those
    values to `user_id`.
4.  Build a per-user identity timeline from the current snapshot and
    historical audit rows.
5.  Recover historical names, emails, phones, and hashes only when
    supported by supplied data.
6.  Preserve the time interval during which each identifier was valid
    where the event chronology allows it to be reconstructed.
7.  Include the stable `user_id` in the internal identity bundle; never
    assume it is itself a prohibited direct identifier in every data
    category.
8.  Detect ambiguity: if an email maps to multiple users or the history
    conflicts, record the ambiguity internally and search for additional
    corroboration instead of choosing arbitrarily.
9.  Search evidence using all relevant current and historical
    identifiers. Hashes should be matched only when the supplied hash
    algorithm/value is directly supported; do not generate a hash based
    on an assumed normalization algorithm.
10. Avoid logging or printing unnecessary personal data. Use IDs and
    redacted excerpts in diagnostic logs.

Internal representation suggestion:

``` python
IdentityBundle(
    user_id="user_...",
    request_email="...",
    current_identifiers={...},
    historical_identifiers=[...],
    identifier_validity=[...],
    identity_evidence=[...],
    ambiguity_flags=[...],
)
```

This is an internal model only; do not put it in `steps_json`.

------------------------------------------------------------------------

# 6. Evidence ingestion and retrieval

All 94 manifest entries must be discoverable through
`evidence_files.csv`. The observed archive includes: - 24 SQL database
snapshots; - 4 PDFs; - 11 images; - 26 logs; - 28 JSON records; - 1
plain-text record.

Validate these counts against the actual filesystem rather than
hardcoding them. The evidence is distributed among `databases/`,
`documents/`, `images/`, `logs/`, and `records/`.

## 6.1 Evidence manifest

Create an inventory index with: - `file_id`; - relative `file_path`; -
`origin`; - `captured_at`; - file exists/parse status; - file type; -
extracted text/structured records location; - extraction errors; -
source timestamp(s) found within the file, distinct from `captured_at`.

Fail clearly when manifest paths are missing or archive paths do not
match. Do not silently skip unreadable files.

## 6.2 Logs and plain text

-   Read with safe encoding fallback (`utf-8`, then a documented
    fallback such as `latin-1`).
-   Preserve original line numbers.
-   Parse ISO timestamps and resource identifiers where possible.
-   Index full text and extracted fields.
-   Search for current and historical identifiers, resource IDs, action
    names, source/target systems, and phrases indicating
    sync/restore/indexing state.
-   Do not trust strings such as `SUCCESS`, `COMPLETE`, or `deleted` as
    conclusive proof without matching the event to the actual resource
    and cutoff.

## 6.3 JSON records

-   Parse JSON structurally, recursively flattening nested fields while
    retaining the original JSON path.
-   Preserve array indices and resource boundaries.
-   Search identifiers and classify candidate records.
-   Store a compact excerpt or JSON path for auditability.
-   Distinguish capture time from event time and from the audit cutoff.

## 6.4 SQL snapshots

SQL captures are readable text and may be executable with SQLite. Treat
them as untrusted input files, not production databases.

-   Inspect schema, tables, columns, and row counts.
-   Load each snapshot into a separate temporary SQLite database or
    parse it safely; do not combine snapshots with conflicting schemas
    blindly.
-   Extract rows and map tables/columns to known categories using
    content and schema evidence.
-   Search all resolved identifiers, including old email/phone/hash
    values.
-   Track file path, snapshot/capture timestamp, table name,
    primary/resource ID, and matched field.
-   Compare primary, regional, reporting, read, and failover replicas to
    find replication drift.
-   Do not infer that the newest file is authoritative for a case if its
    capture time is after `audit_at`.
-   Do not treat a SQL `DELETE` event in a log as proof that every
    replica is clean.
-   Never execute arbitrary SQL against a production connection. Only
    process supplied local snapshots in an isolated, read-only or
    disposable environment.

## 6.5 PDFs and images

-   Extract PDF text with a suitable PDF parser.
-   For image-based/scanned PDFs, use OCR where available.
-   Extract text from PNG screenshots using OCR.
-   If OCR is unavailable, fail with a clear diagnostic and offer an
    optional OCR dependency; do not silently classify an unreadable
    image as clean.
-   For multimodal models, use only targeted images/pages when text
    extraction is insufficient and record provider/model, calls, token
    usage, and errors.
-   Capture page number, image filename, OCR text, confidence where
    available, and file ID.
-   Avoid sending unrelated personal data to external model APIs.

## 6.6 Retrieval strategy

Use a two-stage search: 1. Candidate generation with exact identifiers,
tokenized normalized text, resource IDs, and time filters. 2. Evidence
ranking by direct identity match, resource match, temporal relevance,
evidence type, and consistency with independent sources.

A good evidence ranking must not let a weak semantic similarity outrank
an exact identifier and matching resource. A result should be relevant
to both the subject and the resource/system being evaluated.

Create a cache keyed by file hash and parser version so reruns do not
re-extract unchanged evidence. Cache extracted evidence locally and
exclude caches from `code.zip`.

------------------------------------------------------------------------

# 7. Temporal reconstruction

The required question is: **what was the state at `audit_at`?** Not what
the system says now, and not what a later snapshot shows.

For each case: - parse `requested_at`, `reported_at`, `audit_at`,
evidence capture times, and event times as timezone-aware timestamps; -
only use state evidence available at or before `audit_at` to determine
the case's answer; - use identity audit history to search for historical
identifiers that may still appear in older resources; - reconstruct
state transitions from events, but treat event `reported_result` as a
claim unless corroborated; - compare the last relevant evidence before
the cutoff with later evidence only for diagnostics, never to backdate
future state; - handle missing timestamps conservatively and flag the
evidence as temporally uncertain; - distinguish record state from the
operation log that claims to have changed it; - check if a later
synchronization/import/restore could have recreated data before
`audit_at`; - inspect data flows active at the cutoff, not just flows
that exist in the dataset generally.

Create an internal state ledger such as:

``` text
subject_id | system_id | resource_id | category | observed_state
observed_at | evidence_id | identifier_match | source_confidence
state_before_cutoff | active_recreation_path | policy_action
```

Do not output this ledger in the CSV. It is a reasoning/evaluation
artifact.

------------------------------------------------------------------------

# 8. Request intent classification

The request text can be multilingual and may ask for non-deletion
actions. Classify whether the text authorizes deletion before auditing.

Suggested internal labels: - `DELETE_REQUEST` - `NON_DELETE_REQUEST` -
`AMBIGUOUS`

Do not treat account access, data export/access, correction, marketing
opt-out, or a generic support complaint as deletion unless the text
actually asks to erase/delete/close the account with personal-data
removal. Account closure language should be interpreted in context; when
it clearly requests closure and removal of associated personal data, it
authorizes deletion.

Implementation: 1. Use transparent deterministic rules for common clear
phrases. 2. Use a structured LLM classification call only for
multilingual or ambiguous requests. 3. Ask the model to return a strict
JSON object containing `intent`, `confidence`, `supporting_quote`, and
`language`. 4. Validate model output and reject unsupported labels. 5.
Never let the LLM invent evidence or decide record states based on
request wording. 6. For genuinely ambiguous cases, use a conservative
documented rule. Do not use `NOT_APPLICABLE` merely because the language
is non-English. 7. Compare classifier outcomes against the 32 public
samples and build custom tests for non-deletion, explicit deletion,
multilingual deletion, and ambiguous requests.

Keep prompts under `code/prompts/`. Avoid embedding sample output labels
as lookup rules or case-specific examples.

------------------------------------------------------------------------

# 9. Policy engine and record classification

For each candidate record, create a normalized `RecordAssessment`: -
subject identity match and matched identifiers; - system/resource ID; -
data category; - current state at `audit_at`; - direct PII fields
present; - linkability/attribution assessment; - retention period/legal
hold evidence; - restore-block capability and active restore paths; -
evidence IDs and timestamps; - required policy treatment; -
confidence/ambiguity flags.

Policy engine outputs only supported treatments: `DELETE`, `REDACT`,
`ANONYMIZE`, `RETAIN`. Any record whose category or policy condition
cannot be established should be marked internally as unresolved and
reviewed against more evidence; do not invent a new policy.

A record is a violation if its observed state does not satisfy the
applicable policy at `audit_at`. Examples: - `USER_PROFILE` still
present: deletion violation. - `SEARCH_INDEX_ENTRY` remains: deletion
violation. - `SUPPORT_MESSAGE` with required shared context still
present and direct identifiers exposed: redaction violation, not
necessarily deletion. - `ANALYTICS_PROFILE` still attributable:
anonymization violation. - `SECURITY_AUDIT_LOG` within retention period:
preserve it, but redact prohibited identifiers only if the
policy/evidence requires that treatment elsewhere. - Active legal hold:
retain the protected record. - `BACKUP_ARCHIVE`: retention may be
allowed when restore access is blocked; report active restore risk if
the backup can reintroduce deleted data. - `ACCOUNT_TOMBSTONE`: stable
`user_id` may remain; direct identifiers must not.

Do not apply one global action to all records. The same subject can have
multiple record categories with different required treatments.

------------------------------------------------------------------------

# 10. Data-flow and restore dependency graph

Build a graph from observed `system_activity.csv` events and evidence: -
nodes: source resources, target resources, systems, jobs, backups,
replicas, indexes, exports; - edges: sync, import, index, export,
replicate, backup, restore, copy; - edge attributes: source, target,
event time, active/disabled state, evidence reference, confidence.

For every prohibited surviving record, trace incoming active flows and
restore paths that could recreate it. If a data flow is active, the
remediation plan must disable it before removing downstream records that
it can repopulate. If a backup restore path can reintroduce data, block
the restore before final verification. Verify the data flow or restore
path separately using the corresponding verification operation.

Avoid false positives: an old historical sync event does not prove the
flow is still active at `audit_at`. Active status must be inferred from
the latest relevant evidence at or before the cutoff and corroborating
configuration/activity evidence.

------------------------------------------------------------------------

# 11. Decision engine and remediation planner

## 11.1 Decision logic

For each case: 1. Classify request intent. 2. If non-deletion, return
`NOT_APPLICABLE` and `[]`. 3. Resolve subject identity and historical
identifiers. 4. Build the complete candidate resource set from all
relevant evidence. 5. Exclude records that are unrelated to the subject
based on exact matching and corroboration. 6. Assess each record against
policy and time cutoff. 7. Assess active data flows and restore paths.
8. If any required treatment is unsatisfied or a recreation risk
remains, classify `INCOMPLETE`. 9. Otherwise classify `COMPLETE` and
generate verification-only steps that demonstrate the required state.
10. Validate completeness: no relevant resource or flow should remain
unexamined simply because the primary account record is absent.

Do not equate "no matches found" with "complete" unless the evidence
coverage is sufficient to support the required verification. The
evaluation output nevertheless requires a categorical status, so
establish a documented deterministic policy for incomplete/weak evidence
and use the available sources consistently.

## 11.2 Findings

For an `INCOMPLETE` case, include each supported finding: -
`REPORT_REMAINING_RECORD / PRESENT` for a record that should have been
deleted but remains; - `REPORT_EXPOSED_PII / PRESENT` for a surviving
record with identifiers that policy requires to be
redacted/anonymized; - `REPORT_ACTIVE_DATA_FLOW / ACTIVE` for a process
capable of recreating data; - `REPORT_RESTORE_RISK / ACTIVE` for a
backup/restore path capable of reintroducing prohibited data.

Do not emit a finding merely because an operation was attempted.
Findings must be supported by evidence and relevant to this subject and
the cutoff.

## 11.3 Remediation

Generate proposed actions from the policy violation and dependency
graph: - disable active flows; - block restore paths; - delete records
whose policy action is `DELETE`; - redact records whose policy action is
`REDACT`; - anonymize records whose policy action is `ANONYMIZE`; - do
not delete records whose policy action is `RETAIN`.

Use the exact allowed operation/state pair. Proposed remediation must
use `evidence_id: ""`. Do not invent a separate "action description"
field.

## 11.4 Verification

For `INCOMPLETE`, generate the verification checks that must pass after
the proposed remediation. The verification should cover every
remediation and every required retained record, not only the primary
account. Use empty evidence IDs for future checks.

For `COMPLETE`, include verification-only steps, and cite current-state
evidence IDs. Do not include findings or remediation steps. Include
checks appropriate to all relevant records, data flows, restore paths,
and required retained records.

For `NOT_APPLICABLE`, return `[]`.

## 11.5 Exact step ordering

Implement a single function that: 1. partitions steps by phase order; 2.
sorts each phase by the official operation order; 3. sorts ties by
`system_id`, then `resource_id`; 4. applies explicit dependency
constraints where required by the problem statement without
nondeterministic sorting; 5. assigns consecutive `step_no` values after
final ordering.

Create tests for repeated runs producing byte-stable `steps_json` for
the same input. If dependency constraints conflict with the canonical
operation sort, document and test the chosen interpretation based on the
official contract and sample outputs.

------------------------------------------------------------------------

# 12. Output generation and strict validation

The final output must be written to the repository root as `output.csv`,
not only to `dataset/output.csv`.

Use Python's `csv` module or pandas with correct quoting so commas and
quotes inside JSON are handled correctly. Use UTF-8. Preserve the exact
header order.

Create a validator that checks: - exact header and column order; - 518
output data rows (derive expected count from the input file rather than
hardcoding); - exactly one output row per input `case_id`, no
duplicates, no missing or extra IDs; - sorted `case_id`; - valid status
enum; - `steps_json` is valid JSON and an array; - every step object has
exactly the seven required keys; - consecutive integer step numbers
starting at 1; - phase/operation/state pairs are valid; - phase order is
correct; - operation and tie-break ordering are correct; -
`NOT_APPLICABLE` has an empty step array; - `COMPLETE` contains
verification steps only; - `INCOMPLETE` has findings, remediation, and
verification as required by the detected violations; - evidence
references for findings and complete verification are valid IDs from
allowed sources; - remediation and future verification evidence IDs are
empty strings; - no step uses an invented operation or state; - no
post-`audit_at` evidence is cited to prove earlier state.

The validator must fail loudly and identify the exact `case_id` and step
index. Never silently "repair" invalid output in a way that changes the
decision without recording it.

------------------------------------------------------------------------

# 13. Evaluation plan

The public `sample_output.csv` is a critical format and correctness
reference. Run all 32 sample cases through the exact same inference
pipeline. Do not build a special path that returns hardcoded sample
labels.

## 13.1 Sample evaluation

Report: - status accuracy; - exact-case match rate; - step count
precision/recall where meaningful; - field-level accuracy by `phase`,
`system_id`, `resource_id`, `operation`, `state`, `evidence_id`; -
ordered step sequence exact match; - valid JSON rate; - evidence
citation validity; - invalid operation/state rate; - time cutoff
violations; - policy violations in generated plans.

Because steps are lists, compare both: - exact sequence equality (order
matters); - multiset/field-level overlap (diagnostic only; not a
substitute for exact sequence scoring).

Normalize JSON object-key order for comparison but do not normalize away
array ordering or semantic differences.

## 13.2 Three or more custom cases

Create at least three new unit-level evaluation cases in Python
source/Markdown (not just a raw CSV file) and include them in
`evaluation_report.md`: 1. Non-deletion request must return
`NOT_APPLICABLE` and `[]`. 2. Current email differs from a historical
email that remains in a secondary record; identity resolution must
discover it. 3. An account tombstone remains with stable `user_id` but
direct identifiers must be redacted. 4. Optional additional cases:
active sync recreates deleted data; legal hold requires retention;
analytics record remains linkable; future evidence must not affect a
past cutoff; restore risk requires blocking before final verification.

Each case must define the expected behavior and what it tests. Do not
hardcode any of these test labels into the production case decision
logic.

## 13.3 Regression workflow

Suggested commands: -
`python code/main.py --input dataset/sample_deletion_requests.csv --output code/evaluation/sample_predictions.csv` -
`python code/evaluation/main.py --predictions code/evaluation/sample_predictions.csv --expected dataset/sample_output.csv` -
`python code/main.py` -
`python code/evaluation/main.py --predictions output.csv --expected dataset/sample_output.csv --full-dataset dataset/deletion_requests.csv`

Antigravity should implement a clean CLI argument interface; adapt
command names if needed, but document the final ones.

For the full hidden set, there is no ground-truth label available. Do
not claim hidden-test accuracy. Report structural validity, internal
consistency, sample performance, and manually audited case examples
separately.

## 13.4 Failure analysis and iteration

For every sample mismatch: 1. classify the failure: intent, identity,
retrieval, temporal state, policy, dependency, ordering, evidence
citation, serialization; 2. identify the source evidence needed to
decide the issue; 3. change the generic logic, not a one-off case
answer; 4. add a regression test; 5. rerun the entire sample suite; 6.
report before/after metrics.

Never tune production logic by inserting `case_01` or another fixed case
label. Do not use organizer-only truth, hidden answer files, or external
leakage.

------------------------------------------------------------------------

# 14. Token and cost accounting

Create a centralized model client wrapper so every call is logged
with: - timestamp; - provider; - exact model name; - purpose/task
type; - request/case identifier (use case ID only; avoid personal
data); - input tokens; - output tokens; - cached tokens if available; -
estimated cost based on configurable provider pricing; - latency; -
success/error and retry count.

Do not hardcode uncertain pricing as fact. Store pricing assumptions and
effective date in configuration/report. If the provider does not return
token usage, record it as estimated and explain the estimator.

`code/evaluation/usage_report.md` must describe the final full-dataset
run: - provider(s) and exact model names; - total model calls, grouped
by model and task; - total input and output tokens; - total tokens; -
average tokens per request across the 518 requests; - estimated total
and per-request cost; - per-model totals and overall totals if multiple
models are used; - caching and batching strategy; - missing usage data
or estimation limitations.

Count requests that use no model call in the per-request average
denominator, because the report describes the full 518-case run. Make
sure retries are included in call and cost totals.

Never place API keys or credentials in source files, prompts, `log.txt`,
README, or reports. Read secrets only from environment variables or an
uncommitted `.env`.

------------------------------------------------------------------------

# 15. Local UI / audit workbench (secondary feature)

The benchmark does not require a web UI, so implement this only after
the CLI, evidence processing, sample evaluation, and output validation
work. The UI is a diagnostic aid, not a replacement for root
`output.csv`.

Recommended minimal implementation: Streamlit in `code/ui/app.py`, or
another lightweight local UI if the repo already has one. Keep the
Python core importable and framework-independent.

## 15.1 Visual direction

-   Professional audit/security operations console.
-   Neutral background, high contrast, restrained color.
-   Use status labels with text, not color alone.
-   Dense data tables suitable for analysts; responsive layout.
-   Avoid unnecessary animations and decorative dashboards.
-   Show timestamps in UTC and label the timezone explicitly.
-   Avoid displaying full emails/phone numbers by default; provide
    masked values and an explicit reveal toggle for local debugging
    only.

## 15.2 Screens

### A. Overview

-   total requests loaded;
-   count by predicted status;
-   sample accuracy when sample evaluation has run;
-   invalid-output count;
-   evidence extraction success/failure count;
-   model calls, token totals, estimated cost;
-   latest run timestamp and output path.

### B. Case explorer

-   filter/search by case ID, status, reported status, or system;
-   case table with `case_id`, reported status, predicted status, audit
    cutoff, number of findings, number of remediation steps;
-   click a case to inspect the complete ordered plan;
-   clearly distinguish workflow-reported status from audited status.

### C. Case investigation

-   request text and intent classification;
-   resolved stable `user_id`;
-   current and historical identifiers, masked by default;
-   timeline of request, reported status, audit cutoff, and evidence
    timestamps;
-   findings with evidence source and short excerpt;
-   records grouped by system and data category;
-   policy rule applied and why;
-   active data-flow/restore graph;
-   remediation steps and corresponding verification;
-   warnings for ambiguous identity, missing evidence, or post-cutoff
    material.

### D. Evidence viewer

-   filter by evidence ID, file path, system, type, capture time,
    matched identifier;
-   show extracted text/JSON/SQL row snippets;
-   PDF page or image preview where possible;
-   source provenance and parser errors;
-   never edit the source evidence from the UI.

### E. Evaluation

-   sample comparison metrics;
-   exact-case and sequence match;
-   per-field mismatch table;
-   click mismatch to inspect expected vs predicted steps;
-   custom test results and regression history.

### F. Run controls

-   choose sample or full dataset;
-   configure optional model/provider using environment variables, not a
    UI field that stores secrets;
-   dry-run and validate-only modes;
-   display progress, failures, model usage and output file path;
-   prevent the UI from silently overwriting a previous output; ask for
    explicit confirmation or use timestamped intermediate runs before
    final promotion.

## 15.3 UI safety and scope

-   Never perform real deletion, redaction, anonymization, or restore
    blocking in external systems.
-   The UI displays a proposed plan only.
-   Do not expose credentials or raw environment variables.
-   Keep the UI optional and ensure `python code/main.py` works without
    Streamlit installed.
-   Do not include the UI's build caches or local evidence corpus in
    `code.zip`.

------------------------------------------------------------------------

# 16. Additional engineering features worth implementing

These are additions to improve reliability, auditability, and the AI
Judge explanation. They must not change the required output schema.

1.  **Evidence provenance ledger:** every extracted claim links to file
    ID, path, line/page/table/JSON path, timestamp, and matched
    identifier.
2.  **Temporal confidence flags:** flag missing, conflicting, or
    post-cutoff evidence internally.
3.  **Coverage report:** show which files were successfully parsed,
    partially parsed, or failed.
4.  **Dependency graph:** visualize active
    sync/import/index/export/restore paths.
5.  **Deterministic replay:** same inputs/configuration must produce the
    same output except for explicitly nondeterministic model calls;
    cache validated model results and record prompt/model versions.
6.  **Evidence cache:** skip unchanged files using SHA-256 file hashes
    and parser version.
7.  **Offline fallback:** if model API is unavailable, deterministic
    request rules and parsers should still run; unresolved cases must be
    flagged in diagnostics, not silently fabricated.
8.  **Structured LLM outputs:** validate JSON against schemas and retry
    only malformed responses with bounded retries.
9.  **PII minimization:** send only relevant snippets to external models
    and redact unrelated subjects.
10. **Reproducible configuration:** record runtime version, package
    versions, prompt version, model ID, and configuration flags in a run
    manifest without secrets.
11. **Failure quarantine:** write parse/model errors to a local
    diagnostics file outside final submission, with personal identifiers
    masked.
12. **Preflight command:** validate all required files and dependencies
    before an expensive full run.
13. **Output diff:** compare new output to previous run and report
    changed cases and reasons.
14. **Packaging audit:** programmatically inspect `code.zip` and fail if
    it contains `dataset/`, nested archives, `.env`, keys, caches, or
    virtual environments.
15. **AI Judge briefing:** generate a concise
    architecture/decision/evaluation summary in README for interview
    preparation.

Do not add features that consume the available time before the core
pipeline is accurate. Prioritize in this order: data correctness, sample
matching, complete output, reports, packaging, then UI polish.

------------------------------------------------------------------------

# 17. Security, privacy, and benchmark integrity

-   Use only participant-facing files under `dataset/`.
-   Never search for or use organizer-only golden answers or hidden
    evaluation artifacts.
-   Never hardcode labels or evidence IDs for specific cases.
-   Do not use external personal-data sources.
-   Treat the dataset and evidence as untrusted inputs.
-   Avoid sending whole datasets or unrelated PII to external APIs.
-   Keep all credentials out of source, logs, transcript, ZIP, and
    reports.
-   Do not include `dataset/` or evidence files in `code.zip`.
-   Do not modify supplied source evidence.
-   Use local, disposable storage for SQL processing.
-   Record model calls and estimated cost honestly.
-   Make no unsupported claims of 100% accuracy or hidden-test
    performance.

------------------------------------------------------------------------

# 18. Transcript logging and repository instructions

Before coding, Antigravity must: 1. Start from the repository root. 2.
Read `AGENTS.md` completely. 3. Follow its append-only `log.txt`
protocol. 4. Append the required `SESSION START` entry and per-turn
summaries. 5. Include exact authoritative harness and model identifiers
as required by `AGENTS.md`; never guess those values. 6. Never rewrite
old log entries. 7. Never log secrets or unnecessary real personal data.
8. Keep `log.txt` at repository root and submit it as `chat_transcript`.

If Antigravity cannot identify the exact runtime/tool/model names
required by the logging contract, it must inspect available runtime
metadata rather than inventing names. Do not claim the transcript is
compliant until it has been checked.

------------------------------------------------------------------------

# 19. Implementation phases and milestones

## Phase 0 --- Repository reconnaissance

-   Read `AGENTS.md`, README, and `problem_statement.md`.
-   Inspect the starter code and current repo state before editing.
-   Confirm actual dataset paths, dependencies, and output template.
-   Inventory all evidence and check manifest/path consistency.
-   Preserve existing useful starter code.

**Gate:** repo and dataset inventory is recorded; transcript logging
works.

## Phase 1 --- Schemas and baseline

-   Implement CSV loaders and schema validation.
-   Implement output step enums and serializer.
-   Implement output validator and sample diff tool.
-   Run the existing code, if any, before changing it; record baseline
    behavior.

**Gate:** CLI can read requests and produce structurally valid
placeholder/test outputs, but no fabricated predictions.

## Phase 2 --- Identity and request intent

-   Implement current/historical identity resolver.
-   Add multilingual deletion-intent classification.
-   Unit-test ambiguity, historical email, and non-deletion behavior.

**Gate:** identity resolution and intent decisions are explainable and
tested.

## Phase 3 --- Evidence ingestion

-   Implement parser dispatch for logs, JSON, SQL, PDFs, images, and
    text.
-   Build provenance-rich normalized evidence index.
-   Add cache and coverage/error report.
-   Verify each manifest file is accounted for.

**Gate:** parser coverage is measurable; unreadable files do not
silently disappear.

## Phase 4 --- Temporal state and policy

-   Implement time cutoff logic.
-   Implement record category classification and policy resolver.
-   Implement data-flow/restore graph.
-   Add tests for retention, legal hold, tombstones, anonymization,
    replicas, and future evidence.

**Gate:** each assessed record has evidence, cutoff-aware state, and a
policy treatment.

## Phase 5 --- Decision and remediation

-   Implement status decision engine.
-   Implement findings generation.
-   Implement dependency-aware remediation and verification generation.
-   Implement canonical ordering and step numbering.

**Gate:** generated plans use only allowed operations/states and satisfy
phase/order rules.

## Phase 6 --- Sample-driven evaluation

-   Run all 32 sample cases.
-   Compare every status and ordered step against `sample_output.csv`.
-   Inspect every mismatch and trace it to source evidence.
-   Fix generic reasoning/parser/order issues and add regression tests.
-   Repeat until the best achievable sample alignment is reached; report
    residual mismatches honestly.

**Gate:** evaluation report contains measured metrics and error
analysis.

## Phase 7 --- Full 518-case run

-   Run the same production pipeline over `deletion_requests.csv`.
-   Produce root-level `output.csv`.
-   Run strict structural, temporal, evidence, policy, and ordering
    checks.
-   Confirm row count, sorting, and one-to-one case coverage.
-   Do not skip difficult cases; record uncertainty and failures in
    diagnostics.

**Gate:** valid output is reproducible and all validator checks pass.

## Phase 8 --- Evaluation and usage reports

-   Write `code/evaluation/evaluation_report.md`.
-   Include case/status accuracy on the public samples,
    field/step/sequence metrics, at least three custom cases, failure
    analysis, and improvements.
-   Write `code/evaluation/usage_report.md` from actual model telemetry
    for the final full run.
-   Never invent token counts or pricing.

**Gate:** both reports are present and supported by run data.

## Phase 9 --- UI workbench

-   Only after the CLI pipeline and sample evaluation work.
-   Implement overview, case explorer, evidence viewer, evaluation page,
    and run controls.
-   Reuse the core engine; no duplicate logic.
-   Confirm the UI is optional.

**Gate:** UI can inspect a run and does not break CLI execution.

## Phase 10 --- Packaging and submission readiness

-   Update `code/README.md` with setup, run, test, evaluation, UI,
    environment configuration, and architecture.
-   Generate `code.zip` using the official exclusion rules.
-   Check ZIP contents programmatically.
-   Verify root `output.csv`.
-   Verify `log.txt`.
-   Confirm no secrets, dataset corpus, nested archives, virtual
    environments, or caches are packaged.
-   Prepare AI Judge talking points.

**Gate:** all deliverables are present and pass the preflight checklist.

------------------------------------------------------------------------

# 20. Final deliverables checklist

## Required by the challenge

-   [ ] Root `output.csv` with 518 predictions, exact header, sorted
    cases.
-   [ ] `code.zip` containing runnable code, prompts/configuration,
    README, and evaluation folder.
-   [ ] `code/evaluation/evaluation_report.md`.
-   [ ] `code/evaluation/usage_report.md`.
-   [ ] Root `log.txt` for the chat transcript.
-   [ ] Reproducible setup/run instructions.
-   [ ] No API keys, credentials, or sensitive configuration values.

## Quality checks

-   [ ] Public sample set run through production code.
-   [ ] Sample differences reviewed and explained.
-   [ ] At least three custom evaluation cases.
-   [ ] Correct current/historical identity mapping.
-   [ ] No post-cutoff evidence used as proof of earlier state.
-   [ ] Every policy-required record treatment checked.
-   [ ] Active sync/import/restore risks evaluated.
-   [ ] Tombstones preserve only permitted identifiers.
-   [ ] Retained security/legal records preserved when policy conditions
    apply.
-   [ ] Findings and complete verifications cite evidence.
-   [ ] Proposed remediation and future verification use empty evidence
    IDs.
-   [ ] Step order, operation/state pairs, and step numbers validated.
-   [ ] Repeat run is deterministic or all nondeterministic sources are
    logged.
-   [ ] Packaging audit passes.
-   [ ] AI Judge explanation is consistent with the actual
    implementation.

------------------------------------------------------------------------

# 21. Ready-to-paste master instruction for Antigravity

Paste the following into Antigravity after opening the official
repository as the workspace. Launch Antigravity from the repository root
so it can read `AGENTS.md` and maintain `log.txt`.

> You are the lead engineer implementing HackerRank Orchestrate October
> 2026, problem "Ghost Data Still Exists," in this repository.
>
> **First read `AGENTS.md`, `README.md`, and `problem_statement.md`
> completely. Follow `AGENTS.md` exactly, including append-only root
> `log.txt` session and turn logging. Do not guess harness/model names
> required by the log. Inspect the existing starter code and preserve
> useful work.**
>
> Implement the complete solution described in
> `ANTIGRAVITY_IMPLEMENTATION_PLAN.md` (this plan should be placed at
> the repository root before execution, or the instructions can be
> pasted directly if the file is not present). The official problem
> statement, README, and AGENTS.md are the source of truth if any detail
> conflicts with this plan.
>
> Prioritize the grader contract above optional UI features. Use a
> modular Python implementation with `code/main.py` as the entry point
> unless the starter repository has a compelling existing design that
> already satisfies the contract. Read only participant-facing data
> under `dataset/`. Never use organizer-only truth, hardcode case
> labels, or hardcode evidence IDs as answers.
>
> Build the pipeline in this order: 1. Repository/data preflight and
> input schema validation. 2. Identity resolution using current
> identities and historical audit values. 3. Request-intent
> classification, including multilingual deletion requests and
> non-deletion requests. 4. Evidence ingestion for logs, JSON,
> SQLite-compatible SQL snapshots, PDFs, images/OCR, and text. 5.
> Evidence provenance and retrieval with time-aware matching. 6.
> Temporal state reconstruction at each `audit_at`. 7. Data-driven
> policy engine based on `deletion_rules.csv`. 8. Active
> sync/import/replication/index/export and backup/restore risk analysis.
> 9. Deterministic status decision, findings, complete remediation plan,
> and verification plan. 10. Strict operation/state validation,
> canonical ordering, and output serialization. 11. Public sample
> evaluation, mismatch analysis, and regression tests. 12. Full 518-case
> run and strict preflight. 13. Real token/cost telemetry and the two
> required evaluation reports. 14. Optional local audit UI, only after
> the core solution works. 15. Packaging audit and interview
> preparation.
>
> Do not assume reported workflow statuses or event results are true.
> Resolve current and historical identifiers. Do not use evidence
> captured after `audit_at` to prove a prior state. Apply retention,
> legal hold, support-message redaction, analytics/telemetry
> anonymization, backup restore blocking, and tombstone rules precisely.
> Do not delete retained records. Proposed remediation must not execute
> against external services; only produce the prescribed plan.
>
> Final `output.csv` must be at repository root and have exactly
> `case_id,deletion_status,steps_json`, one row per request in sorted
> order. `steps_json` must use only the exact allowed fields, phases,
> operations, and states from `problem_statement.md`. `NOT_APPLICABLE`
> uses `[]`; `COMPLETE` has verification steps only; `INCOMPLETE`
> includes findings, remediation, and future verification. Findings and
> completed-state verification cite valid evidence; proposed remediation
> and future verification use an empty `evidence_id`. Order steps
> according to the official contract and assign consecutive step numbers
> after sorting.
>
> Compare all 32 sample predictions against `dataset/sample_output.csv`.
> Do not special-case sample IDs. Diagnose every mismatch, fix general
> logic, add regression tests, and rerun. Then process all requests,
> validate all output invariants, and report structural quality
> honestly. Do not claim hidden-set accuracy because hidden labels are
> unavailable.
>
> Create `code/evaluation/evaluation_report.md` with
> status/case/field/step/sequence metrics, at least three custom test
> cases, failures, and improvements. Create
> `code/evaluation/usage_report.md` from actual telemetry with
> provider/model names, calls, input/output/total tokens, average tokens
> per request, and estimated total/per-request costs. Never fabricate
> metrics or token counts.
>
> Implement the optional local UI as a diagnostic workbench only after
> the CLI, evaluation, and output generation are reliable. It should
> show overview metrics, case explorer, evidence provenance, policy
> treatment, timelines, data-flow/restore risks, and sample mismatches.
> The UI must reuse the core engine and must not be required for CLI
> execution.
>
> Before finishing, run all tests, run the full pipeline, validate the
> root output, inspect `log.txt`, write the README and reports, package
> `code.zip` without `dataset/`, evidence files, nested archives,
> virtual environments, caches, or secrets, and verify the archive
> contents. Report exactly what is complete, what remains uncertain, the
> final metrics, and the commands to reproduce the result. If blocked,
> continue with all independent work possible and report the concrete
> blocker rather than stopping after planning.
>
> Work incrementally and actually edit/run/test the project. Do not
> respond with another plan in place of implementation.

------------------------------------------------------------------------

# 22. Final note

The UI and added engineering features are optional enhancements. The
highest-value work is correct identity resolution, evidence linkage,
temporal reconstruction, policy application, ordered steps, and
sample-driven evaluation. The final solution should be compact enough to
run reproducibly, explainable enough for the AI Judge, and strict enough
that malformed JSON or invalid evidence references cannot slip into the
submission.
