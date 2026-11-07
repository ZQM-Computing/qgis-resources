# Synthetic 3D utility separation — uncertainty-aware proof of concept

**Status: engineering test only, not field clearance, wildfire risk, maintenance prioritization or a regulatory determination.**

This module is a second independently reviewed utility workstream, **not** a modification of the existing 2D polygon corridor PR #43. It measures straight-line Euclidean separation between a synthetic conductor **segment** and a synthetic vegetation **sample point** using `scripts/synthetic_clearance_3d.py`. Results are measured in metres in an explicitly artificial shared vertical coordinate frame.

## Input and units

The local JSON fixture `fixtures/utility-clearance-3d-synthetic.json` supplies a horizontal CRS label (EPSG:32617), a **fictional shared vertical reference** (`SYNTHETIC_SHARED_LOCAL_METRES`), an ISO observation date, a synthetic proximity threshold, conductor line segments and sampled vegetation 3D points.

The input is deliberately limited to 1 MiB, 100 segments, 2,000 sample points and finite, bounded projected coordinates. It refuses absent positional error estimates, identical segment endpoints, invalid dates, non-finite values, duplicate IDs, booleans substituted for numbers, unsupported coordinate reference and self-authorization.

No real vertical datum transformation or surveyed source authenticity is implemented.

## Method and limits

For a vegetation point `p` and a finite segment `[a,b]`, the code projects `p` onto the segment, clamps the parameter to [0,1], and computes the Euclidean 3D distance to the closest point. It then forms a **conditional** lower/upper range by subtracting/adding the sum of the two separately asserted absolute position errors. A sample is flagged if the lower distance bound falls within the fictional review threshold.

**This range is not statistically calibrated or a guaranteed confidence interval.** It is only a geometric sensitivity bound *if* the absolute error assertions are trustworthy and all relevant errors are included. It excludes data capture age, conductor sag, temperature, wind, pole deformation, vegetation motion and unsampled canopy surfaces. A clear distance from a sampled point cannot establish clearance of a tree canopy or the line corridor.

If one or more samples are flagged, status is `REVIEW`; if no sample is flagged, status is `INSUFFICIENT_EVIDENCE`. The output always sets field clearance, wildfire probability, work-order authorization, customer savings and human approval to false/required. It never creates a maintenance order.

## Exact repeatable checks

```bash
python -m unittest discover -s tests -p 'test_synthetic_clearance_3d.py' -v
python scripts/synthetic_clearance_3d.py fixtures/utility-clearance-3d-synthetic.json
```

Synthetic fixture: a straight segment and a sample separated by 3.0 m (nominal), each with an asserted 0.5 m position error, produce a conditional 2.0–4.0 m range and an inspection flag under an **arbitrary 4.0 m research threshold**. These values are fictional, not a utility-approved safety standard. A second asset with no nearby sampled point returns `SAMPLED_POINTS_OUTSIDE_THRESHOLD_NOT_CLEARANCE`.

The repository's standard CI Python tests are sufficient for the pure 3D geometric helper; the existing 2D workstream runs its separate GDAL/OGR QGIS runtime tests. All baseline CI/security workflows continue to run and must pass.

## Path to a real product

1. Confirm requirements with a named utility or vegetation management contractor and qualified safety reviewer; collect test evidence outside public code.
2. Independently verify geodetic + vertical datums, point classifications, LiDAR density, equipment measurement error, conductor geometry, sag and environmental conditions.
3. Test false negative and false positive rates against independent field-observed hazards; provide versioned risk methodology and audit trail.
4. Distinguish physical clearance measurements, operational inspections, permitted trim work and financial scenarios in separate schemas with explicit human authorization.
5. Estimate ROI only from customer-approved baseline maintenance costs, crew hours, downtime, and observable outcomes. Do not claim 25% savings as achieved performance.

No customer data, credentials, real infrastructure topology, autonomous field work, cloud integration or production deployment is introduced.
