# Utility risk-screening reference comparison — synthetic evaluation only

**Research-only artifact:** `scripts/utility_validation.py` computes a confusion matrix and descriptive rates for the synthetic 3D proximity module. No physical inspection data, independently verified reference labels, operational accuracy or utility work order approvals are included.

## Inputs and integrity

- Screened geometry/position fixture: `fixtures/utility-clearance-3d-synthetic.json`.
- Separately declared *toy* truth labels: `fixtures/utility-validation-labels-synthetic.json`.
- A canonical SHA-256 of the screened JSON is required to bind labels to the exact input values; stale or altered inputs fail closed.
- Label IDs must match the full segment inventory exactly, with no unknown or duplicate identifiers, and every label is a boolean indicating a **fictional** inspection-needed classification.
- The reference input explicitly states `synthetic-only`, `unverified-fixture`, and `independent-synthetic-labels`. These are contract declarations, **not** evidence of an independent field inspector or data-origin authenticity.

## Output

The report contains true positives, false positives, true negatives and false negatives, plus:

- Recall/sensitivity = TP/(TP+FN).
- Specificity = TN/(TN+FP).
- Precision = TP/(TP+FP).
- False-negative rate = FN/(TP+FN).
- False-positive rate = FP/(FP+TN).

Undefined rates return JSON `null` rather than zero. Rates rounded to six decimal places are **descriptive statistics on tiny fictional fixtures**. They do not generalize to actual utility corridors. `independent_field_truth_verified=false`, `model_validated_for_operations=false`, and `decision=NOT_VALIDATED` are fixed.

Run locally (no network, customer data or external dependencies):

```bash
python -m unittest discover -s tests -p 'test_utility_validation.py' -v
python scripts/utility_validation.py fixtures/utility-clearance-3d-synthetic.json fixtures/utility-validation-labels-synthetic.json
```

A successful CLI exit indicates **only** that a synthetic comparison executed without data-contract failures; it does **not** mean a safe or operationally validated model.

## Independent field-validation acceptance gates

1. Independently sampled reference field observations with explicit time, surveyor/contractor verification, collection method, datum reconciliation and signed data-rights review. No sensitive infrastructure data in this public repository.
2. Adequate samples of actual positive/negative cases across asset types, weather, terrain and vegetation strata, with a holdout set isolated from development.
3. Prespecified safety-driven minimum recall and false-negative-rate thresholds approved by the qualified utility safety owner; meaningful uncertainty intervals and subgroup breakdowns; sensitivity to mislabeled truth and instrument error.
4. Demonstrated precision and economic work-order benefit using recorded costs, with review of unacceptable false-positive inspection loads.
5. Reproducible field evidence and explicit human authorization **before** any clearance recommendation or maintenance work-order system integration.

Source completeness, vertical calibration, conductor sag/temperature/wind, canopy interpolation and acquisition-date drift remain unsupported. Full production use is blocked independently of green synthetic CI.
