---
name: spec
---

# broker

- alpaca supplies market data and order execution
- paper and live credentials are separate
- live startup requires explicit confirmation
- foreign spy positions or orders prevent startup

# opening range

- spy is the default instrument
- five one-minute bars form the range from 09:30 through 09:35 et
- the first later close outside the range defines the breakout
- one entry is allowed per trading day
- all bot positions close by 15:55 et

# entry

- an upper breakout enters long
- a lower breakout enters short
- fractional quantities are allowed for long entries
- whole quantities are required for short entries
- an invalid risk-sized quantity prevents entry

# risk

- planned stop loss does not exceed $0.80
- the opposite opening-range boundary sets the protective stop
- a rejected protective stop causes an immediate flatten request
- a daily loss of $1 disables entries and causes a flatten request
- gaps and slippage can make realized loss exceed $1

# recovery

- bot order identifiers and position state persist locally
- restart accepts only broker state owned by the bot
- a position carried into another session causes a flatten request
- a normal end-of-session state has no open position
