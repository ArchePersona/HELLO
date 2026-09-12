"""ELLE engine orchestration: ingestion -> lifecycle -> promotion."""

from __future__ import annotations

import uuid
from typing import Iterable

from .models import (
    Event,
    GossipState,
    ParcelStage,
    Rule,
    WorkParcel,
    find_parcel,
)
from .pressure import evaluate_pressure, ready_for_promotion


class ELLEEngine:
    """Orchestrates the external learning loop."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.parcels: list[WorkParcel] = []
        self.rules: list[Rule] = []
        self._promoted: set[str] = set()

    # --- event ingestion -------------------------------------------------

    def ingest(self, source: str, kind: str,
               payload: dict | None = None) -> Event:
        event = Event(source=source, kind=kind, payload=dict(payload or {}))
        self.events.append(event)
        return event

    # --- work parcel lifecycle -------------------------------------------

    def open_parcel(self, parcel_id: str | None = None,
                    ancestry: Iterable[str] = ()) -> WorkParcel:
        parcel = WorkParcel(
            parcel_id=parcel_id or f"parcel-{uuid.uuid4().hex[:10]}",
            ancestry=list(ancestry),
        )
        self.parcels.append(parcel)
        return parcel

    def activate(self, parcel_id: str) -> WorkParcel:
        parcel = self._require(parcel_id)
        parcel.stage = ParcelStage.ACTIVE
        parcel.touch("activated")
        return parcel

    def settle(self, parcel_id: str, *,
               verified: bool = True) -> WorkParcel:
        parcel = self._require(parcel_id)
        parcel.stage = ParcelStage.SETTLED
        # GRAY gossip state management: settlement verifies or kills.
        parcel.gossip = GossipState.BLACK if verified else GossipState.DEAD
        parcel.touch(f"settled verified={verified}")
        evaluate_pressure(parcel)
        return parcel

    def propagate_gossip(self, parcel_id: str) -> WorkParcel:
        """Move a WHITE parcel into GRAY (propagating, unverified)."""
        parcel = self._require(parcel_id)
        if parcel.gossip == GossipState.WHITE:
            parcel.gossip = GossipState.GRAY
        parcel.touch("gossip propagated")
        evaluate_pressure(parcel)
        return parcel

    # --- rule promotion ----------------------------------------------------

    def promote_ready(self) -> list[Rule]:
        promoted: list[Rule] = []
        for parcel in self.parcels:
            if parcel.parcel_id in self._promoted:
                continue  # a parcel promotes at most once
            if parcel.gossip == GossipState.BLACK and                     ready_for_promotion(parcel):
                rule = Rule(
                    rule_id=f"rule-{uuid.uuid4().hex[:8]}",
                    statement=f"derived from {parcel.parcel_id}",
                    maturity=parcel.pressure,
                    ancestry=self.ancestry_of(parcel),
                )
                self.rules.append(rule)
                self._promoted.add(parcel.parcel_id)
                promoted.append(rule)
        return promoted

    # --- ancestry tracking ---------------------------------------------------

    def ancestry_of(self, parcel: WorkParcel) -> list[str]:
        return list(parcel.ancestry)

    def lineage(self, parcel_id: str) -> list[str]:
        chain: list[str] = []
        current = find_parcel(self.parcels, parcel_id)
        while current is not None:
            chain.append(current.parcel_id)
            parents = current.ancestry
            current = find_parcel(self.parcels, parents[0]) if parents else None
        return list(reversed(chain))

    # --- internal ------------------------------------------------------------

    def _require(self, parcel_id: str) -> WorkParcel:
        parcel = find_parcel(self.parcels, parcel_id)
        if parcel is None:
            raise KeyError(f"unknown parcel: {parcel_id}")
        return parcel
