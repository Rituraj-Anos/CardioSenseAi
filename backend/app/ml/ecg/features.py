"""ECG feature extraction — shared by training and serving.

Interpretable rhythm/interval/morphology features from a single-lead window,
built on the R-peak detection already in ecg/signal.py. One module for both
train and serve keeps them identical (anti train/serve skew).

Approach note: a classical feature model over rhythm + morphology descriptors.
A 1D-CNN / ResNet-1D on the raw waveform is the documented upgrade path; this
build ships the classical model honestly labelled as such.
"""

from __future__ import annotations

import numpy as np

from app.ml.ecg.signal import ECGSignal, detect_r_peaks

FEATURE_NAMES: list[str] = [
    "heart_rate_bpm",
    "mean_rr",
    "sdnn",
    "rmssd",
    "rr_irregularity",
    "pnn50",
    "qrs_amp_mean",
    "qrs_amp_std",
    "signal_std",
    "signal_ptp",
    "beat_rate_per_s",
    "rr_range",
]


def extract_features(ecg: ECGSignal) -> np.ndarray:
    sig = ecg.signal.astype(float)
    sr = ecg.sample_rate
    peaks = detect_r_peaks(sig, sr)

    if peaks.size >= 3:
        rr = np.diff(peaks) / sr
        rr = rr[(rr > 0.25) & (rr < 2.5)]
    else:
        rr = np.array([])

    if rr.size >= 2:
        mean_rr = float(np.mean(rr))
        sdnn = float(np.std(rr))
        diff_rr = np.diff(rr)
        rmssd = float(np.sqrt(np.mean(diff_rr**2)))
        pnn50 = float(np.mean(np.abs(diff_rr) > 0.05))
        hr = 60.0 / mean_rr if mean_rr else 0.0
        rr_irr = sdnn / mean_rr if mean_rr else 0.0
        rr_range = float(np.max(rr) - np.min(rr))
    else:
        mean_rr = sdnn = rmssd = pnn50 = hr = rr_irr = rr_range = 0.0

    qrs_amp = np.abs(sig[peaks]) if peaks.size else np.array([0.0])
    duration = max(sig.size / sr, 1e-6)

    feats = np.array([
        hr,
        mean_rr,
        sdnn,
        rmssd,
        rr_irr,
        pnn50,
        float(np.mean(qrs_amp)),
        float(np.std(qrs_amp)),
        float(np.std(sig)),
        float(np.ptp(sig)),
        float(peaks.size / duration),
        rr_range,
    ])
    return np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
