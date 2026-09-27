"""
News-lockout calendar.

Covers three event types, each sourced from the issuing agency directly
(not a third-party aggregator like ForexFactory):

- FOMC rate decisions: federalreserve.gov press releases / meeting calendars.
  Date is the SECOND day of each 2-day meeting; time approximated as 18:00 UTC
  (14:00 ET) — actual release time shifts ~1hr across the sample with DST, so
  the blackout window is deliberately wide enough to absorb that.
- NFP (Employment Situation): bls.gov/schedule/ full-year pages for 2020-2024,
  plus BLS's live published calendar (bls.gov/schedule/news_release/bls.ics)
  for 2025-2026. Time is 08:30 ET as published.
- CPI (Consumer Price Index): same sourcing as NFP.

SCOPE NOTE: ECB rate decisions are NOT yet included — would need the same
per-agency sourcing treatment (ecb.europa.eu Governing Council calendar).
Flagging as a gap rather than guessing at dates.

2025 NFP/CPI note: several 2025 releases were delayed by U.S. government
shutdowns (per BLS's own "revised release dates" notice) — the dates below
are the ACTUAL (revised) release dates, not the originally scheduled ones.
"""

import pandas as pd

FOMC_DECISION_DATES = [
    "2020-01-29", "2020-03-18", "2020-04-29", "2020-06-10",
    "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16",
    "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
    "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-11",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# NFP ("Employment Situation") release dates, 08:30 ET, from bls.gov/schedule/
NFP_DATES = [
    "2020-01-10","2020-02-07","2020-03-06","2020-04-03","2020-05-08","2020-06-05",
    "2020-07-02","2020-08-07","2020-09-04","2020-10-02","2020-11-06","2020-12-04",
    "2021-01-08","2021-02-05","2021-03-05","2021-04-02","2021-05-07","2021-06-04",
    "2021-07-02","2021-08-06","2021-09-03","2021-10-08","2021-11-05","2021-12-03",
    "2022-01-07","2022-02-04","2022-03-04","2022-04-01","2022-05-06","2022-06-03",
    "2022-07-08","2022-08-05","2022-09-02","2022-10-07","2022-11-04","2022-12-02",
    "2023-01-06","2023-02-03","2023-03-10","2023-04-07","2023-05-05","2023-06-02",
    "2023-07-07","2023-08-04","2023-09-01","2023-10-06","2023-11-03","2023-12-08",
    "2024-01-05","2024-02-02","2024-03-08","2024-04-05","2024-05-03","2024-06-07",
    "2024-07-05","2024-08-02","2024-09-06","2024-10-04","2024-11-01","2024-12-06",
    "2025-01-10","2025-02-07","2025-03-07","2025-04-04","2025-05-02","2025-06-06",
    "2025-07-03","2025-08-01","2025-09-05","2025-11-20","2025-12-16",
    "2026-01-09","2026-02-11","2026-03-06","2026-04-03","2026-05-08","2026-06-05",
    "2026-07-02","2026-08-07","2026-09-04",
]

# CPI release dates, 08:30 ET, from bls.gov/schedule/
CPI_DATES = [
    "2020-01-14","2020-02-13","2020-03-11","2020-04-10","2020-05-12","2020-06-10",
    "2020-07-14","2020-08-12","2020-09-11","2020-10-13","2020-11-12","2020-12-10",
    "2021-01-13","2021-02-10","2021-03-10","2021-04-13","2021-05-12","2021-06-10",
    "2021-07-13","2021-08-11","2021-09-14","2021-10-13","2021-11-10","2021-12-10",
    "2022-01-12","2022-02-10","2022-03-10","2022-04-12","2022-05-11","2022-06-10",
    "2022-07-13","2022-08-10","2022-09-13","2022-10-13","2022-11-10","2022-12-13",
    "2023-01-12","2023-02-14","2023-03-14","2023-04-12","2023-05-10","2023-06-13",
    "2023-07-12","2023-08-10","2023-09-13","2023-10-12","2023-11-14","2023-12-12",
    "2024-01-11","2024-02-13","2024-03-12","2024-04-10","2024-05-15","2024-06-12",
    "2024-07-11","2024-08-14","2024-09-11","2024-10-10","2024-11-13","2024-12-11",
    "2025-01-15","2025-02-12","2025-03-12","2025-04-10","2025-05-13","2025-06-11",
    "2025-07-15","2025-08-12","2025-09-11","2025-10-24","2025-12-18",
    "2026-01-13","2026-02-13","2026-03-11","2026-04-10","2026-05-12","2026-06-10",
    "2026-07-14","2026-08-12","2026-09-11",
]


def build_blackout_index(index: pd.DatetimeIndex, window_hours: int = 2) -> pd.Series:
    """
    Returns a boolean Series aligned to `index`: True where a bar falls inside
    the news-lockout window around any FOMC / NFP / CPI event.

    NOTE: FOMC times are UTC-based (18:00 UTC approximation); NFP/CPI times are
    08:30 US-Eastern as BLS publishes them. Broker server time (this data's
    index) is typically UTC or UTC+2/+3 — if bars land off by 1-2 hours from
    expected, check your broker's timestamp convention against ET/UTC.
    """
    fomc_times = pd.to_datetime(FOMC_DECISION_DATES) + pd.Timedelta(hours=18)
    nfp_times = pd.to_datetime(NFP_DATES) + pd.Timedelta(hours=13, minutes=30)  # 08:30 ET -> 13:30 UTC (standard)
    cpi_times = pd.to_datetime(CPI_DATES) + pd.Timedelta(hours=13, minutes=30)

    all_events = pd.concat([
        pd.Series(fomc_times), pd.Series(nfp_times), pd.Series(cpi_times)
    ]).reset_index(drop=True)

    blackout = pd.Series(False, index=index)
    for et in all_events:
        start = et - pd.Timedelta(hours=window_hours)
        end = et + pd.Timedelta(hours=window_hours)
        blackout |= (index >= start) & (index <= end)
    return blackout


def apply_news_lockout(classified: pd.DataFrame, window_hours: int = 2) -> pd.DataFrame:
    out = classified.copy()
    blackout = build_blackout_index(out.index, window_hours=window_hours)
    out.loc[blackout, "regime"] = "News-lockout"
    out.loc[blackout, "size_multiplier"] = 0.0
    out["news_blackout"] = blackout
    return out


if __name__ == "__main__":
    from data_loader import load_mt5_h1
    from regime_detector import compute_regime_signals, calibrate_thresholds, classify_regime, summarize_regime

    df = load_mt5_h1("EURUSD_raw.csv", "EURUSD")
    signals = compute_regime_signals(df)
    thresholds = calibrate_thresholds(signals)
    classified = classify_regime(signals, thresholds)
    final = apply_news_lockout(classified)

    def _in_range(dates):
        return sum(1 for d in dates if df.index.min() <= pd.Timestamp(d) <= df.index.max())
    print(f"FOMC events in range: {_in_range(FOMC_DECISION_DATES)}  "
          f"NFP: {_in_range(NFP_DATES)}  CPI: {_in_range(CPI_DATES)}")
    print(f"Bars flagged News-lockout: {final['news_blackout'].sum()}")
    summarize_regime(final, "EURUSD (with news-lockout)")
