import pandas as pd
from qfx.data_loader import load_mt5_h1


def _write_synthetic_mt5_csv(path):
    """
    Mimics the real bug found in this project: MT5 broker history that
    backfills beyond its stored intraday depth with one daily bar per day
    (always stamped 00:00:00), disguised as H1. Three daily-only days,
    then two real multi-bar days.
    """
    lines = ["<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"]
    for day in ["2024.01.01", "2024.01.02", "2024.01.03"]:
        lines.append(f"{day}\t00:00:00\t1.1000\t1.1010\t1.0990\t1.1005\t500\t0\t10")
    for hour in range(24):
        lines.append(f"2024.01.04\t{hour:02d}:00:00\t1.1005\t1.1008\t1.1002\t1.1006\t50\t0\t10")
    for hour in range(24):
        lines.append(f"2024.01.05\t{hour:02d}:00:00\t1.1006\t1.1009\t1.1003\t1.1007\t50\t0\t10")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def test_trims_daily_disguised_segment(tmp_path):
    csv_path = tmp_path / "synthetic.csv"
    _write_synthetic_mt5_csv(csv_path)

    df = load_mt5_h1(str(csv_path), "TEST")

    # The three daily-only rows (Jan 1-3) must be gone; only the 48 true
    # hourly bars (Jan 4-5) should remain.
    assert len(df) == 48
    assert df.index.min() == pd.Timestamp("2024-01-04 00:00:00")
    assert df.attrs["true_h1_start"] == pd.Timestamp("2024-01-04")
    assert df.attrs["rows_dropped"] == 3


def test_raises_if_no_true_h1_segment_exists(tmp_path):
    """If every day in the file only has one bar, there's no true-H1
    segment to find — the loader should say so clearly rather than
    silently return daily-disguised data as if it were hourly."""
    csv_path = tmp_path / "all_daily.csv"
    lines = ["<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"]
    for day in ["2024.01.01", "2024.01.02"]:
        lines.append(f"{day}\t00:00:00\t1.1000\t1.1010\t1.0990\t1.1005\t500\t0\t10")
    with open(csv_path, "w") as f:
        f.write("\n".join(lines))

    try:
        load_mt5_h1(str(csv_path), "TEST")
        assert False, "expected ValueError for all-daily data, none was raised"
    except ValueError as e:
        assert "no multi-bar days found" in str(e)
