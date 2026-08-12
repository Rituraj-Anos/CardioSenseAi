# ECG model — evaluation report

Generated 2026-08-12T15:03:28.226066+00:00 · algorithm `xgboost` · version `v1`.

## Approach
rhythm/interval/morphology features (classical, not CNN). Positive class = abnormal rhythm. Single-lead
(channel 0 / modified lead II) only. A 1D-CNN on the raw waveform is the upgrade path.

## Data
- Source: MIT-BIH Arrhythmia Database (PhysioNet)
- Split: by record (no subject crosses the split)
- Train records: ['100', '101', '103', '105', '108', '112', '113', '115', '117', '122', '205', '202', '201', '203', '208', '210', '213', '215']
- Test records: ['119', '121', '200', '209', '212', '228', '231', '233']
- Windows: 1080 train / 480 test (10s each)
- Label rule: window abnormal if >=20% of its beats are non-normal (MIT-BIH symbols)

## Candidate comparison (5-fold CV ROC-AUC)
| Model | ROC-AUC |
|---|---|
| `logistic_regression` | 0.9541 ± 0.0144 |
| `random_forest` | 0.9786 ± 0.0091 |
| `xgboost` | 0.9799 ± 0.0038 |

## Held-out test (threshold 0.02)
| Metric | Value |
|---|---|
| ROC-AUC | 0.9428 |
| Sensitivity | 0.8693 |
| Specificity | 0.8532 |
| Precision | 0.7348 |
| F1 | 0.7964 |
| Accuracy | 0.8583 |
| Brier | 0.1574 |

Confusion: TN 279 · FP 48 · FN 20 · TP 133

Test records are entirely held out from training, so these numbers reflect
generalisation to unseen recordings, not memorised beats.
