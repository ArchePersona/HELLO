"""Maturity pressure evaluation for ELLE."""

from __future__ import annotations

from .models import GossipState, WorkParcel

# Pressure weights per GRAY gossip state.
PRESSURE_WEIGHTS: dict[GossipState, float] = {
    GossipState.WHITE: 0.10,
    GossipState.GRAY: 0.40,
    GossipState.BLACK: 1.00,
    GossipState.DEAD: 0.00,
}

PROMOTION_THRESHOLD = 0.75


def evaluate_pressure(parcel: WorkParcel) -> float:
    """Maturity pressure = weight(gossip state) x event count factor."""
    weight = PRESSURE_WEIGHTS.get(parcel.gossip, 0.0)
    events = max(len(parcel.notes), 0)
    factor = 1.0 + 0.1 * events  # every corroborating note adds pressure
    parcel.pressure = min(weight * factor, 1.0)
    return parcel.pressure


def ready_for_promotion(parcel: WorkParcel) -> bool:
    return (
        parcel.stage.value == "settled"
        and parcel.gossip == GossipState.BLACK
        and parcel.pressure >= PROMOTION_THRESHOLD
    )
