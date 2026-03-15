from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from .api import fetch_active_events, fetch_best_ask
from .models import Event, Opportunity, TokenQuote

ONE = Decimal("1")
TEN_THOUSAND = Decimal("10000")


def _market_is_eligible(market, include_fee_enabled: bool) -> bool:
    if not market.active or market.closed or market.archived:
        return False
    if market.fees_enabled and not include_fee_enabled:
        return False
    return True


def _collect_quotes(events: list[Event], include_fee_enabled: bool, workers: int) -> dict[str, TokenQuote]:
    token_map: dict[str, str] = {}
    for event in events:
        for market in event.markets:
            if not _market_is_eligible(market, include_fee_enabled):
                continue
            for outcome, token_id in market.tokens:
                if token_id and token_id not in token_map:
                    token_map[token_id] = outcome

    if not token_map:
        return {}

    quotes: dict[str, TokenQuote] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {
            executor.submit(fetch_best_ask, token_id): (token_id, outcome)
            for token_id, outcome in token_map.items()
        }
        for future, (token_id, outcome) in future_map.items():
            quote = future.result()
            if quote is None:
                continue
            quote.outcome = outcome
            quotes[token_id] = quote
    return quotes


def _quotes_for_market(market, quote_map: dict[str, TokenQuote]) -> list[TokenQuote]:
    quotes: list[TokenQuote] = []
    for outcome, token_id in market.tokens:
        quote = quote_map.get(token_id)
        if quote is None:
            return []
        quotes.append(
            TokenQuote(
                token_id=quote.token_id,
                outcome=outcome,
                ask_price=quote.ask_price,
                ask_size=quote.ask_size,
            )
        )
    return quotes


def _adjusted_cost(gross_cost: Decimal, slippage_bps: Decimal, fee_bps: Decimal) -> Decimal:
    return gross_cost * (ONE + ((slippage_bps + fee_bps) / TEN_THOUSAND))


def find_binary_market_arbs(
    events: list[Event],
    quote_map: dict[str, TokenQuote],
    min_edge: Decimal,
    slippage_bps: Decimal,
    fee_bps: Decimal,
    include_fee_enabled: bool,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []

    for event in events:
        for market in event.markets:
            if not _market_is_eligible(market, include_fee_enabled):
                continue
            if len(market.tokens) != 2:
                continue

            quotes = _quotes_for_market(market, quote_map)
            if len(quotes) != 2:
                continue

            gross_cost = sum((quote.ask_price for quote in quotes), start=Decimal("0"))
            gross_edge = ONE - gross_cost
            adjusted_cost = _adjusted_cost(gross_cost, slippage_bps, fee_bps)
            net_edge = ONE - adjusted_cost
            if net_edge < min_edge:
                continue

            max_size = min((quote.ask_size for quote in quotes), default=Decimal("0"))
            if max_size <= 0:
                continue

            opportunities.append(
                Opportunity(
                    kind="binary_box",
                    event_title=event.title,
                    market_title=market.question,
                    legs=quotes,
                    gross_cost=gross_cost,
                    gross_payout=ONE,
                    gross_edge=gross_edge,
                    adjusted_cost=adjusted_cost,
                    net_edge=net_edge,
                    max_size=max_size,
                )
            )

    return opportunities


def find_neg_risk_bundle_arbs(
    events: list[Event],
    quote_map: dict[str, TokenQuote],
    min_edge: Decimal,
    slippage_bps: Decimal,
    fee_bps: Decimal,
    include_fee_enabled: bool,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []

    for event in events:
        if not event.neg_risk:
            continue

        quotes: list[TokenQuote] = []
        market_titles: list[str] = []
        for market in event.markets:
            if not _market_is_eligible(market, include_fee_enabled):
                continue
            if len(market.tokens) != 2:
                continue

            market_quotes = _quotes_for_market(market, quote_map)
            if len(market_quotes) != 2:
                quotes = []
                break

            yes_quote = next(
                (quote for quote in market_quotes if quote.outcome.strip().lower() == "yes"),
                market_quotes[0],
            )
            quotes.append(yes_quote)
            market_titles.append(market.question)

        if len(quotes) < 2:
            continue

        gross_cost = sum((quote.ask_price for quote in quotes), start=Decimal("0"))
        gross_edge = ONE - gross_cost
        adjusted_cost = _adjusted_cost(gross_cost, slippage_bps, fee_bps)
        net_edge = ONE - adjusted_cost
        if net_edge < min_edge:
            continue

        max_size = min((quote.ask_size for quote in quotes), default=Decimal("0"))
        if max_size <= 0:
            continue

        opportunities.append(
            Opportunity(
                kind="neg_risk_bundle",
                event_title=event.title,
                market_title=" | ".join(market_titles),
                legs=quotes,
                gross_cost=gross_cost,
                gross_payout=ONE,
                gross_edge=gross_edge,
                adjusted_cost=adjusted_cost,
                net_edge=net_edge,
                max_size=max_size,
            )
        )

    return opportunities


def scan_opportunities(
    min_edge: Decimal = Decimal("0.01"),
    max_events: int = 100,
    slippage_bps: Decimal = Decimal("0"),
    fee_bps: Decimal = Decimal("0"),
    include_fee_enabled: bool = False,
    workers: int = 16,
) -> list[Opportunity]:
    events = fetch_active_events(max_events=max_events)
    quote_map = _collect_quotes(events, include_fee_enabled, workers)
    opportunities = []
    opportunities.extend(
        find_binary_market_arbs(
            events,
            quote_map,
            min_edge,
            slippage_bps,
            fee_bps,
            include_fee_enabled,
        )
    )
    opportunities.extend(
        find_neg_risk_bundle_arbs(
            events,
            quote_map,
            min_edge,
            slippage_bps,
            fee_bps,
            include_fee_enabled,
        )
    )
    opportunities.sort(key=lambda opportunity: opportunity.net_edge, reverse=True)
    return opportunities
