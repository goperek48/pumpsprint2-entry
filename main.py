"""Pump.fun paper sprint bot: catch the launch pop, cash it in, walk away.

Every new coin on a bonding curve gets its verdict in minutes. Across
the house dev window, the typical coin pushed roughly 30% past its
launch price within four minutes, a quarter of them doubled or better,
and barely one in twenty-five held a 25% gain until the day was over.
That shape says the edge lives in the first few minutes of trading and
dies if you overstay: a coin parked for an hour usually drifts back to
where it began, so this bot treats every position as a short visit.

It only steps in once the crowd has shown up. A coin qualifies after
five real trades, while it is still under about four minutes old, with
its price sitting 2% to 25% over launch. Under 2% the rally has not
really begun and the coin might be stillborn; over 25% the cheap part
of the climb is gone and the bot would be handing its money to sellers
heading for the door. The trade also has to be big enough to matter:
the per-coin size limit (1% of real reserves) must have grown to at
least 0.02 SOL before the bot risks anything, and then it stakes that
limit up to 0.15 SOL, a single entry per coin, no second chances.

After entry the bot gives winners room to stretch. It liquidates the
whole stake at +40% above the entry print, at -15%, when the price
retreats 12% from the highest print since entry, or once 600 slots
(around four minutes) have passed, whichever trips first. The generous
profit target follows the dev-window shape -- a full quarter of coins
doubled -- while the tight stop and the trailing exit keep losers
small, since a memecoin that rolls over seldom recovers inside the
window.

Curves that finish are closed by the house, and the house flattens the
whole book when the window ends, so the bot never needs to force an
exit on a dead market.

Hard limits the bot never crosses: no more than five open positions,
no more than sixteen orders in one batch, never committing cash it does
not actually hold after fees, and a 500 bps slippage bound on every
order. No clock, no environment, no unseeded dice: feed it the same
tape twice and the replies match byte for byte.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script dir off sys.path)

# --- strategy knobs, kept together so a sweep can retune them ---
ENTRY_MIN_MULT = 1.02      # enter once the rally has genuinely started:
                           # a 2% lift off launch means the coin is alive
                           # rather than stillborn
ENTRY_MAX_MULT = 1.25      # ... but while the rally is still young: past
                           # +25% the cheap part of the climb is gone and
                           # the bot would be funding other sellers' exits
ENTRY_MIN_TRADES = 5       # ... and the coin has printed real trades, so
                           # there is a crowd behind it, not just a bare
                           # create event
ENTRY_MIN_CAP_LAMPORTS = 20_000_000   # ... and the per-coin size limit has
                           # grown to 0.02 SOL, so the trade is worth the
                           # flat per-order chain fee
ENTRY_WINDOW_SLOTS = 600   # ... and the coin is no more than ~4 min old
MIN_STAKE_LAMPORTS = 10_000_000        # 0.01 SOL: the guardrail round-trip floor
MAX_STAKE_LAMPORTS = 150_000_000       # 0.15 SOL: the largest single stake
TAKE_PROFIT_MULT = 1.40    # liquidate the whole stake at +40% over entry:
                           # a quarter of dev-window coins doubled, so give
                           # the winners room past a plain scalp target
STOP_LOSS_MULT = 0.85      # liquidate the whole stake at -15% under entry
TRAIL_MULT = 0.88          # liquidate it when the price retreats 12% from
                           # its best print since entry
MAX_HOLD_SLOTS = 600       # hard clock: out after ~4 minutes regardless
MAX_SLIPPAGE_BPS = 500     # a fill may land at most 5% worse than the quote


class Trade:
    """One live trade, as the bot remembers it."""

    __slots__ = ("entry", "peak", "opened", "size")

    def __init__(self, entry, opened, size):
        self.entry = entry          # quote per token paid on the first buy
        self.peak = entry           # best quote per token seen since entry
        self.opened = opened        # slot the first buy was decided on
        self.size = size            # lamports the first buy cost


class Bot:
    """Buys each confirmed launcher once, exits fast, never holds more than five."""

    def __init__(self):
        # mint -> launch price (quote per token on the CreateEvent)
        self.launch_price = {}
        # mint -> slot its CreateEvent landed in
        self.born = {}
        # mints bought once already (a dumped coin gets no second entry)
        self.done = set()
        # mint -> Trade for the positions still open
        self.live = {}

    def on_batch(self, state, batch):
        self._note_launches(batch)
        orders = []
        orders += self._close_out(state)
        orders += self._open_new(state, batch)
        return orders

    def _note_launches(self, batch):
        """Remember the launch price of every coin born in this batch."""
        for e in batch["events"]:
            if e["event"] != "CreateEvent":
                continue
            mint = e["mint"]
            # Read the launch price off the event itself: by the time this
            # callback runs, the curve in state already reflects every
            # trade in this batch, so pricing from the curve would value
            # the launch after the first trades of the same slot, not at
            # the moment of creation.
            vt = int(e.get("virtual_token_reserves") or 0)
            vq = int(e.get("virtual_quote_reserves") or 0)
            if vt > 0 and vq > 0:
                self.launch_price[mint] = vq / vt
                self.born[mint] = e["slot"]

    @staticmethod
    def _quote(curve):
        """A curve's current price in quote lamports per token, or None."""
        if curve.virtual_token_reserves <= 0:
            return None
        return curve.virtual_quote_reserves / curve.virtual_token_reserves

    def _close_out(self, state):
        """Liquidate every open trade whose exit rule has tripped."""
        orders = []
        for mint, trade in list(self.live.items()):
            holding = state.positions.get(mint)
            if holding is None or holding.token_amount <= 0:
                # Nothing left to liquidate (already closed by the house
                # or sold): forget the trade.
                del self.live[mint]
                continue
            curve = state.curves.get(mint)
            if curve is None or curve.complete:
                # A finished curve rejects sell orders and the house
                # settles it on its own. Forget the trade.
                if curve is not None and curve.complete:
                    del self.live[mint]
                continue
            price = self._quote(curve)
            if price is None:
                continue
            if price > trade.peak:
                trade.peak = price
            if (
                price >= trade.entry * TAKE_PROFIT_MULT
                or price <= trade.entry * STOP_LOSS_MULT
                or price <= trade.peak * TRAIL_MULT
                or state.slot - trade.opened >= MAX_HOLD_SLOTS
            ):
                orders.append(
                    {
                        "side": "sell",
                        "mint": mint,
                        "token_amount": holding.token_amount,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                )
                del self.live[mint]
        return orders

    def _open_new(self, state, batch):
        """First entries on fresh coins whose rally is confirmed but young."""
        orders = []
        caps = state.hello["caps"]
        tx = state.tx_fee_lamports()
        free = state.free_cash_lamports()
        room = caps["max_open_positions"] - state.committed_position_count()
        if room <= 0:
            return orders
        for e in batch["events"]:
            if len(orders) + len(state.pending) >= caps["max_orders_per_batch"]:
                break
            mint = e["mint"]
            if mint in self.done or mint in self.live:
                continue
            if mint not in self.launch_price:
                continue
            if state.slot - self.born.get(mint, state.slot) > ENTRY_WINDOW_SLOTS:
                continue
            curve = state.curves.get(mint)
            if curve is None or curve.complete:
                continue
            if curve.trades < ENTRY_MIN_TRADES:
                # No crowd behind it yet: a lone create event is not a market.
                continue
            price = self._quote(curve)
            if price is None or price < self.launch_price[mint] * ENTRY_MIN_MULT:
                continue
            if price > self.launch_price[mint] * ENTRY_MAX_MULT:
                # Rally already spent: the climb is exhausted. Wait for a
                # pullback into the window instead of chasing the top.
                continue
            cap = state.max_buy_lamports(mint)
            if cap < ENTRY_MIN_CAP_LAMPORTS:
                continue
            stake = min(cap, MAX_STAKE_LAMPORTS)
            if stake < MIN_STAKE_LAMPORTS:
                continue
            if room <= 0 or free < stake + tx:
                continue
            orders.append(
                {
                    "side": "buy",
                    "mint": mint,
                    "quote_lamports": stake,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            )
            self.done.add(mint)
            self.live[mint] = Trade(price, state.slot, stake)
            free -= stake + tx
            room -= 1
        return orders


def main():
    bot = Bot()
    makefun_bot.run(bot.on_batch)


if __name__ == "__main__":
    main()
