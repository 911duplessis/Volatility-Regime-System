"""
Risk gate — the validated risk-sizing rule, as a pure, testable function.

This is the Python mirror of QFX_Protector.mq5's enforcement logic:
size multiplier by regime state, and an equity-drawdown kill-switch.
Kept here as plain functions (not a class with hidden state) so each
piece is independently testable — a risk gate that's hard to test in
isolation is a risk gate you can't fully trust in production either.
"""

from dataclasses import dataclass

# Validated regime -> size multiplier mapping. Panic/Euphoria cut to zero
# is not a guess — it's backed by the actual backtest: Panic bars showed
# roughly double the forward tail risk of Calm on both BTC and XAU
# (p5 drawdown -7.79% vs -4.20% on BTC at 10h; -2.96% vs -1.43% on XAU).
REGIME_SIZE_MULTIPLIERS = {
    "Calm": 1.0,
    "Elevated-Bullish": 0.5,
    "Elevated-Bearish": 0.5,
    "Panic": 0.0,
    "Euphoria": 0.0,
    "News-Lockout": 0.0,
    "Unknown": 0.0,
}


def size_multiplier_for(regime: str) -> float:
    """Returns the validated size multiplier for a regime state.
    Unrecognized regime strings are treated as Unknown (0.0) — failing
    closed (no size) rather than open (full size) on a bad/unexpected
    input is the correct default for a risk gate."""
    return REGIME_SIZE_MULTIPLIERS.get(regime, 0.0)


@dataclass
class DrawdownState:
    peak_equity: float
    halted: bool = False


def update_drawdown_state(state: DrawdownState, current_equity: float,
                           max_drawdown_pct: float) -> DrawdownState:
    """
    Pure update function — given the current state and equity reading,
    returns the new state. Mirrors QFX_Protector.mq5's kill-switch:
    peak only ratchets up, and once halted it STAYS halted (no
    auto-recovery) until something external clears it — a kill-switch
    that quietly re-arms itself on its own isn't a kill-switch.
    """
    if state.halted:
        return state  # stays halted regardless of equity moving back up

    new_peak = max(state.peak_equity, current_equity)
    drawdown_pct = (new_peak - current_equity) / new_peak * 100.0 if new_peak > 0 else 0.0
    halted = drawdown_pct >= max_drawdown_pct

    return DrawdownState(peak_equity=new_peak, halted=halted)
