# Polymarket Arbitrage Scanner

This project scans public Polymarket APIs for two simple arbitrage patterns:

- Binary market box arb: buy both outcomes in the same binary market when the combined best asks are below `1.00`.
- Negative-risk event bundle arb: buy every YES outcome in a negative-risk event when the combined best asks are below `1.00`.

It only uses public market metadata and public order books. It does not place trades.

## What it checks

The scanner uses:

- Gamma API for events and market metadata: `https://gamma-api.polymarket.com`
- CLOB API for order books: `https://clob.polymarket.com`

The current Polymarket docs describe:

- Gamma and CLOB base URLs in the API introduction.
- Orderbook access via the public CLOB orderbook endpoint.
- `negRisk` on events for winner-take-all linked outcome sets.
- Fee-enabled markets via `feesEnabled`, which this scanner skips by default.

## Quick start

Run from this folder:

```bash
python3 -m polymarket_arbitrage.cli
```

Useful options:

```bash
python3 -m polymarket_arbitrage.cli --min-edge 0.02 --top 20
python3 -m polymarket_arbitrage.cli --max-events 150 --include-fee-enabled
python3 -m polymarket_arbitrage.cli --slippage-bps 15 --fee-bps 25 --workers 32
python3 -m polymarket_arbitrage.cli --json
```

## Output

Each opportunity includes:

- opportunity type
- event and market titles
- gross bundle cost
- adjusted cost after configured slippage/fee assumptions
- gross and net edge per complete bundle
- available size at the quoted best asks

## Important limits

- This is gross edge, not net PnL. Fees, gas, fills, latency, and partial fills can remove the edge.
- `--slippage-bps` and `--fee-bps` only adjust entry cost. They are a screening approximation, not an exchange-accurate settlement model.
- The negative-risk detector assumes the event’s active markets represent the current complete tradable winner set.
- The scanner uses only top-of-book quotes, so deeper liquidity is not modeled.
- It skips fee-enabled markets by default because taker fees can invalidate naive arbitrage math.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
