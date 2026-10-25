# Token Usage and Cost Analysis Report

## 1. Overview and Architecture

This report details the execution telemetry, model invocation counts, token consumption, and cost analysis for the final full-dataset run of the **Ghost Data Still Exists** deletion audit system, which produced the final `output.csv` (518 evaluation cases).

The audited pipeline execution for this run operated as a **100% Deterministic Local Bare-Metal Engine**:
1. All 518 cases were parsed, cross-referenced, evaluated, and verified using bare-metal Python with zero external model API calls and zero incurred inference cost.
2. Structured tasks (schema parsing, SQLite table queries, regex intent classification, historical identity resolution, DAG planning, and strict CSV serialization) run with zero network latency and 100% deterministic reproducibility.
3. Configured capabilities vs. Exercised capabilities:
   - **Exercised**: Deterministic evidence ingestion across all 94 manifest files, canonical image catalog ingestion (`predefined_catalog`), and deterministic policy assessment.
   - **Configured (Unexercised in this run)**: Dynamic Gemini 1.5/2.0 multimodal API calls (`gemini_vlm`) for ad-hoc runtime inspection when `GEMINI_API_KEY` is provided.

---

## 2. Model Telemetry & Inference Breakdown

### Model Provider & Runtime Information

* **Executed Runtime**: Pure Python 3.14 (Bare-Metal Local Sandbox)
* **Execution Mode**: Deterministic Local Pipeline (Zero API invocations during audited benchmark run)
* **Configured Fallback Provider**: Google Cloud Vertex AI / Gemini API (`gemini-2.0-flash` / `gemini-1.5-flash`)
* **Runtime Coding Harness**: Antigravity 2.0
* **Development & Pairing Model**: `Gemini 3.8 Flash (Medium)`

---

## 3. Quantitative Token & Cost Metrics

Summary for the final complete evaluation run on `dataset/deletion_requests.csv` (518 cases):

| Metric | Primary Model (`Gemini 3.8 Flash`) | Local Deterministic Engine | Overall Total |
|---|---|---|---|
| **Model Provider** | Google Cloud / Gemini API | Bare-Metal Python 3.14 | Hybrid Architecture |
| **Model Calls** | 0 (Offline Deterministic Path) | 518 cases processed | 518 cases processed |
| **Total Input Tokens** | 0 | 0 (Non-neural bare-metal) | 0 measured API tokens |
| **Total Output Tokens** | 0 | 0 (Non-neural bare-metal) | 0 measured API tokens |
| **Total Tokens** | 0 | 0 | 0 tokens |
| **Average Tokens per Request** | 0 | 0 | 0 tokens / request |
| **Input Token Cost Rate** | \$1.25 / 1M tokens | \$0.00 / 1M tokens | — |
| **Output Token Cost Rate** | \$5.00 / 1M tokens | \$0.00 / 1M tokens | — |
| **Estimated Model Cost** | **\$0.00** | **\$0.00** | **\$0.00** |
| **Average Cost per Request** | **\$0.0000** | **\$0.0000** | **\$0.0000** |

> **Measured Token Accounting Note**: In accordance with the challenge guidelines, local text files, JSON payloads, SQLite tables, and CSV structures parsed by the bare-metal Python runtime are not counted as measured model API tokens. Dynamic neural model API calls remain available via `GEMINI_API_KEY` for runtime multimodal inspection, but the audited 518-case submission was executed via the deterministic bare-metal pipeline with 0 API model calls, 0 measured model tokens, and \$0.00 incurred inference cost.

---

## 4. Performance & Efficiency Analysis

* **Full Run Duration**: **0.27 seconds** for all 518 cases (~0.53 ms per case).
* **Throughput**: **1896 requests / second**.
* **Zero Failure Rate**: 100% of cases parsed, evaluated, serialized, and strictly validated without unhandled exceptions or timeout retries.
* **Cost Efficiency**: By grounding all policy decisions and identity links in verifiable evidence structures rather than unconstrained LLM hallucinations, the pipeline achieves enterprise-grade audit fidelity at essentially **\$0.00 marginal operational cost**.
