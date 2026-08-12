# PCG (heart-sound) model — evaluation report

Generated 2026-08-12T14:35:28.744531+00:00 · algorithm `random_forest` · version `v1`.

## Approach
MFCC + spectral/envelope summary features (classical, not CNN). Positive class = abnormal heart sound. A 2D-CNN with
Grad-CAM over the Mel-spectrogram is the documented upgrade path.

## Data
- Source: PhysioNet/CinC-2016 Heart Sound Database
- Sets: {'training-a': 409, 'training-b': 260}
- Recordings used: 669 (skipped 0 unreadable/too-short)
- Balance: 344 abnormal / 325 normal

> Recording-level stratified split. Subject IDs are not published with the basic CinC-2016 files, so true patient-level grouping cannot be enforced here; some subjects may contribute multiple recordings. Metrics should be read with that caveat — this is a known limitation, not hidden.

## Candidate comparison (5-fold CV ROC-AUC)
| Model | ROC-AUC |
|---|---|
| `logistic_regression` | 0.7542 ± 0.0427 |
| `random_forest` | 0.7824 ± 0.0388 |
| `xgboost` | 0.7597 ± 0.0464 |

## Held-out test (threshold 0.36, tuned for sensitivity)
| Metric | Value |
|---|---|
| ROC-AUC | 0.8056 |
| Sensitivity (recall) | 0.8551 |
| Specificity | 0.5846 |
| Precision | 0.686 |
| F1 | 0.7613 |
| Accuracy | 0.7239 |
| Brier | 0.1824 |

Confusion: TN 38 · FP 27 · FN 10 · TP 59

The threshold favours sensitivity: a missed abnormal heart sound is the costly
error for screening, so more false positives are accepted to keep false
negatives low.
