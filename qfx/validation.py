"""
Regime validation.

The test that actually matters: does a bar's regime label predict anything
about what happens NEXT, or is it just describing what already happened?

For each bar, look forward N bars and measure:
  - fwd_return   : close-to-close return over the horizon
  - fwd_drawdown : worst adverse excursion (min low reached) over the horizon,
                   expressed as a return — the "if you'd gone long here, how
                   bad could it get" number
  - fwd_runup    : best favorable excursion (max high reached) — the mirror,
                   useful for checking Euphoria/Panic aren't just noise labels
                   in one direction only

Then group by regime and compare against Calm as the baseline. A useful
regime signal shows: Panic/Elevated-Bearish -> worse fwd_drawdown than Calm;
Euphoria/Elevated-Bullish -> better fwd_runup than Calm. If the numbers don't
separate from Calm, the regime label isn't earning its keep as a filter.
"""

import pandas as pd
import numpy as np

from data_loader import load_mt5_h1
from regime_detector import compute_regime_signals, calibrate_thresholds, classify_regime
from news_calendar import apply_news_lockout

HORIZONS = [5, 10, 20]  # bars ahead (H1 data -> 5h, 10h, 20h)


def compute_forward_metrics(df: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    low = out["low"]
    high = out["high"]

    for h in horizons:
        # min low / max high among the NEXT h bars (t+1 .. t+h), aligned to t
        future_min_low = low[::-1].rolling(h, min_periods=h).min()[::-1].shift(-1)
        future_max_high = high[::-1].rolling(h, min_periods=h).max()[::-1].shift(-1)
        fwd_close = close.shift(-h)

        out[f"fwd_return_{h}"] = fwd_close / close - 1
        out[f"fwd_drawdown_{h}"] = future_min_low / close - 1
        out[f"fwd_runup_{h}"] = future_max_high / close - 1

    return out


def summarize_by_regime(df: pd.DataFrame, symbol: str, horizons=HORIZONS) -> pd.DataFrame:
    rows = []
    for regime, group in df.groupby("regime"):
        if regime in ("Unknown",):
            continue
        row = {"symbol": symbol, "regime": regime, "n_bars": len(group)}
        for h in horizons:
            ret_col, dd_col, ru_col = f"fwd_return_{h}", f"fwd_drawdown_{h}", f"fwd_runup_{h}"
            row[f"mean_ret_{h}h"] = group[ret_col].mean()
            row[f"ret_vol_{h}h"] = group[ret_col].std()
            row[f"mean_drawdown_{h}h"] = group[dd_col].mean()
            row[f"p5_drawdown_{h}h"] = group[dd_col].quantile(0.05)
            row[f"mean_runup_{h}h"] = group[ru_col].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def print_comparison(summary: pd.DataFrame, symbol: str, horizon: int = 10):
    sub = summary[summary["symbol"] == symbol].set_index("regime")
    if "Calm" not in sub.index:
        print(f"  (no Calm baseline found for {symbol})")
        return
    calm = sub.loc["Calm"]
    print(f"\n{symbol} — {horizon}h forward outcomes vs Calm baseline:")
    print(f"  {'regime':18s} {'n':>7s} {'mean_ret':>10s} {'ret_vol':>10s} {'mean_dd':>10s} {'p5_dd':>10s} {'mean_ru':>10s}")
    for regime in ["Calm", "Elevated-Bullish", "Elevated-Bearish", "Euphoria", "Panic"]:
        if regime not in sub.index:
            continue
        r = sub.loc[regime]
        print(f"  {regime:18s} {int(r['n_bars']):7d} "
              f"{r[f'mean_ret_{horizon}h']*100:9.3f}% "
              f"{r[f'ret_vol_{horizon}h']*100:9.3f}% "
              f"{r[f'mean_drawdown_{horizon}h']*100:9.3f}% "
              f"{r[f'p5_drawdown_{horizon}h']*100:9.3f}% "
              f"{r[f'mean_runup_{horizon}h']*100:9.3f}%")


if __name__ == "__main__":
    files = {
        "BTCUSD": "BTCUSD_raw.csv",
        "EURUSD": "EURUSD_raw.csv",
        "XAUUSD": "XAUUSD_raw.csv",
    }

    all_summaries = []
    for sym, path in files.items():
        df = load_mt5_h1(path, sym)
        signals = compute_regime_signals(df)
        thresholds = calibrate_thresholds(signals)
        classified = classify_regime(signals, thresholds)
        classified = apply_news_lockout(classified)
        with_forward = compute_forward_metrics(classified)

        summary = summarize_by_regime(with_forward, sym)
        all_summaries.append(summary)

        print_comparison(summary, sym, horizon=10)

    full_summary = pd.concat(all_summaries, ignore_index=True)
    full_summary.to_csv("/mnt/user-data/outputs/regime_validation_summary.csv", index=False)
    print(f"\nFull summary (all horizons, all symbols) saved to regime_validation_summary.csv")
