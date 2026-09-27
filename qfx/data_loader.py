"""
MT5 H1 CSV loader.

Handles the mixed-granularity issue found in these exports: MT5 brokers often
backfill history beyond their stored intraday depth with one D1-style bar per
day, stamped 00:00:00, disguised as H1. Left in, a single "daily bar" masquerading
as one H1 bar has ~24x the true-bar range/volume, which corrupts rolling
volatility and volume calibration. This loader detects the first date with
genuine multi-bar-per-day coverage and trims everything before it.
"""

import pandas as pd
import numpy as np


def load_mt5_h1(path: str, symbol: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", encoding="utf-8")
    df.columns = [c.strip("<>").upper() for c in df.columns]
    df["DATETIME"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("DATETIME").reset_index(drop=True)

    # detect true-H1 start: first date where >1 bar exists that day
    bars_per_day = df.groupby(df["DATETIME"].dt.date).size()
    true_h1_dates = bars_per_day[bars_per_day > 1].index
    if len(true_h1_dates) == 0:
        raise ValueError(f"{symbol}: no multi-bar days found — cannot confirm true H1 data")
    true_h1_start = pd.Timestamp(true_h1_dates.min())

    trimmed = df[df["DATETIME"].dt.normalize() >= true_h1_start].copy()

    trimmed = trimmed.rename(columns={
        "OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close",
        "TICKVOL": "tick_volume", "VOL": "real_volume", "SPREAD": "spread",
    })
    trimmed = trimmed.set_index("DATETIME")[["open", "high", "low", "close", "tick_volume", "real_volume", "spread"]]
    trimmed.attrs["symbol"] = symbol
    trimmed.attrs["true_h1_start"] = true_h1_start
    trimmed.attrs["rows_dropped"] = len(df) - len(trimmed)

    return trimmed


if __name__ == "__main__":
    files = {
        "BTCUSD": "BTCUSD_raw.csv",
        "EURUSD": "EURUSD_raw.csv",
        "XAUUSD": "XAUUSD_raw.csv",
    }
    for sym, path in files.items():
        d = load_mt5_h1(path, sym)
        print(f"{sym}: {len(d)} true-H1 bars, from {d.index.min()} to {d.index.max()}, "
              f"dropped {d.attrs['rows_dropped']} pre-H1 rows (true H1 start: {d.attrs['true_h1_start'].date()})")
