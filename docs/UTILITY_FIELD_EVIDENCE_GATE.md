# Utility field-evidence acceptance packet — pre-production gate

**This is a metadata checklist, not field-truth verification or an operational permit.** The CLI `scripts/utility_field_evidence_gate.py` creates a deterministic decision-support packet from a local JSON file. It cannot authenticate signatures, inspect referenced documents, test physical clearances, establish utility safety, or authorize deployment.

## Inputs and controls

- `schema_version=1`, `scope=field-evidence-packet-proposal`, `release_approved=false`, and an opaque project identifier are required.
- Every evidence category needs a document ID, SHA-256 digest, review-date metadata, and an explicit reviewed boolean. The categories are horizontal datum, vertical datum, field observation method, conductor sag, canopy sampling, temporal alignment and source data rights.
- Evaluation references require immutable hashes of the model, source dataset and independently labeled dataset.
- Development and holdout segment inventories must be nonempty, unique and **disjoint**, with explicit blinded holdout-after-model-freeze assertions. A shared or missing segment fails closed.
- Independent reference-review metadata, safety-threshold review, field calibration, subgroup-error analysis and false-negative review must be complete before the **packet itself** can be designated structurally complete.
- A qualified independent utility reviewer role is required as a **metadata assertion**, not proof of credentials, signature or consent.

The output always includes `evidence_authenticity_verified=false`, `field_accuracy_established=false`, `operational_use_approved=false`, `work_order_authorized=false`, and `human_approval_required=true`, even when all metadata are populated. A complete packet returns `PACKET_COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION`, **not** authorization.

## Synthetic demonstration

The deliberately incomplete fixture `fixtures/utility-field-evidence-packet-synthetic.json` yields `BLOCKED`. It includes no real infrastructure or protected customer data.

```bash
python -m unittest discover -s tests -p 'test_utility_field_evidence_gate.py' -v
python scripts/utility_field_evidence_gate.py fixtures/utility-field-evidence-packet-synthetic.json
```

The CLI exits 1 for blocked packets, 0 for structurally complete but unverified packets, and 2 for invalid input. Exit 0 is never an operational approval signal. Production integration must not use these return codes as authorization to inspect, operate, trim, dispatch or deploy.

## Separate scientific and operational gates

1. A licensed or otherwise appropriately qualified field-methodology owner defines the hazards, scope, validation design and acceptable failure costs.
2. A trusted evidence collector checks actual file hashes, signed review records, survey time, data rights, spatial datums, ground-truth independence and reviewer authorization. JSON metadata is not evidence authenticity.
3. Field results are independently sampled, with locked holdout sets and real failure metrics including confidence intervals, subgroup performance and missed-hazard review.
4. Only a separately authorized control plane can approve production deployment or work-order integration, after applicable security/CI gates, restoration evidence, human review and release signoff.

No customer savings, wildfire probabilities, conductor clearance or guaranteed inspection outcomes are asserted. The core synthetic measurement and score comparison remain separate from human approval.
