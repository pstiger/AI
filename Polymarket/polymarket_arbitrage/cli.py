from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

from .api import PolymarketApiError
from .scanner import scan_opportunities


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan Polymarket for simple arbitrage opportunities.")
    parser.add_argument("--min-edge", default="0.01", help="Minimum net edge per bundle. Default: 0.01")
    parser.add_argument("--max-events", type=int, default=100, help="Maximum active events to scan. Default: 100")
    parser.add_argument("--top", type=int, default=10, help="Number of opportunities to print. Default: 10")
    parser.add_argument(
        "--slippage-bps",
        default="0",
        help="Add slippage to cost in basis points. Example: 15 = 0.15%%. Default: 0",
    )
    parser.add_argument(
        "--fee-bps",
        default="0",
        help="Add fee assumption to cost in basis points. Default: 0",
    )
    parser.add_argument("--workers", type=int, default=16, help="Concurrent orderbook requests. Default: 16")
    parser.add_argument(
        "--include-fee-enabled",
        action="store_true",
        help="Include fee-enabled markets. Off by default because fees can erase the edge.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of plain text.")
    return parser


def _serialize(opportunity):
    return {
        "kind": opportunity.kind,
        "event_title": opportunity.event_title,
        "market_title": opportunity.market_title,
        "gross_cost": str(opportunity.gross_cost),
        "gross_payout": str(opportunity.gross_payout),
        "gross_edge": str(opportunity.gross_edge),
        "adjusted_cost": str(opportunity.adjusted_cost),
        "net_edge": str(opportunity.net_edge),
        "max_size": str(opportunity.max_size),
        "legs": [
            {
                "outcome": leg.outcome,
                "token_id": leg.token_id,
                "ask_price": str(leg.ask_price),
                "ask_size": str(leg.ask_size),
            }
            for leg in opportunity.legs
        ],
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        min_edge = Decimal(args.min_edge)
        slippage_bps = Decimal(args.slippage_bps)
        fee_bps = Decimal(args.fee_bps)
    except Exception:
        parser.error("--min-edge, --slippage-bps, and --fee-bps must be decimal values")
        return 2

    try:
        opportunities = scan_opportunities(
            min_edge=min_edge,
            max_events=args.max_events,
            slippage_bps=slippage_bps,
            fee_bps=fee_bps,
            include_fee_enabled=args.include_fee_enabled,
            workers=args.workers,
        )
    except PolymarketApiError as exc:
        print(f"Polymarket API error: {exc}", file=sys.stderr)
        return 1
    selected = opportunities[: args.top]

    if args.json:
        print(json.dumps([_serialize(item) for item in selected], indent=2))
        return 0

    if not selected:
        print("No opportunities found with the current filters.")
        return 0

    for index, opportunity in enumerate(selected, start=1):
        print(f"{index}. [{opportunity.kind}] {opportunity.event_title}")
        print(f"   Market(s): {opportunity.market_title}")
        print(
            f"   Gross cost: {opportunity.gross_cost}  Adjusted cost: {opportunity.adjusted_cost}  "
            f"Payout: {opportunity.gross_payout}"
        )
        print(f"   Gross edge: {opportunity.gross_edge}  Net edge: {opportunity.net_edge}")
        print(f"   Max size at best asks: {opportunity.max_size}")
        print("   Legs:")
        for leg in opportunity.legs:
            print(
                f"     - {leg.outcome or 'Outcome'} token {leg.token_id}: "
                f"ask {leg.ask_price} size {leg.ask_size}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
