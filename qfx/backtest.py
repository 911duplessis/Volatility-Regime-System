"""
Backtest: turns regime-detector statistics into actual simulated trades.

Tests TWO entry hypotheses against the same Panic regime:
  1. ONSET   — enter the moment Panic begins (tested first; see results —
     this did NOT survive contact with a real stop, on BTC in particular)
  2. EXHAUSTION — enter when Panic just ENDS (episode transitions back to a
     calmer state) — a different hypothesis: that the bounce/continuation
     lives in the stabilization moment, not the panic onset itself

Rules (both hypotheses):
  - Entry: at the close of the triggering bar (episode start or episode end,
    depending on hypothesis) — non-overlapping, one trade per episode
  - Exit: horizon (20 bars) OR stop-loss, whichever comes first
  - Stop: ATR-multiple based (adapts to each instrument/bar automatically,
    rather than a fixed % that would misfit BTC vs XAU's different vol scales)
  - Cost: actual historical spread from the MT5 export, converted to price
    using the instrument's point size, deducted once per round trip. This is
    real recorded spread, not an assumed constant — but it's still just
    spread; it does NOT include slippage on the stop fill (stops assumed to
    fill exactly at the stop price, which is optimistic for fast-moving
    Panic bars) or any commission the broker charges separately.
"""

import pandas as pd
import numpy as np

from data_loader import load_mt5_h1
from regime_detector import compute_regime_signals, calibrate_thresholds, classify_regime
from news_calendar import apply_news_lockout


def infer_point_size(df: pd.DataFrame) -> float:
    sample = df["close"].astype(str).str.split(".").str[-1].str.len()
    decimals = int(sample.mode().iloc[0])
    return 10 ** (-decimals)


def find_episode_starts(regime: pd.Series, target: str) -> pd.DatetimeIndex:
    """Bar where regime FIRST becomes target (episode onset)."""
    is_target = regime == target
    starts = is_target & (~is_target.shift(1, fill_value=False))
    return regime.index[starts]


def find_episode_ends(regime: pd.Series, target: str) -> pd.DatetimeIndex:
    """Bar where regime just LEFT target (episode exhaustion/stabilization) —
    i.e. previous bar was target, current bar isn't."""
    is_target = regime == target
    ends = (~is_target) & (is_target.shift(1, fill_value=False))
    return regime.index[ends]


def backtest(df: pd.DataFrame, direction: int, entries: pd.DatetimeIndex,
             horizon: int = 20, atr_stop_mult: float = 2.0, symbol: str = "") -> pd.DataFrame:
    """direction: +1 long, -1 short. `entries` is a set of bar timestamps to enter at (close)."""
    point_size = infer_point_size(df)
    trades = []

    for entry_time in entries:
        i = df.index.get_loc(entry_time)
        if i + horizon >= len(df) or i == 0:
            continue

        entry_price = df["close"].iloc[i]
        atr_at_entry = df["atr"].iloc[i]
        if pd.isna(atr_at_entry) or atr_at_entry <= 0:
            continue

        spread_points = df["spread"].iloc[i]
        cost_pct = (spread_points * point_size) / entry_price if spread_points > 0 else 0.0

        stop_distance = atr_stop_mult * atr_at_entry
        stop_price = entry_price - direction * stop_distance

        window = df.iloc[i + 1: i + 1 + horizon]
        exit_price, exit_reason, exit_time = None, "horizon", window.index[-1]

        if direction == 1:
            hit = window[window["low"] <= stop_price]
        else:
            hit = window[window["high"] >= stop_price]

        if len(hit) > 0:
            exit_time = hit.index[0]
            exit_price = stop_price
            exit_reason = "stop"
        else:
            exit_price = window["close"].iloc[-1]

        raw_ret = (exit_price / entry_price - 1) * direction
        net_ret = raw_ret - cost_pct

        trades.append({
            "symbol": symbol, "entry_time": entry_time, "exit_time": exit_time,
            "direction": "long" if direction == 1 else "short",
            "entry_price": entry_price, "exit_price": exit_price,
            "exit_reason": exit_reason, "raw_ret": raw_ret, "cost_pct": cost_pct,
            "net_ret": net_ret,
        })

    return pd.DataFrame(trades)


def summarize_trades(trades: pd.DataFrame, label: str) -> dict:
    if len(trades) == 0:
        print(f"\n{label}: no trades generated")
        return {}

    n = len(trades)
    win_rate = (trades["net_ret"] > 0).mean()
    avg_win = trades.loc[trades["net_ret"] > 0, "net_ret"].mean() if win_rate > 0 else 0.0
    avg_loss = trades.loc[trades["net_ret"] <= 0, "net_ret"].mean() if win_rate < 1 else 0.0
    expectancy = trades["net_ret"].mean()
    ret_std = trades["net_ret"].std()
    sharpe_per_trade = expectancy / ret_std if ret_std > 0 else float("nan")
    stop_rate = (trades["exit_reason"] == "stop").mean()
    total_ret = trades["net_ret"].sum()

    print(f"\n{label}")
    print(f"  trades: {n}  |  win rate: {win_rate*100:.1f}%  |  stopped out: {stop_rate*100:.1f}%")
    print(f"  expectancy/trade: {expectancy*100:.3f}%  |  avg win: {avg_win*100:.3f}%  |  avg loss: {avg_loss*100:.3f}%")
    print(f"  per-trade Sharpe (mean/std): {sharpe_per_trade:.3f}  |  sum of net returns: {total_ret*100:.2f}%")

    return {
        "label": label, "n_trades": n, "win_rate": win_rate,
        "expectancy": expectancy, "avg_win": avg_win, "avg_loss": avg_loss,
        "stop_rate": stop_rate, "sharpe_per_trade": sharpe_per_trade, "sum_net_ret": total_ret,
    }


if __name__ == "__main__":
    onset_setups = [
        ("BTCUSD", "BTCUSD_raw.csv", "Panic", 1),   # long on Panic onset
        ("XAUUSD", "XAUUSD_raw.csv", "Panic", -1),  # short on Panic onset
    ]

    all_trades = []
    all_results = []

    print("=" * 70)
    print("HYPOTHESIS 1 (already tested, shown for comparison): enter on Panic ONSET")
    print("=" * 70)
    for sym, path, regime, direction in onset_setups:
        df = load_mt5_h1(path, sym)
        signals = compute_regime_signals(df)
        thresholds = calibrate_thresholds(signals)
        classified = classify_regime(signals, thresholds)
        classified = apply_news_lockout(classified)

        entries = find_episode_starts(classified["regime"], regime)
        label = f"{sym} — {'LONG' if direction == 1 else 'SHORT'} on {regime} ONSET (20h horizon, 2x ATR stop)"
        trades = backtest(classified, direction, entries, horizon=20, atr_stop_mult=2.0, symbol=sym)
        result = summarize_trades(trades, label)
        if result:
            all_results.append(result)
        if len(trades) > 0:
            all_trades.append(trades)

    print("\n" + "=" * 70)
    print("HYPOTHESIS 2 (new): enter on Panic EXHAUSTION (episode transitions back out)")
    print("=" * 70)
    exhaustion_setups = [
        ("BTCUSD", "BTCUSD_raw.csv", "Panic", 1),   # long on Panic exhaustion
        ("XAUUSD", "XAUUSD_raw.csv", "Panic", -1),  # short on Panic exhaustion (does the same trick help here?)
    ]
    for sym, path, regime, direction in exhaustion_setups:
        df = load_mt5_h1(path, sym)
        signals = compute_regime_signals(df)
        thresholds = calibrate_thresholds(signals)
        classified = classify_regime(signals, thresholds)
        classified = apply_news_lockout(classified)

        entries = find_episode_ends(classified["regime"], regime)
        label = f"{sym} — {'LONG' if direction == 1 else 'SHORT'} on {regime} EXHAUSTION (20h horizon, 2x ATR stop)"
        trades = backtest(classified, direction, entries, horizon=20, atr_stop_mult=2.0, symbol=sym)
        result = summarize_trades(trades, label)
        if result:
            all_results.append(result)
        if len(trades) > 0:
            all_trades.append(trades)

    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        combined.to_csv("/mnt/user-data/outputs/backtest_trades.csv", index=False)
        pd.DataFrame(all_results).to_csv("/mnt/user-data/outputs/backtest_summary.csv", index=False)
        print(f"\nSaved {len(combined)} trades to backtest_trades.csv, summary to backtest_summary.csv")
