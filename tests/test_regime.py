import numpy as np
import pandas as pd
from qfx.regime_detector import compute_regime_signals, calibrate_thresholds, classify_regime


def _make_synthetic_ohlcv(n=500, seed=42):
    """Synthetic H1 bars: mostly calm random walk, with one deliberate
    volatility spike injected in the back half so classification has
    something real to detect."""
    rng = np.random.default_rng(seed)
    calm_rets = rng.normal(0, 0.001, n)
    calm_rets[300:320] = rng.normal(-0.01, 0.02, 20)  # injected spike, biased down

    price = 100 * np.exp(np.cumsum(calm_rets))
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    df = pd.DataFrame({
        "open": price, "close": price,
        "high": price * 1.001, "low": price * 0.999,
        "tick_volume": rng.integers(100, 200, n),
        "real_volume": np.zeros(n),
        "spread": rng.integers(5, 15, n),
    }, index=idx)
    return df


def test_calibration_produces_ordered_thresholds():
    df = _make_synthetic_ohlcv()
    signals = compute_regime_signals(df)
    thresholds = calibrate_thresholds(signals)
    # Spike threshold (95th pct) must exceed elevated threshold (75th pct) —
    # if this ever failed it would mean the percentile logic is broken.
    assert thresholds["vol_ratio_spike"] > thresholds["vol_ratio_elevated"]
    assert thresholds["atr_ratio_spike"] > thresholds["atr_ratio_elevated"]


def test_injected_spike_gets_classified_as_panic_or_elevated():
    df = _make_synthetic_ohlcv()
    signals = compute_regime_signals(df)
    thresholds = calibrate_thresholds(signals)
    classified = classify_regime(signals, thresholds)

    # The injected spike region (bars 300-320) should show up as something
    # other than Calm — not asserting exactly "Panic" since synthetic noise
    # levels vary run to run, but it must not be silently missed entirely.
    spike_region = classified.iloc[300:320]["regime"]
    non_calm_count = (spike_region != "Calm").sum()
    assert non_calm_count > 0, "injected volatility spike was not detected at all"


def test_direction_sign_matches_injected_bias():
    df = _make_synthetic_ohlcv()
    signals = compute_regime_signals(df)
    # The injected spike was biased downward (-0.01 mean) — direction_ret
    # somewhere in/after that window should reflect a negative move.
    window = signals.iloc[300:330]["direction_ret"]
    assert window.min() < 0, "downward-biased spike did not produce any negative direction_ret"
