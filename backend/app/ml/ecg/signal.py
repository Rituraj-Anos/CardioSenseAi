"""ECG signal ingestion and preprocessing — Blueprint Sections 19 and 27.

The ingestion contract is the Hardware Abstraction Layer contract:
`{signal: number[], sample_rate: int, metadata: {...}}`. Every source — a CSV
upload, a WFDB record, or a future AD8232/ESP32 front end — is normalised into
`ECGSignal` before the model sees it, so the model never learns which device
produced the waveform.

One caveat carried through deliberately (Buildchain Brief Section 1): MIT-BIH
is 2-channel at 360 Hz. Only channel 0 (modified lead II) is used. Averaging or
concatenating both channels would teach a 2-lead signature that a single-lead
AD8232 front end can never produce.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

TARGET_SAMPLE_RATE = 250          # ample for rhythm analysis, keeps arrays small
POWERLINE_HZ_INDIA = 50.0         # notch target; 60 Hz in the Americas
BANDPASS_LOW_HZ = 0.5             # removes baseline wander
BANDPASS_HIGH_HZ = 40.0
MIN_DURATION_S = 5.0
MAX_DURATION_S = 300.0


class ECGValidationError(ValueError):
    """Raised when a payload cannot be interpreted as an ECG waveform."""


@dataclass
class ECGSignal:
    """The single ingestion contract every ECG source is normalised into."""

    signal: np.ndarray                       # 1-D, single lead, filtered
    sample_rate: int
    lead_name: str = "II"
    leads_available: int = 1
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
def from_array(
    values: list[float] | np.ndarray,
    sample_rate: int,
    *,
    lead_name: str = "II",
    metadata: dict[str, Any] | None = None,
) -> ECGSignal:
    """The HAL entry point. A device driver only has to reach this function."""
    arr = np.asarray(values, dtype=np.float64).ravel()
    if arr.size == 0:
        raise ECGValidationError("ECG signal is empty.")
    if not np.isfinite(arr).all():
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    if sample_rate <= 0:
        raise ECGValidationError("sample_rate must be positive.")

    duration = arr.size / sample_rate
    if duration < MIN_DURATION_S:
        raise ECGValidationError(
            f"Recording is {duration:.1f}s; at least {MIN_DURATION_S:.0f}s is needed."
        )
    if duration > MAX_DURATION_S:
        raise ECGValidationError(
            f"Recording is {duration:.0f}s; the maximum accepted is {MAX_DURATION_S:.0f}s."
        )

    resampled, sr = resample(arr, sample_rate, TARGET_SAMPLE_RATE)
    filtered = preprocess(resampled, sr)

    return ECGSignal(
        signal=filtered.astype(np.float32),
        sample_rate=sr,
        lead_name=lead_name,
        duration_seconds=float(filtered.size / sr),
        metadata={"original_sample_rate": int(sample_rate), **(metadata or {})},
    )


def from_upload(path: str | Path, sample_rate: int | None = None) -> ECGSignal:
    """Read an uploaded CSV/TXT/JSON waveform."""
    path = Path(path)
    if not path.is_file():
        raise ECGValidationError(f"ECG file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "signal" not in payload:
            raise ECGValidationError(
                "JSON ECG must be an object with a 'signal' array and 'sample_rate'."
            )
        sr = int(payload.get("sample_rate") or sample_rate or 0)
        if sr <= 0:
            raise ECGValidationError("JSON ECG is missing 'sample_rate'.")
        return from_array(
            payload["signal"],
            sr,
            lead_name=str(payload.get("lead_name", "II")),
            metadata={k: v for k, v in payload.items() if k not in {"signal", "sample_rate"}},
        )

    if sample_rate is None:
        raise ECGValidationError(
            "A sample_rate must be supplied for CSV/TXT uploads — a waveform "
            "without its sampling rate is uninterpretable."
        )

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        raise ECGValidationError("ECG file is empty.")

    lines = text.splitlines()
    # Drop a header row if the first line has no parseable number.
    if lines and not _looks_numeric(lines[0]):
        lines = lines[1:]

    values: list[float] = []
    for line in lines:
        for token in line.replace(";", ",").replace("\t", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                values.append(float(token))
            except ValueError:
                continue
            break  # first numeric column only — single lead by contract

    if len(values) < 10:
        raise ECGValidationError("Could not parse a numeric waveform from the file.")

    return from_array(values, sample_rate, metadata={"source_file": path.name})


def _looks_numeric(line: str) -> bool:
    """True if the line contains at least one parseable number — used to detect
    and skip a header row in an uploaded CSV/TXT waveform."""
    for token in line.replace(";", ",").replace("\t", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            float(token)
            return True
        except ValueError:
            continue
    return False


def from_wfdb(record_name: str, pn_dir: str = "mitdb", channel: int = 0) -> ECGSignal:
    """Load a PhysioNet WFDB record (used for the curated demo inputs).

    `channel=0` is deliberate and should stay 0 for MIT-BIH: it is the modified
    lead II channel, the one closest to what a single-lead front end produces.
    """
    import wfdb

    record = wfdb.rdrecord(record_name, pn_dir=pn_dir)
    signals = np.asarray(record.p_signal)
    if signals.ndim == 1:
        channel_data = signals
    else:
        if channel >= signals.shape[1]:
            raise ECGValidationError(
                f"Record {record_name} has {signals.shape[1]} channel(s); "
                f"channel {channel} was requested."
            )
        channel_data = signals[:, channel]

    lead_names = list(getattr(record, "sig_name", []) or [])
    return from_array(
        channel_data,
        int(record.fs),
        lead_name=lead_names[channel] if channel < len(lead_names) else "II",
        metadata={
            "source": "physionet_wfdb",
            "record": record_name,
            "database": pn_dir,
            "channels_in_record": int(signals.shape[1]) if signals.ndim > 1 else 1,
            "channel_used": channel,
            "all_lead_names": lead_names,
            "channel_note": (
                "Only one channel is used. Multi-channel records are not averaged "
                "or concatenated, so the model cannot learn a multi-lead signature "
                "that single-lead hardware could never reproduce."
            ),
        },
    )


# --------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------
def resample(signal: np.ndarray, sr_in: int, sr_out: int) -> tuple[np.ndarray, int]:
    if sr_in == sr_out:
        return signal, sr_in
    from scipy.signal import resample_poly
    from math import gcd

    g = gcd(int(sr_in), int(sr_out))
    return resample_poly(signal, sr_out // g, sr_in // g), sr_out


def preprocess(signal: np.ndarray, sr: int) -> np.ndarray:
    """Bandpass for baseline wander + notch for powerline interference."""
    from scipy.signal import butter, iirnotch, sosfiltfilt, tf2sos

    nyquist = sr / 2.0
    high = min(BANDPASS_HIGH_HZ, nyquist * 0.95)
    sos = butter(4, [BANDPASS_LOW_HZ / nyquist, high / nyquist], btype="band", output="sos")
    out = sosfiltfilt(sos, signal)

    if POWERLINE_HZ_INDIA < nyquist:
        b, a = iirnotch(POWERLINE_HZ_INDIA / nyquist, Q=30.0)
        out = sosfiltfilt(tf2sos(b, a), out)

    return out


def detect_r_peaks(signal: np.ndarray, sr: int) -> np.ndarray:
    """Pan–Tompkins-style R-peak detection (Blueprint Section 19).

    Derivative → squaring → moving-window integration → adaptive-threshold
    peak picking, with a physiological refractory period.
    """
    from scipy.signal import find_peaks

    if signal.size < sr:
        return np.array([], dtype=int)

    differentiated = np.diff(signal, prepend=signal[0])
    squared = differentiated**2
    window = max(1, int(0.150 * sr))
    integrated = np.convolve(squared, np.ones(window) / window, mode="same")

    threshold = float(np.mean(integrated) + 0.5 * np.std(integrated))
    refractory = int(0.25 * sr)  # 250 ms ≈ 240 bpm ceiling
    peaks, _ = find_peaks(integrated, height=threshold, distance=refractory)

    # Snap each detection onto the true local maximum of the filtered signal.
    search = max(1, int(0.05 * sr))
    refined = []
    for p in peaks:
        lo, hi = max(0, p - search), min(signal.size, p + search)
        refined.append(lo + int(np.argmax(np.abs(signal[lo:hi]))))
    return np.unique(np.asarray(refined, dtype=int))


def rhythm_summary(ecg: ECGSignal) -> dict[str, Any]:
    """Interpretable rhythm descriptors: rate, RR variability, irregularity.

    These are signal-processing measurements, not model output. They are safe
    to display because they describe the waveform rather than predicting an
    outcome from it.
    """
    peaks = detect_r_peaks(ecg.signal, ecg.sample_rate)
    if peaks.size < 3:
        return {
            "beats_detected": int(peaks.size),
            "heart_rate_bpm": None,
            "note": "Too few beats detected to summarise rhythm reliably.",
        }

    rr = np.diff(peaks) / ecg.sample_rate
    rr = rr[(rr > 0.25) & (rr < 2.5)]
    if rr.size < 2:
        return {"beats_detected": int(peaks.size), "heart_rate_bpm": None}

    mean_rr = float(np.mean(rr))
    rmssd = float(np.sqrt(np.mean(np.diff(rr) ** 2))) if rr.size > 2 else 0.0

    return {
        "beats_detected": int(peaks.size),
        "heart_rate_bpm": round(60.0 / mean_rr, 1),
        "mean_rr_seconds": round(mean_rr, 4),
        "sdnn_seconds": round(float(np.std(rr)), 4),
        "rmssd_seconds": round(rmssd, 4),
        "irregularity_index": round(float(np.std(rr) / mean_rr), 4) if mean_rr else None,
    }
