from qfx.risk import size_multiplier_for, update_drawdown_state, DrawdownState


def test_calm_gets_full_size():
    assert size_multiplier_for("Calm") == 1.0


def test_panic_and_euphoria_cut_to_zero():
    # This is the actual validated finding, not an assumption: Panic/Euphoria
    # showed materially worse forward tail risk in the real backtest.
    assert size_multiplier_for("Panic") == 0.0
    assert size_multiplier_for("Euphoria") == 0.0


def test_elevated_states_cut_to_half():
    assert size_multiplier_for("Elevated-Bullish") == 0.5
    assert size_multiplier_for("Elevated-Bearish") == 0.5


def test_unrecognized_regime_fails_closed():
    # A risk gate should fail to zero size on bad input, not full size.
    assert size_multiplier_for("SomethingUnexpected") == 0.0


def test_drawdown_peak_ratchets_up_only():
    state = DrawdownState(peak_equity=1000.0)
    state = update_drawdown_state(state, current_equity=1100.0, max_drawdown_pct=10.0)
    assert state.peak_equity == 1100.0
    state = update_drawdown_state(state, current_equity=1050.0, max_drawdown_pct=10.0)
    assert state.peak_equity == 1100.0  # peak does not fall back down


def test_drawdown_triggers_halt_at_threshold():
    state = DrawdownState(peak_equity=1000.0)
    # 9% drawdown, threshold 10% -> should NOT halt yet
    state = update_drawdown_state(state, current_equity=910.0, max_drawdown_pct=10.0)
    assert state.halted is False
    # 10% drawdown exactly -> should halt
    state = update_drawdown_state(state, current_equity=900.0, max_drawdown_pct=10.0)
    assert state.halted is True


def test_halt_does_not_auto_recover():
    state = DrawdownState(peak_equity=1000.0, halted=True)
    # Equity fully recovers to a new high — should NOT un-halt on its own
    state = update_drawdown_state(state, current_equity=1200.0, max_drawdown_pct=10.0)
    assert state.halted is True
    assert state.peak_equity == 1000.0  # frozen — halted state doesn't update peak either
