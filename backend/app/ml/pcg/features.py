"""PCG feature extraction — shared by training and serving.

A compact, interpretable feature vector for a classical heart-sound classifier:
MFCC summary statistics plus spectral and envelope descriptors. Living in one
module (imported by both ml/pcg/train.py and the live predictor) is what keeps
train and serve identical — the same anti-skew rule as the clinical model.

Note on approach: the Blueprint targets a 2D-CNN on the Mel-spectrogram with
Grad-CAM. That needs a deep-learning runtime this build doesn't ship. This
MFCC-based classical model is a genuine, honestly-labelled first model; the CNN
remains the documented upgrade path. Explanations here are feature-importance
based, not Grad-CAM, and are labelled as such.
"""

from __future__ import annotations

import numpy as np

from app.ml.pcg.signal import PCGSignal, estimate_heart_rate

N_MFCC = 13

# Contractual feature order shared by train and serve.
FEATURE_NAMES: list[str] = (
    [f"mfcc{i}_mean" for i in range(N_MFCC)]
    + [f"mfcc{i}_std" for i in range(N_MFCC)]
    + [
        "spectral_centroid_mean",
        "spectral_bandwidth_mean",
        "spectral_rolloff_mean",
        "zcr_mean",
        "rms_mean",
        "rms_std",
        "in_band_energy_ratio",
        "heart_rate_norm",
    ]
)


def extract_features(signal: PCGSignal) -> np.ndarray:
    """Return the feature vector for one recording, in FEATURE_NAMES order."""
    import librosa

    y = signal.audio
    sr = signal.sample_rate

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC, n_fft=512, hop_length=128)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=512, hop_length=128)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=512, hop_length=128)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=512, hop_length=128)
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=512, hop_length=128)
    rms = librosa.feature.rms(y=y, frame_length=512, hop_length=128)

    hr = estimate_heart_rate(y, sr)
    hr_norm = (hr / 200.0) if hr else 0.0

    feats = np.concatenate(
        [
            mfcc.mean(axis=1),
            mfcc.std(axis=1),
            [
                float(centroid.mean()),
                float(bandwidth.mean()),
                float(rolloff.mean()),
                float(zcr.mean()),
                float(rms.mean()),
                float(rms.std()),
                float(signal.quality.get("in_band_energy_ratio", 0.0)),
                float(hr_norm),
            ],
        ]
    )
    return np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
