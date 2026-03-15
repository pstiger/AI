from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from polymarket_arbitrage.models import Event, Market, TokenQuote
from polymarket_arbitrage.scanner import (
    _collect_quotes,
    find_binary_market_arbs,
    find_neg_risk_bundle_arbs,
)


class ScannerTests(TestCase):
    def test_binary_box_arb_detected(self) -> None:
        event = Event(
            id="1",
            title="Election",
            slug="election",
            active=True,
            closed=False,
            archived=False,
            neg_risk=False,
            markets=[
                Market(
                    id="m1",
                    question="Will X win?",
                    slug="will-x-win",
                    event_id="1",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=False,
                    tokens=[("Yes", "yes-token"), ("No", "no-token")],
                )
            ],
        )

        prices = {
            "yes-token": TokenQuote("yes-token", "Yes", Decimal("0.47"), Decimal("150")),
            "no-token": TokenQuote("no-token", "No", Decimal("0.48"), Decimal("90")),
        }

        with patch(
            "polymarket_arbitrage.scanner.fetch_best_ask",
            side_effect=lambda token_id: prices[token_id],
        ):
            quote_map = _collect_quotes([event], False, 2)
            opportunities = find_binary_market_arbs(
                [event], quote_map, Decimal("0.01"), Decimal("0"), Decimal("0"), False
            )

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].gross_edge, Decimal("0.05"))
        self.assertEqual(opportunities[0].net_edge, Decimal("0.05"))
        self.assertEqual(opportunities[0].max_size, Decimal("90"))

    def test_fee_enabled_market_skipped_by_default(self) -> None:
        event = Event(
            id="1",
            title="Crypto",
            slug="crypto",
            active=True,
            closed=False,
            archived=False,
            neg_risk=False,
            markets=[
                Market(
                    id="m1",
                    question="BTC above 100k?",
                    slug="btc-above-100k",
                    event_id="1",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=True,
                    tokens=[("Yes", "yes-token"), ("No", "no-token")],
                )
            ],
        )

        with patch("polymarket_arbitrage.scanner.fetch_best_ask") as mocked_fetch:
            quote_map = _collect_quotes([event], False, 2)
            opportunities = find_binary_market_arbs(
                [event], quote_map, Decimal("0.01"), Decimal("0"), Decimal("0"), False
            )

        self.assertEqual(opportunities, [])
        mocked_fetch.assert_not_called()

    def test_neg_risk_bundle_detected(self) -> None:
        event = Event(
            id="2",
            title="Who wins?",
            slug="who-wins",
            active=True,
            closed=False,
            archived=False,
            neg_risk=True,
            markets=[
                Market(
                    id="a",
                    question="Alice",
                    slug="alice",
                    event_id="2",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=False,
                    tokens=[("Yes", "alice-yes"), ("No", "alice-no")],
                ),
                Market(
                    id="b",
                    question="Bob",
                    slug="bob",
                    event_id="2",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=False,
                    tokens=[("Yes", "bob-yes"), ("No", "bob-no")],
                ),
                Market(
                    id="c",
                    question="Carol",
                    slug="carol",
                    event_id="2",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=False,
                    tokens=[("Yes", "carol-yes"), ("No", "carol-no")],
                ),
            ],
        )

        prices = {
            "alice-yes": TokenQuote("alice-yes", "Yes", Decimal("0.31"), Decimal("25")),
            "alice-no": TokenQuote("alice-no", "No", Decimal("0.72"), Decimal("25")),
            "bob-yes": TokenQuote("bob-yes", "Yes", Decimal("0.29"), Decimal("50")),
            "bob-no": TokenQuote("bob-no", "No", Decimal("0.74"), Decimal("50")),
            "carol-yes": TokenQuote("carol-yes", "Yes", Decimal("0.30"), Decimal("18")),
            "carol-no": TokenQuote("carol-no", "No", Decimal("0.71"), Decimal("18")),
        }

        with patch(
            "polymarket_arbitrage.scanner.fetch_best_ask",
            side_effect=lambda token_id: prices[token_id],
        ):
            quote_map = _collect_quotes([event], False, 3)
            opportunities = find_neg_risk_bundle_arbs(
                [event], quote_map, Decimal("0.01"), Decimal("0"), Decimal("0"), False
            )

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].gross_cost, Decimal("0.90"))
        self.assertEqual(opportunities[0].gross_edge, Decimal("0.10"))
        self.assertEqual(opportunities[0].net_edge, Decimal("0.10"))
        self.assertEqual(opportunities[0].max_size, Decimal("18"))

    def test_net_edge_respects_cost_adjustments(self) -> None:
        event = Event(
            id="1",
            title="Election",
            slug="election",
            active=True,
            closed=False,
            archived=False,
            neg_risk=False,
            markets=[
                Market(
                    id="m1",
                    question="Will X win?",
                    slug="will-x-win",
                    event_id="1",
                    active=True,
                    closed=False,
                    archived=False,
                    fees_enabled=False,
                    tokens=[("Yes", "yes-token"), ("No", "no-token")],
                )
            ],
        )

        prices = {
            "yes-token": TokenQuote("yes-token", "Yes", Decimal("0.47"), Decimal("150")),
            "no-token": TokenQuote("no-token", "No", Decimal("0.48"), Decimal("90")),
        }

        with patch(
            "polymarket_arbitrage.scanner.fetch_best_ask",
            side_effect=lambda token_id: prices[token_id],
        ):
            quote_map = _collect_quotes([event], False, 2)
            opportunities = find_binary_market_arbs(
                [event], quote_map, Decimal("0.04"), Decimal("100"), Decimal("100"), False
            )

        self.assertEqual(opportunities, [])
