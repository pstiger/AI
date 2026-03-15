from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True)
class TokenQuote:
    token_id: str
    outcome: str
    ask_price: Decimal
    ask_size: Decimal


@dataclass(slots=True)
class Market:
    id: str
    question: str
    slug: str
    event_id: str
    active: bool
    closed: bool
    archived: bool
    fees_enabled: bool
    tokens: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class Event:
    id: str
    title: str
    slug: str
    active: bool
    closed: bool
    archived: bool
    neg_risk: bool
    markets: list[Market] = field(default_factory=list)


@dataclass(slots=True)
class Opportunity:
    kind: str
    event_title: str
    market_title: str
    legs: list[TokenQuote]
    gross_cost: Decimal
    gross_payout: Decimal
    gross_edge: Decimal
    adjusted_cost: Decimal
    net_edge: Decimal
    max_size: Decimal
