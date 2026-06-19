# Agentic SWIFT Processing System

An AI-powered pipeline for processing, validating, and fraud-screening international bank payment messages (SWIFT MT103/MT202) using multi-agent patterns.

---

## Overview

This system simulates how a bank could use AI agents to automatically validate, detect fraud, and make compliance decisions on international wire transfers — replacing what would normally require multiple human analysts.

All LLM calls use **OpenAI GPT-4o**.

---

## Project Structure

```
project/
├── agents/
│   ├── evaluator_optimizer.py      # Step 1: Validate & correct messages
│   ├── parallelization.py          # Step 2: Parallel fraud detection
│   ├── prompt_chaining.py          # Step 3: Chain of compliance agents
│   ├── orchestrator_worker.py      # Step 4: Orchestrator-worker pattern
│   └── workflow_agents/
│       └── base_agents.py          # BaseAgent ABC + all fraud agent classes
├── audits/
│   └── explainability.jsonl        # Per-message audit log (one record per message)
├── models/
│   ├── bank.py                     # Bank entity model
│   └── swift_message.py            # SWIFT message Pydantic model
├── services/
│   ├── explainability_logger.py    # Explainability audit logger
│   ├── llm_service.py              # OpenAI integration service
│   └── swift_generator.py          # Fake SWIFT message generator
├── config.py                       # System configuration
├── main.py                         # Entry point — runs the full pipeline
└── generate_swift_messages.py      # Standalone message generator script
```

---

## Pipeline (4 Steps)

### Step 1 — Evaluator-Optimizer
- Generates SWIFT messages and validates them against SWIFT standards (BIC format, amount range, currency, reference length)
- If invalid, sends the message to GPT-4o (`SwiftCorrectionAgent`) to auto-correct errors
- Iterates up to 3 times until valid or marks as `INVALID`

### Step 2 — Parallelization (Fraud Detection)
Runs 3 fraud detection agents **simultaneously** on every message:

| Agent | What it checks |
|---|---|
| `FraudAmountDetectionAgent` | Large or suspiciously round amounts |
| `FraudPatternDetectionAgent` | BIC test patterns, suspicious keywords |
| `GeographicRiskAgent` | High/medium-risk country codes in BIC |

Results are aggregated by `FraudAggAgent` (threshold: 50% avg risk score) and each message is marked `FRAUDULENT` or `CLEAN`.

### Step 3 — Prompt Chaining
Passes messages through a chain of 5 AI agents in sequence, each building on the previous:

1. **InitialScreener** — Assigns GREEN / YELLOW / RED risk level
2. **TechnicalAnalyst** — Validates SWIFT format, BIC codes, reference patterns
3. **RiskAssessor** — Evaluates behavioral patterns and velocity
4. **ComplianceOfficer** — AML, sanctions, KYC, and regulatory checks
5. **FinalReviewer** — Makes final decision: `APPROVE`, `HOLD`, or `REJECT`

### Step 4 — Orchestrator-Worker
- An **Orchestrator** LLM analyzes the message batch and dynamically creates specific tasks
- **GenericAgent** workers execute each task (compliance checks, fraud investigations, summaries)
- Filters to high-value transactions (amount > $50,000) for this step

---

## Explainability Logging

Every run produces a structured audit trail in `audits/explainability.jsonl`. Each line is one JSON record representing the full processing history of a single message across all pipeline steps:

```json
{
  "run_id": "...",
  "message_id": "...",
  "timestamp": "...",
  "steps": {
    "evaluator_optimizer":  { "agent": "...", "decision": "VALID",   "output": {...} },
    "parallelization":      { "agent": "...", "decision": "CLEAN",   "output": {...} },
    "prompt_chaining": {
      "initial_screening":  { "agent": "InitialScreener",   "decision": "GREEN",   "output": {...} },
      "technical_analysis": { "agent": "TechnicalAnalyst",  "decision": "maintain","output": {...} },
      "risk_assessment":    { "agent": "RiskAssessor",      "decision": "batch-level", "output": {...} },
      "compliance_review":  { "agent": "ComplianceOfficer", "decision": "low",     "output": {...} },
      "final_review":       { "agent": "FinalReviewer",     "decision": "APPROVE", "output": {...} }
    }
  }
}
```

---

## Setup

### Prerequisites
- Python 3.11+
- OpenAI API key

### Install dependencies
```bash
pip install faker numpy openai pandas pydantic scipy
```

### Configure environment
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-api-key-here
```

### Run
```bash
export $(grep -v '^#' .env | xargs) && python main.py
```

---

## Configuration

Edit `config.py` to change system behaviour:

| Setting | Default | Description |
|---|---|---|
| `MESSAGE_COUNT` | `10` | Number of SWIFT messages to generate |
| `BANK_COUNT` | `5` | Number of banks in the registry |
| `MAX_WORKERS` | `8` | Max parallel threads for fraud detection |
| `OPENAI_MODEL` | `gpt-4o` | LLM model used for all AI calls |
