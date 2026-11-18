# GTA VI Twitch CCU forecast

Forecasts hour-by-hour GTA VI Twitch viewers from an hour-1 anchor and comparable past launches.

Bounty: https://make.fun/bounty/gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adofl/makefun-gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adofl/makefun-gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

## Run locally

Requires Python 3.13 or newer; no third-party packages.

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` reads every `*.in` case from `MAKEFUN_INPUT_DIR` and writes one `<id>.out` per case into `MAKEFUN_OUTPUT_DIR` (created if missing).

## Model

Each comparable contributes a curve of `log(viewers / hour-1 viewers)` for hours 1–24, weighted by `exp(-days/400)` from its `day_start` to the case's. At each forecast hour the weighted mean and variance set the center and spread (standard deviation clamped to 0.05–0.9); the mean is blended 65/35 with a generic `-0.18 * log(h)` decay. Five quantiles (`z` = -1.645, -0.674, 0, 0.674, 1.645) are exponentiated from the hour-1 anchor, clamped to `[0.01, 1e9]`, rounded to two decimals, and sorted.
