from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Event, Market, TokenQuote

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"


class PolymarketApiError(RuntimeError):
    """Raised when public Polymarket data cannot be fetched."""


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    target = url
    if params:
        target = f"{url}?{urlencode(params)}"
    request = Request(
        target,
        headers={
            "Accept": "application/json",
            "User-Agent": "polymarket-arbitrage-scanner/0.1",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise PolymarketApiError(f"Request failed for {target}: {exc.reason}") from exc


def _parse_jsonish_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [item.strip() for item in text.split(",") if item.strip()]
        return parsed if isinstance(parsed, list) else []
    return []


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _extract_tokens(market_payload: dict[str, Any]) -> list[tuple[str, str]]:
    tokens = market_payload.get("tokens")
    if isinstance(tokens, list) and tokens:
        parsed_tokens: list[tuple[str, str]] = []
        for token in tokens:
            if not isinstance(token, dict):
                continue
            token_id = str(
                token.get("token_id")
                or token.get("tokenId")
                or token.get("clobTokenId")
                or token.get("id")
                or ""
            ).strip()
            outcome = str(token.get("outcome") or token.get("name") or "").strip()
            if token_id:
                parsed_tokens.append((outcome or token_id, token_id))
        if parsed_tokens:
            return parsed_tokens

    outcomes = _parse_jsonish_list(market_payload.get("outcomes"))
    token_ids = _parse_jsonish_list(
        market_payload.get("clobTokenIds") or market_payload.get("clobTokenids")
    )
    if not token_ids:
        return []

    parsed_fallback: list[tuple[str, str]] = []
    for index, token_id in enumerate(token_ids):
        outcome = str(outcomes[index]) if index < len(outcomes) else f"Outcome {index + 1}"
        parsed_fallback.append((outcome, str(token_id)))
    return parsed_fallback


def fetch_active_events(max_events: int = 100) -> list[Event]:
    events: list[Event] = []
    offset = 0
    page_size = min(max_events, 100)

    while len(events) < max_events:
        payload = _get_json(
            f"{GAMMA_BASE_URL}/events",
            params={
                "active": "true",
                "closed": "false",
                "limit": page_size,
                "offset": offset,
            },
        )
        if not isinstance(payload, list) or not payload:
            break

        for raw_event in payload:
            if not isinstance(raw_event, dict):
                continue
            event = Event(
                id=str(raw_event.get("id") or ""),
                title=str(raw_event.get("title") or raw_event.get("slug") or ""),
                slug=str(raw_event.get("slug") or ""),
                active=_to_bool(raw_event.get("active")),
                closed=_to_bool(raw_event.get("closed")),
                archived=_to_bool(raw_event.get("archived")),
                neg_risk=_to_bool(raw_event.get("negRisk")),
            )
            raw_markets = raw_event.get("markets")
            if isinstance(raw_markets, list):
                for raw_market in raw_markets:
                    if not isinstance(raw_market, dict):
                        continue
                    event.markets.append(
                        Market(
                            id=str(raw_market.get("id") or ""),
                            question=str(raw_market.get("question") or raw_market.get("slug") or ""),
                            slug=str(raw_market.get("slug") or ""),
                            event_id=event.id,
                            active=_to_bool(raw_market.get("active")),
                            closed=_to_bool(raw_market.get("closed")),
                            archived=_to_bool(raw_market.get("archived")),
                            fees_enabled=_to_bool(raw_market.get("feesEnabled")),
                            tokens=_extract_tokens(raw_market),
                        )
                    )
            events.append(event)
            if len(events) >= max_events:
                break

        if len(payload) < page_size:
            break
        offset += page_size

    return events


def fetch_best_ask(token_id: str) -> TokenQuote | None:
    payload = _get_json(f"{CLOB_BASE_URL}/book", params={"token_id": token_id})
    asks = payload.get("asks") if isinstance(payload, dict) else None
    if not isinstance(asks, list) or not asks:
        return None

    best_ask = asks[0]
    if not isinstance(best_ask, dict):
        return None

    ask_price = _to_decimal(best_ask.get("price"))
    ask_size = _to_decimal(best_ask.get("size"))
    if ask_price <= 0 or ask_size <= 0:
        return None

    return TokenQuote(token_id=token_id, outcome="", ask_price=ask_price, ask_size=ask_size)
