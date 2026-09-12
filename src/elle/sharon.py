"""SHARON/ERIE exchange interface (integration boundary)."""

from __future__ import annotations

from typing import Any, Protocol

from .models import Rule, WorkParcel


class ExchangeSink(Protocol):
    """Any downstream system ELLE can hand rules/parcels to."""

    def receive(self, envelope: dict[str, Any]) -> str:
        ...


class SharonExchange:
    """Outbound: ELLE -> SHARON."""

    def __init__(self, sink: ExchangeSink) -> None:
        self._sink = sink

    def publish_rule(self, rule: Rule) -> str:
        return self._sink.receive({
            "type": "rule",
            "rule_id": rule.rule_id,
            "statement": rule.statement,
            "maturity": rule.maturity,
            "ancestry": list(rule.ancestry),
        })

    def publish_parcel(self, parcel: WorkParcel) -> str:
        return self._sink.receive({
            "type": "parcel",
            "parcel_id": parcel.parcel_id,
            "stage": parcel.stage.value,
            "gossip": parcel.gossip.value,
        })


class ErieExchange:
    """Inbound: ERIE -> ELLE."""

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []

    def accept(self, envelope: dict[str, Any]) -> str:
        self._queue.append(dict(envelope))
        return "accepted"

    def drain(self) -> list[dict[str, Any]]:
        items, self._queue = self._queue, []
        return items
