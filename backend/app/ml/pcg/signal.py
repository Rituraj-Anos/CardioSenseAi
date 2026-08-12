"""PCG (heart-sound) signal validation and preprocessing — Blueprint Section 18.

Shared by the future training script and the live inference path, same
anti-skew rule as the clinical model.

Pipeline implemented here: format/duration/sample-rate validation → bandpass
filter (heart sounds sit roughly in the 20–200 Hz band) → downsample to a
fixed rate → Mel-spectrogram / MFCC representation.

Segmentation into S1/S2/systole/diastole is envelope-based here. A full
HSMM segmenter is the stronger option named in the Blueprint and is left as a
follow-up; the envelope approach is honest about being the simpler one rather
than being labelled as something it isn't.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Heart sounds are low-frequency. 2 kHz is ample and keeps everything small.
TARGET_SAMPLE_RATE = 2000
BANDPASS_LOW_HZ = 20.0
BANDPASS_HIGH_HZ = 200.0
MIN_DURATION_S = 2.0
MAX_DURATION_S = 120.0
N_MELS = 64
N_MFCC = 20


class PCGValidationError(ValueError):
    """Raised when an audio file cannot be used as a heart-sound recording."""


@dataclass
class PCGSignal:
    audio: np.ndarray          # mono, float32, filtered, at TARGET_SAMPLE_RATE
    sample_rate: int
    duration_seconds: float
    original_sample_rate: int
    quality: dict[str, float]


def load_and_validate(path: str | Path) -> PCGSignal:
    import librosa
    import soundfile as sf

    path = Path(path)
    if not path.is_file():
        raise PCGValidationError(f"Audio file not found: {path}")

    try:
        info = sf.info(str(path))
    except Exception as exc:
        raise PCGValidationError(f"Unreadable audio file: {exc}") from exc

    if info.duration < MIN_DURATION_S:
        raise PCGValidationError(
            f"Recording is {info.duration:.1f}s; at least {MIN_DURATION_S:.0f}s is "
            f"needed to capture several cardiac cycles."
        )
    if info.duration > MAX_DURATION_S:
        raise PCGValidationError(
            f"Recording is {info.duration:.0f}s; the maximum accepted is "
            f"{MAX_DURATION_S:.0f}s."
        )

    audio, sr = librosa.load(str(path), sr=TARGET_SAMPLE_RATE, mono=True)
    if audio.size == 0:
        raise PCGValidationError("Audio file decoded to zero samples.")

    filtered = bandpass(audio, sr)
    filtered = normalise(filtered)

    return PCGSignal(
        audio=filtered.astype(np.float32),
        sample_rate=sr,
        duration_seconds=float(len(filtered) / sr),
        original_sample_rate=int(info.samplerate),
        quality=quality_metrics(filtered, sr),
    )


def bandpass(audio: np.ndarray, sr: int) -> np.ndarray:
    """Zero-phase Butterworth bandpass over the heart-sound band."""
    from scipy.signal import butter, sosfiltfilt

    nyquist = sr / 2.0
    high = min(BANDPASS_HIGH_HZ, nyquist * 0.99)
    sos = butter(4, [BANDPASS_LOW_HZ / nyquist, high / nyquist], btype="band", output="sos")
    return sosfiltfilt(sos, audio)


def normalise(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio / peak if peak > 1e-9 else audio


def envelope(audio: np.ndarray, sr: int, smooth_ms: float = 50.0) -> np.ndarray:
    """Shannon-energy envelope, the standard basis for S1/S2 detection."""
    from scipy.signal import savgol_filter

    x = normalise(audio)
    energy = -(x**2) * np.log(np.clip(x**2, 1e-12, None))
    window = max(5, int(sr * smooth_ms / 1000.0) | 1)
    if window >= len(energy):
        return energy
    return savgol_filter(energy, window_length=window, polyorder=2)


def detect_peaks(audio: np.ndarray, sr: int) -> np.ndarray:
    """Candidate S1/S2 locations from the envelope, as sample indices."""
    from scipy.signal import find_peaks

    env = envelope(audio, sr)
    if env.size == 0:
        return np.array([], dtype=int)
    # Physiological floor: at 200 bpm, S1 and S2 are still ~150 ms apart.
    min_distance = int(sr * 0.15)
    peaks, _ = find_peaks(
        env, distance=min_distance, height=float(np.mean(env) + 0.5 * np.std(env))
    )
    return peaks


def estimate_heart_rate(audio: np.ndarray, sr: int) -> float | None:
    """Rough bpm from peak spacing. Returns None when it cannot be trusted."""
    peaks = detect_peaks(audio, sr)
    if len(peaks) < 4:
        return None
    intervals = np.diff(peaks) / sr
    # Peaks alternate S1/S2, so a full cycle spans two intervals.
    cycle = float(np.median(intervals)) * 2.0
    if cycle <= 0:
        return None
    bpm = 60.0 / cycle
    return round(bpm, 1) if 30.0 <= bpm <= 220.0 else None


def quality_metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
    """Cheap signal-quality proxies.

    These are transparency signals for the UI, not a validated SQI. The
    CinC-2016 database ships its own `REFERENCE-SQI.csv` for curation; this is
    for flagging an obviously unusable live recording, and is labelled as a
    proxy everywhere it surfaces.
    """
    if audio.size == 0:
        return {"rms": 0.0, "clipping_ratio": 0.0, "in_band_energy_ratio": 0.0}

    rms = float(np.sqrt(np.mean(audio**2)))
    clipping = float(np.mean(np.abs(audio) > 0.99))

    spectrum = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), d=1.0 / sr)
    total = float(np.sum(spectrum**2)) or 1.0
    in_band = float(
        np.sum(spectrum[(freqs >= BANDPASS_LOW_HZ) & (freqs <= BANDPASS_HIGH_HZ)] ** 2)
    )

    return {
        "rms": round(rms, 5),
        "clipping_ratio": round(clipping, 5),
        "in_band_energy_ratio": round(in_band / total, 5),
    }


def mel_spectrogram(signal: PCGSignal) -> np.ndarray:
    """Log-Mel spectrogram, the CNN input representation."""
    import librosa

    mel = librosa.feature.melspectrogram(
        y=signal.audio,
        sr=signal.sample_rate,
        n_fft=512,
        hop_length=128,
        n_mels=N_MELS,
        fmin=BANDPASS_LOW_HZ,
        fmax=min(BANDPASS_HIGH_HZ * 2, signal.sample_rate / 2),
    )
    return librosa.power_to_db(mel, ref=np.max)


def mfcc_features(signal: PCGSignal) -> np.ndarray:
    """Summary MFCC vector (mean + std per coefficient), for classical models."""
    import librosa

    mfcc = librosa.feature.mfcc(
        y=signal.audio, sr=signal.sample_rate, n_mfcc=N_MFCC, n_fft=512, hop_length=128
    )
    return np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)])
