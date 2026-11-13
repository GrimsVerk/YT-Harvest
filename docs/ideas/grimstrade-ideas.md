# GrimsTrade ideas from YouTube (harvest 1)

Testable trading and investing rules, in our own words, for GrimsTrade (paper trading; its own RL
agent is the main goal). The transcripts were inspiration only: they stay local, and the sources
are video ids (`https://youtu.be/<id>`). Data columns refer to the local inventory in
`grimstrade-ingest/docs/data-inventory.md` (as of 2026-11-13).

**Coverage so far: 8 videos (7 with finance content) from 8 of the 12 channels.** The fetch
was stopped by YouTube (HTTP 429) after 8 transcripts (see `next-steps.md`), so this is a
first pass. The plan is each channel's 10 most-viewed + 10 most-recent videos; extend the file
from those once they are fetched. "Channels" counts how many channels make the point.

Verdicts: **testable** (a backtest can decide it with data we have or could get), **vague**
(needs a choice of parameters before it can be tested), **hype** (prediction or narrative, no rule).

## Rules worth testing

### Volatility and momentum extremes as cycle-top signals (crypto)

| # | Rule | Assets, horizon | Data | Verdict | Sources (channels: 1) |
| --- | --- | --- | --- | --- | --- |
| 1 | When the **weekly Bollinger Band Width Percentile** (band width ranked against its own past, e.g. 252-week lookback) rises above ~95, a major top usually comes within 0–2 months: cut exposure or tighten stops. Mirror case: a very low percentile flags a coming breakout (direction unknown). | BTC, weeks to months | BTC daily/1m (have, since 2011) | testable (few cycle tops, so check on many coins and on equities too) | FAIAELKdn7g |
| 2 | **Monthly stochastic RSI** crossing back down out of its overbought zone (above ~80) marks a cycle top; sell into strength after it. | BTC, months | BTC daily (have) | testable, ~4 events for BTC: weak evidence alone; good as an RL feature | FAIAELKdn7g |
| 3 | **Time since the breakout above the old all-time high**: past BTC cycles peaked 42–231 days (mean ~115) after the first weekly close above the previous ATH. Use as a clock: raise exits as the count passes ~100 days. | BTC, months | BTC daily (have) | testable but n = 4; overfitting risk high | FAIAELKdn7g |
| 4 | **Monthly RSI against a falling trend line through past cycle-peak RSI values**: a touch flags the top. | BTC, months | BTC daily (have) | vague (the trend line is drawn by hand; a rolling max of peak RSI would make it testable) | FAIAELKdn7g |
| 5 | **Diminishing returns per cycle**: each BTC cycle's peak-over-previous-peak multiple has fallen (roughly +3,800%, +1,500%, +250%, i.e. ×39, ×16, ×3.5). Use the next ratio in that falling series as a take-profit band. | BTC, cycle | BTC daily (have) | vague (3 data points; useful as a sanity cap, not a signal) | FAIAELKdn7g |
| 6 | **Four-year halving cycle**: BTC tops in the Q4 of the year after a halving, then falls ~70–80%. | BTC, years | BTC daily + halving dates (have/known) | testable, n = 3–4 | FAIAELKdn7g (as the main counter-argument to its own thesis) |

### Macro regimes

| # | Rule | Assets, horizon | Data | Verdict | Sources (channels) |
| --- | --- | --- | --- | --- | --- |
| 7 | **"Wall Street vs Main Street" sentiment gap**: when equities (or consumers' stock-market expectations) sit near highs while consumer sentiment about their own finances is near lows, expect equities to underperform over the next 6–24 months (one side must converge). | SPY/^GSPC, months | U. Michigan sentiment and Conference Board stock-price expectations: **not available** (FRED skipped; Conference Board is paid) | testable once UMich sentiment is downloaded (a long monthly series) | YXFvwJQBzJc, f353QO5Dgus (**2 channels**) |
| 8 | **Oil supply shock regime**: when crude rises very fast (e.g. +50% or more over 6 months, or doubles within a year), cut equity exposure and favour energy/commodities; past shocks (1973, 1990, 2008, 2022) saw equity drawdowns of 20–50%. | SPY, XLE, USO, GLD vs CL=F; months | CL=F and USO daily (have, since ~2000/2006); Shiller lacks oil, so pre-2000 needs another source | testable (few episodes since 2000: 2008, 2022) | f353QO5Dgus |
| 9 | **Yield stress threshold**: a 10-year US yield above ~4.6–4.8% while oil and inflation rise is a "debt stress" regime: underweight long bonds (TLT) and equities. | TLT, SPY vs ^TNX; months | ^TNX daily, Treasury curve since 1990 (have) | testable, but the threshold is narrative; test a range of thresholds and the 3-month change instead | f353QO5Dgus |
| 10 | **Stay long risk assets while money flows in; turn defensive when the trend flips.** Turned into a rule: long SPY, GLD and BTC while each is above its long moving average (e.g. 200-day or 10-month), else cash/short bonds. | SPY, GLD, BTC; months | daily prices (have) | testable (classic trend following: a good baseline for the RL agent) | YXFvwJQBzJc |
| 11 | **Debasement hurdle / "everything code"**: money printing (~8% a year) plus inflation (~3%) sets a ~11% yearly hurdle, so only the "secular bull" assets (tech and crypto) beat it. As an allocation: overweight QQQ/XLK and BTC against SPY, IWM, value and gold miners. | QQQ, XLK, BTC vs SPY/IWM; years | prices (have); M2/Fed balance sheet as a liquidity signal: **not available** (FRED) | testable as an allocation; the liquidity driver needs FRED or another source of M2 | -Xi8Krhy8FQ |

### Sentiment

| # | Rule | Assets, horizon | Data | Verdict | Sources (channels) |
| --- | --- | --- | --- | --- | --- |
| 12 | **Contrarian on famous critics**: when well-known investors loudly dismiss an asset while institutions quietly adopt it, that is bullish. | BTC; months | news/media events: GDELT only has the last 30 days; no long history | vague/hype (no data to count "loud dismissal"; the crypto Fear & Greed index is the testable stand-in: buy extreme fear) | Fnx513JS5Vg |

## Hype, predictions and untestable claims (noted, not rules)

- A US government **revaluation of gold to ~$20,000/oz** to cut debt/GDP (the speaker himself
  puts it at ~10%). A policy event, not a rule. (nEFN-4QQv-o)
- Insiders shorting oil futures minutes before political announcements; paper vs physical oil
  (futures vs dated Brent) must converge "within weeks". Physical-price data not available;
  the timing claim is a one-off prediction. (f353QO5Dgus)
- Fertilizer (urea) prices lead food inflation by 6–12 months: plausible, but no urea or food
  price data in the inventory. (f353QO5Dgus)
- Rising corporate tax rates trigger a "great reset" crash (as in 1929–31): too few events to
  test. (YXFvwJQBzJc)
- An "economic singularity" around 2030 from AI and robotics, then deflation; crypto
  "$2T → $100T" in six years. (-Xi8Krhy8FQ)
- Big-name critics secretly own Bitcoin, a "coordinated FUD campaign". (Fnx513JS5Vg)
- Many titles are fear-driven ("reset", "crash", "rug pull") on Bravos Research and Andrei
  Jikh. In these samples the content is macro narrative with few concrete entry/exit rules.

## Videos read, without trading content

- Mark Tilbury xfOT2elC2Ok: AI dropshipping (a side business, not markets).
- Real Vision 4cwXifDaCjE (2019): political interview about China; no market rules.

## Data gaps these ideas point at (for grimstrade-ingest)

1. University of Michigan consumer sentiment (monthly, from 1952): needed for idea 7 (2 channels).
2. A liquidity series (M2, Fed balance sheet, reverse repo): idea 11; FRED's API needs a free key.
3. Long oil history before 2000 (e.g. EIA, free): idea 8.
