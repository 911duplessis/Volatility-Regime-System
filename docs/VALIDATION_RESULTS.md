# QF-X / Volatility Regime System — Status

**Scope:** BTCUSD, EURUSD, XAUUSD, H1, MT5 (JustMarkets). Data: true-H1 history 2020-2026 (D1-disguised-as-H1 broker backfill segment auto-detected and trimmed).

---

## VALIDATED — real evidence behind this

**EURUSD CPI-surprise (the one directional edge that survived everything).** Rule: hot CPI m/m (actual > forecast) → short; cool CPI m/m (actual < forecast) → long. Entry at next-bar-open after release (not the release bar's own close — avoids an unrealistic fill), ATR-multiple stop, 20h horizon, real historical spread cost.

- Backtested on TWO independently-sourced historical forecast datasets (a Kaggle-hosted ForexFactory archive, and a direct export from MT5's own native calendar via `CalendarValueHistoryByEvent`) — positive expectancy on both.
- Held up on genuinely out-of-sample data never seen during pattern discovery: +0.122%/trade on the original 2020–Aug2024 period, **+0.151%/trade on Aug2024–Sep2026** (data the effect was never fit on).
- Consistent across every stop width tested (1.5x–4x ATR): win rate 56–72%, Sharpe/trade 0.25–0.37.
- **This is the only hypothesis, across the entire project, that survived a real backtest, two data sources, and a true out-of-sample check.**

**Important data-integrity finding, worth keeping in mind for any future macro-surprise work:** the two forecast sources agreed on the *actual* released CPI value 56/56 times, but agreed on the *forecast* (consensus) figure only 13/56 times — enough disagreement to flip the trade's direction entirely in 9/56 cases (16%). "Market consensus" is vendor-dependent, not one objective number. This is *why* the BTC and XAU versions of this same rule flipped sign between runs and were discarded (below) — a real signal shouldn't be that sensitive to whose forecast number you use.

**Regime classifier as a risk-sizing filter.** Six states (Calm / Elevated-Bullish / Elevated-Bearish / Panic / Euphoria / News-lockout), percentile-calibrated per instrument from its own history (75th/95th percentile of vol_ratio and atr_ratio, not shared hardcoded thresholds).

- Distribution is consistent across all three instruments (~63-67% Calm, ~25-27% Elevated, ~7-8% Panic/Euphoria combined) — sign the calibration isn't overfit to one instrument's scale.
- Forward-looking test (10h horizon): Panic bars show materially worse tail risk than Calm —
  - BTC: p5 drawdown -7.79% (Panic) vs -4.20% (Calm); forward realized vol 2.64% vs 1.87%
  - XAU: p5 drawdown -2.96% (Panic) vs -1.43% (Calm); forward realized vol 1.13% vs 0.67%
  - EUR: no meaningful separation from Calm at any horizon tested (5h/10h/20h) — the filter does not add value for EUR yet.
- **Conclusion: real for BTC and XAU as an exposure-reduction signal (cut size in Panic/Euphoria). Not established for EUR.**

**Economic calendar coverage — now confirmed on both ends.**
- Python (`news_calendar.py`): FOMC (56 events), NFP (80), CPI (80), 2020-2026, sourced directly from federalreserve.gov and bls.gov.
- MQL5 native calendar integration in `QFX_RiskRegimeEngine.mq5`: **confirmed working live** — Journal showed a real cached event count (16 high-impact events in an 8-day window) and correct regime output (`Calm`, vol_ratio/atr_ratio matching Python's calibrated thresholds closely), with no errors, on a live/demo BTCUSD.m chart. Strategy Tester cannot run Calendar functions at all (`err=4014`, confirmed) — live/demo chart is required and was used.
- `QFX_ExportCalendarHistory.mq5` (new): a one-time script that pulls the *full historical* actual/forecast/previous series for any event via `CalendarValueHistoryByEvent` — this is what produced the free, complete, current-through-Sep-2026 CPI dataset above. Confirmed working: 79 real CPI m/m releases exported, 2020-2026.

**Data pipeline.** MT5 H1 export → auto-detects and trims the daily-bar-disguised-as-H1 segment at the start of each file (~200-250 rows per instrument) → clean true-H1 series (~1,500-2,000+ days per instrument). This mattered: leaving that segment in would have corrupted every rolling volatility/ATR calibration silently.

---

## TESTED AND REJECTED — do not rebuild these without new evidence

**Regime state as a directional signal (not just risk-sizing).** Two hypotheses, both backtested with non-overlapping episode entries, ATR-multiple stops (swept 1.5x-6x), and real historical spread costs:

| Hypothesis | BTC expectancy/trade | XAU expectancy/trade |
|---|---|---|
| Long on Panic **onset** | -0.514% | (short) +0.031% |
| Long on Panic **exhaustion** | -0.381% | (short) +0.041% |

BTC: negative under every stop width tested, including 6x ATR — ruled out as a stop-tightness artifact. The apparent "bounce after Panic" in raw bar-level stats was a measurement artifact (averaging bars mid-episode, near the eventual low, together with the entry bar itself). Not tradeable.

**Liquidity sweep + rejection (swing high/low pierce + close-back).** 5 of 6 directional predictions wrong-signed or noise-level, across BTC/EUR/XAU. Volume confirmation made it worse, not better, in every case it moved the number.

**BTC and XAU CPI-surprise (same rule that works for EUR).** Flipped sign depending on which forecast-data source was used (Kaggle vs. MT5-native) — BTC swung from +0.60% to -0.58% expectancy on the *same* 2020-Aug2024 period depending on data source. XAU was marginal both ways (-0.03% to +0.30%, near-zero on the genuine out-of-sample period). Neither is robust enough to trust; discard both.

**BTC day-of-week / hour-of-day seasonality.** No day clears even an uncorrected p<0.05 threshold against zero (closest: Wednesday, p=0.055). A Wed-vs-Thu comparison showed p=0.016, but that doesn't count — those two were selected *as* the extremes out of seven groups after seeing the data, which inflates apparent significance from pure noise. Null result.

**BTC perpetual-futures funding-rate crowding — untested, not rejected, blocked by data access.** The economic rationale (extreme funding = crowded leveraged positioning = squeeze/mean-reversion risk) was never tested, because no free multi-year historical source was reachable: Binance and Bybit's historical REST endpoints geofence this environment; OKX's public endpoint silently ignores its own pagination parameter and only ever returns the most recent ~33 days regardless of the cursor supplied (confirmed by direct test — page 2 with an explicit `before` cursor returned dates identical to page 1). A live websocket connection *does* work (confirmed: real BTCUSDT tickers streamed successfully), but that only captures data forward from whenever it's started — no help for backtesting against 2020-2026 price history. Closing this as **open, not rejected** — a paid vendor (Coinglass/CryptoQuant) or an unblocked authenticated exchange connection would still be a legitimate way to test it.

**Conclusion: six directional hypotheses tried for BTC specifically (regime-onset, regime-exhaustion, liquidity-sweep, CPI-surprise, day-of-week/session seasonality, plus funding-rate blocked before testing). Five came back negative or null; one is unresolved due to data access, not falsified. BTC's role in this system is the validated risk-sizing layer — no directional edge was found in what could actually be tested.**

**Overall: of five directional hypotheses tested across all instruments (regime-onset, regime-exhaustion, liquidity-sweep, CPI-surprise on BTC/XAU, plus BTC-specific seasonality), only EURUSD CPI-surprise survived. Everything else — price/volume patterns and BTC/XAU macro-surprise alike — failed a real backtest, real costs, or a real out-of-sample check. The search for a BTC-specific directional edge is closed for now; BTC remains validated only as a risk-sizing instrument in the regime engine.**

---

## NOT YET BUILT / OPEN

- **No automated entry logic exists in the MQL5 EA.** It remains monitoring-only by design (regime + recommended risk%, zero trades) — the validated EURUSD CPI-surprise rule has not been ported to MQL5 or connected to any execution.
- **CPI-surprise entries currently require manual action around the monthly release** — no automation built yet for entry timing, position sizing integration with the regime engine, or the actual order placement.
- **Sample size is still modest** even for the surviving EUR result (n=41 original + n=16 out-of-sample = 57 trades total) — real, but thin. More out-of-sample time will keep testing whether it holds.
- **Any new hypothesis should bring genuinely new information** (order flow, options positioning) — OHLCV pattern-slicing has now been tried four ways and yielded nothing durable; macro-surprise data is the one category that worked, and CPI is the only release type tested so far (NFP showed no effect; other releases — PPI, retail sales, jobless claims — remain untested).
- **BTC funding-rate crowding remains untested, not disproven** — the one avenue closed by data access rather than by evidence. Revisit only with a paid vendor (Coinglass/CryptoQuant) or an unblocked authenticated exchange connection; free public REST history for this specific question is not reachable from this environment.

---

## Files delivered this session

`data_loader.py` · `regime_detector.py` · `news_calendar.py` · `main.py` · `validation.py` · `backtest.py` · `liquidity_sweep.py` · `liquidity_sweep_validation.py` · `liquidity_sweep_volume.py` · `surprise_validation.py` · `cpi_surprise_backtest.py` · `QFX_RiskRegimeEngine.mq5` · `QFX_ExportCalendarHistory.mq5` · plus CSV outputs (regime-classified data, backtest trades/summaries, sweep validation, CPI surprise trades, `QFX_CPI_History.csv`).
