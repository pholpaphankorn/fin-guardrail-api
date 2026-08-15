# Synthetic Fixture Provenance

The two sample images in this directory were generated on 2026-08-15 with OpenAI's built-in image generation tool. They were created from text prompts without source or reference images and are not derived from customer, patient, or government records.

- `thai_id/synthetic_thai_id.png` uses a geometric avatar, a generic bird icon, an all-zero placeholder number, fictional labels, and prominent `SYNTHETIC` / `NOT VALID` watermarks.
- `thai_medical_receipt/synthetic_medical_receipt.png` uses a fictional clinic, `TEST PATIENT`, record `SYN-000`, synthetic line items, and prominent `SYNTHETIC` / `NOT REAL` watermarks.

The live extraction benchmark contains a byte-for-byte copy of the synthetic ID and matching fictional ground truth. The deterministic validator rejects the repeated-digit placeholder number even though its checksum arithmetic alone would otherwise match.

Do not replace these fixtures with real identity or medical documents. Build new cases from fictional data and document their provenance here.
