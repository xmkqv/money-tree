---
name: spec
terms: names.yaml
---

# system

- opening-range and momentum-long support backtest, paper, and live trading
- spy is the default instrument
- alpaca and lumibot provide the external trading environment
- live startup requires the literal confirmation `live`

# opening-range

- five one-minute bars form the opening range from 09:30 through 09:35 eastern time
- the first later close outside the opening range defines the breakout
- an upper breakout decides a long direction
- a lower breakout decides a short direction
- at most one entry occurs in each trading session
- the strategy flattens by 15:55 eastern time

## opening-range risk

- planned loss does not exceed $0.80
- the opposite opening range boundary sets the protective stop price
- long entries may use fractional quantities
- short entries use whole quantities
- a quantity below the broker minimum prevents entry
- a $1 session loss disables entry and starts flattening

# momentum-long

- the strategy observes 260 daily bars
- the strategy decides only a long or flat direction
- an entry uses ten percent of portfolio value
- entry quantities use whole instrument units
- one entry may occur in each trading session

## momentum-long entry

- the previous close is below its 20-bar simple moving average
- the current close is above its 20-bar and 50-bar simple moving averages
- the 50-bar simple moving average is above the 200-bar simple moving average
- the 14-bar relative strength index is from 50 through 70
- the 14-bar average directional index exceeds 25
- the latest two-bar swing low exists below the current close

## momentum-long protection

- the initial protective stop is one cent below the swing low
- two times initial price risk activates the trailing protective stop
- the trailing distance is 1.5 times the 14-bar average true range
- the trailing protective stop never moves below its initial price
- a close below the 20-bar simple moving average with relative strength index below 50 flattens

# execution constraints

- a rejected protective stop starts immediate flattening
- a canceled protective stop on an open position starts immediate flattening
- protective stop failure disables entry for the trading session
- a flatten order rejection stops the process with an error
- gaps and transaction costs can make realized loss exceed a risk limit

# recovery

- persisted state restores system control after a process restart

## persistence

- strategy identity, instrument identity, position state, and owned orders persist locally
- opening-range session controls and protective stop price persist locally
- momentum-long entry, protective stop, trail activation, and highest prices persist locally
- each order or fill transition saves state with an atomic file replacement

## reconciliation

- startup rejects corrupt state or an identity mismatch
- startup rejects a broker position that is not an owned position
- startup rejects a broker order that is not an owned order
- missing owned orders clear stale identifiers
- an owned open position restores its protective stop before a new decision
