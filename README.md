# Fin-Guardrail API

A production-ready Automated Onboarding (KYC) & Claims Risk Gatekeeper Engine built with **FastAPI**. It combines **Multimodal Vision Models** with **Deterministic Python Guardrails** to automate the validation of Thai National IDs and itemized Medical Claim Receipts without relying on blind AI trust.

## 🚀 System Architecture Overview

This project employs a **Hybrid Verification Design Pattern** built for high reliability and financial risk compliance:
1. **Multimodal Visual Parser Layer:** Uses a Vision LLM combined with native **Pydantic Structural Outputs** to translate unstructured visual document frames into clean, structured JSON schemas.
2. **Deterministic Rules Engine:** Bypasses AI generation limits entirely by executing raw Python validation logic to double-check high-stakes rules (e.g., verifying date expirations via standard calendar libraries and checking itemized cost calculations down to decimal precision).
3. **Automated Risk Router:** Computes a continuous mathematical risk metric vector to dynamically assign transaction states: `APPROVED`, `FLAGGED_FOR_HUMAN_REVIEW`, or `REJECTED`.

## 🛠️ Folder Layout Architecture

```text
fin-guardrail-api/
├── app/
│   ├── main.py          # FastAPI web endpoint layer
│   ├── schemas.py       # Pydantic typing definitions (KYC & Claim profiles)
│   └── services/
│       ├── extractor.py # Vision LLM integration with text stripping
│       └── validator.py # Deterministic mathematical rule evaluations
├── scripts/
│   └── run_eval.py      # Automated performance suite regression runner
└── README.md            # Technical architecture writeup