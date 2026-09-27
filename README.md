# QF-X — Volatility Regime & Risk-Sizing System

**Status: risk-sizing layer validated and tested. No validated directional
entry exists for BTC or XAU. One validated entry exists for EURUSD
(CPI m/m surprise). No live trading or broker credentials in this repo.**

This README states only what has actually been run and verified in this
package — see `docs/VALIDATION_RESULTS.md` for the full evidence trail,
including everything that was tried and rejected.

## What's here

- `qfx/data_loader.py` — MT5 H1 CSV loader. Auto-detects and trims a real
  data-quality bug found during this project: some brokers backfill history
  beyond their stored intraday depth with one daily bar per day, disguised
  as H1 (always stamped 00:00:00). Left in, this silently corrupts every
  rolling volatility calculation. Tested in `tests/test_data_loader.py`.
- `qfx/regime_detector.py` — six-state regime classifier (Calm /
  Elevated-Bullish / Elevated-Bearish / Panic / Euphoria), percentile-
  calibrated per instrument from its own history. Tested in
  `tests/test_regime.py` against synthetic data with a known injected
  volatility spike.
- `qfx/risk.py` — the risk gate: regime → size multiplier, and an equity
  drawdown kill-switch with no auto-recovery. Tested in `tests/test_risk.py`.
- `qfx/news_calendar.py` — FOMC/NFP/CPI event calendar (2020-2026), sourced
  directly from federalreserve.gov and bls.gov.
- `qfx/backtest.py`, `qfx/validation.py` — the backtest and forward-return
  validation harnesses used to test every hypothesis in this project.

## What's validated (with real numbers)

- **Regime as a risk-sizing filter (BTC, XAU):** Panic bars show roughly
  double the forward tail risk of Calm (10h p5 drawdown: BTC -7.79% vs
  -4.20%; XAU -2.96% vs -1.43%). Not established for EUR.
- **EURUSD CPI-surprise entry:** hot CPI → short, cool CPI → long. Survived
  two independent historical forecast-data sources and genuine out-of-
  sample data (Aug 2024–Sep 2026) the pattern was never fit on. Small
  sample (57 trades total) — real, but thin.

## What was tested and rejected — do not rebuild without new evidence

- Regime state as a directional signal (Panic onset, Panic exhaustion) — BTC
  negative under every ATR-stop width tested (1.5x–6x); XAU flat.
- Liquidity sweep + rejection (raw and volume-confirmed) — wrong-signed or
  noise-level on all three instruments.
- CPI-surprise on BTC and XAU (same rule that works for EUR) — flipped sign
  depending on which forecast-data source was used. Not robust; discarded.
- BTC day-of-week / session seasonality — null (no day clears p<0.05 even
  uncorrected).

Full detail, including the exact numbers and why each one failed, is in
`docs/VALIDATION_RESULTS.md`.

## Running the tests

```
pip install -e ".[dev]"
pytest tests/
```

12 tests, currently all passing (data loader trimming, regime calibration,
risk gate, drawdown kill-switch). This has actually been run — see the test
output in `docs/VALIDATION_RESULTS.md` for the real pass/fail record, not
a self-reported confidence number.

## MQL5 execution layer

Lives outside this Python package (separate `.mq5` files): `QFX_Protector.mq5`
(active risk enforcement — closes positions on Panic/Euphoria/News-lockout,
drawdown kill-switch) and `QFX_EURCPISurprise.mq5` (the validated entry,
gated on the Protector's published state). Confirmed compiling and running
on a live/demo MT5 chart; the position-management logic in these two files
has not yet been exercised through a real trade cycle — demo-test before
trusting either with size.
