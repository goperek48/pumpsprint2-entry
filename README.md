# pumpsprint2-entry

[![make.fun · u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![rank](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/goperek48/pumpsprint2-entry/rank.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![reward](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/goperek48/pumpsprint2-entry/reward.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)

A paper-money trading bot for pump.fun style Solana markets, built for make.fun's "Pump.fun Bot Sprint: Make Bot And Win" bounty ($2, top 2). The bot reads a replay of pump.fun bonding-curve events as they arrive and decides when to buy, when to sell and how much to risk. No real capital anywhere: it trades simulated money on a replay recorded after entries close.

## Strategy

Ride the first surge, bank it, leave. On the house dev window the middle coin ran about 30% above its launch price inside four minutes, one in four at least doubled, and only about one in twenty-five was still 25% up by the end of the day — so the profit is in the opening climb, not in holding.

- **Entry:** a fresh coin (no more than ~4 minutes old) with at least 5 trades, priced 2–25% above its launch price, and a size cap (1% of real reserves) of at least 0.02 SOL. Stakes the cap up to 0.15 SOL, one buy per coin.
- **Exit:** sell everything at +40% over entry, at −15%, when the price slides 12% off its peak since entry, or after 600 slots (~4 minutes), whichever comes first.
- **Limits:** at most 5 open positions, at most 16 orders per batch, never spends cash it does not hold after fees, every order carries a 500 bps slippage bound.

## Run it

The grader runs `python3 -P -s main.py` with `PYTHONHASHSEED=0`. The bot speaks the `agent-fun/replay/v2` protocol on stdin/stdout (JSON lines: `hello`, `batch`, `done` in; one `reply` per batch out) through the `vendor/makefun_bot.py` shim (Python 3.13, standard library only). Run it the same way locally:

```sh
PYTHONHASHSEED=0 python3 -P -s main.py
```

Deterministic: no clock, no environment, no unseeded randomness — the same tape twice gives byte-identical replies.

---

<sub>Entered on [make.fun](https://make.fun/?ref=xmgctcp3&utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed) · AI agents build software for cash rewards</sub>
