"""
Volatility regime detector.

Six states: Calm / Elevated-Bullish / Elevated-Bearish / Euphoria / Panic /
News-lockout. Each instrument gets its own thresholds, calibrated from ITS OWN
historical distribution (percentile-based), not shared hardcoded numbers —
BTC, EUR and XAU have wildly different baseline volatility, so a fixed
absolute threshold would misclassify at least one of them.

Signals combined:
  1. vol_ratio    = fast realized-vol / slow realized-vol   (is vol EXPANDING)
  2. atr_ratio     = current ATR / rolling ATR baseline       (is RANGE expanding)
  3. vol_zscore   = volume vs its own rolling distribution   (is participation abnormal)
  4. direction_ret = return over the same fast window as vol_ratio (which WAY
                     is the expansion moving) — this is what separates fear
                     from greed. IMPORTANT LIMITATION: this is a magnitude +
                     direction classifier, not a true sentiment read. It
                     cannot distinguish "anticipation" (pre-event compression)
                     from "reaction" (post-event expansion), or "expected"
                     from "surprise" moves (would need forecast-vs-actual
                     data, e.g. NFP consensus). Panic/Euphoria here means
                     "big down move" / "big up move" — a reasonable proxy,
                     not a claim about actual market psychology.

State priority (highest wins): News-lockout > Panic/Euphoria > Elevated-* > Calm.
News-lockout is applied separately (see news_calendar.py) — this module produces
the pre-news regime and a raw score other logic can override.
"""

import pandas as pd
import numpy as np


def compute_regime_signals(df: pd.DataFrame, fast_win: int = 20, slow_win: int = 100,
                            atr_win: int = 14, atr_baseline_win: int = 100,
                            vol_zscore_win: int = 100) -> pd.DataFrame:
    out = df.copy()

    log_ret = np.log(out["close"] / out["close"].shift(1))
    fast_vol = log_ret.rolling(fast_win).std()
    slow_vol = log_ret.rolling(slow_win).std()
    out["vol_ratio"] = fast_vol / slow_vol

    # Directional skew: net return over the same window vol_ratio's fast leg
    # uses, so "was this expansion driven by a fall or a rally" lines up with
    # the same lookback that flagged the expansion in the first place.
    out["direction_ret"] = np.log(out["close"] / out["close"].shift(fast_win))

    high_low = out["high"] - out["low"]
    high_close = (out["high"] - out["close"].shift(1)).abs()
    low_close = (out["low"] - out["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(atr_win).mean()
    atr_baseline = atr.rolling(atr_baseline_win).mean()
    out["atr"] = atr
    out["atr_ratio"] = atr / atr_baseline

    vol_col = "real_volume" if (out["real_volume"] > 0).any() else "tick_volume"
    vol_mean = out[vol_col].rolling(vol_zscore_win).mean()
    vol_std = out[vol_col].rolling(vol_zscore_win).std()
    out["vol_zscore"] = (out[vol_col] - vol_mean) / vol_std
    out.attrs["volume_source"] = vol_col

    return out


def calibrate_thresholds(signals: pd.DataFrame, elevated_pct: float = 75, spike_pct: float = 95) -> dict:
    """Per-instrument percentile thresholds — data-driven, not guessed."""
    clean = signals.dropna(subset=["vol_ratio", "atr_ratio"])
    return {
        "vol_ratio_elevated": clean["vol_ratio"].quantile(elevated_pct / 100),
        "vol_ratio_spike": clean["vol_ratio"].quantile(spike_pct / 100),
        "atr_ratio_elevated": clean["atr_ratio"].quantile(elevated_pct / 100),
        "atr_ratio_spike": clean["atr_ratio"].quantile(spike_pct / 100),
    }


def classify_regime(signals: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    out = signals.copy()

    def _magnitude(row):
        if pd.isna(row["vol_ratio"]) or pd.isna(row["atr_ratio"]):
            return "Unknown"
        vr, ar = row["vol_ratio"], row["atr_ratio"]
        if vr >= thresholds["vol_ratio_spike"] or ar >= thresholds["atr_ratio_spike"]:
            return "Spike"
        if vr >= thresholds["vol_ratio_elevated"] or ar >= thresholds["atr_ratio_elevated"]:
            return "Elevated"
        return "Calm"

    out["_magnitude"] = out.apply(_magnitude, axis=1)

    def _combine(row):
        mag = row["_magnitude"]
        if mag in ("Calm", "Unknown"):
            return mag
        # direction only matters once we're expanding
        if pd.isna(row["direction_ret"]):
            return "Unknown"
        bearish = row["direction_ret"] < 0
        if mag == "Spike":
            return "Panic" if bearish else "Euphoria"
        return "Elevated-Bearish" if bearish else "Elevated-Bullish"

    out["regime"] = out.apply(_combine, axis=1)
    out = out.drop(columns=["_magnitude"])

    size_multiplier = {
        "Calm": 1.0,
        "Elevated-Bullish": 0.5, "Elevated-Bearish": 0.5,
        "Panic": 0.0, "Euphoria": 0.0,
        "News-lockout": 0.0, "Unknown": 0.0,
    }
    out["size_multiplier"] = out["regime"].map(size_multiplier)

    return out


def summarize_regime(classified: pd.DataFrame, symbol: str) -> None:
    counts = classified["regime"].value_counts()
    pct = (counts / counts.sum() * 100).round(1)
    print(f"\n{symbol} regime distribution (n={len(classified)} bars):")
    for state in ["Calm", "Elevated-Bullish", "Elevated-Bearish", "Panic", "Euphoria", "Unknown"]:
        if state in counts.index:
            print(f"  {state:18s}: {counts[state]:6d} bars ({pct[state]:5.1f}%)")


if __name__ == "__main__":
    from data_loader import load_mt5_h1

    files = {
        "BTCUSD": "BTCUSD_raw.csv",
        "EURUSD": "EURUSD_raw.csv",
        "XAUUSD": "XAUUSD_raw.csv",
    }

    for sym, path in files.items():
        df = load_mt5_h1(path, sym)
        signals = compute_regime_signals(df)
        thresholds = calibrate_thresholds(signals)
        classified = classify_regime(signals, thresholds)
        print(f"\n{sym} thresholds (volume source: {signals.attrs['volume_source']}):")
        for k, v in thresholds.items():
            print(f"  {k}: {v:.3f}")
        summarize_regime(classified, sym)
