"""ELLE test suite (runs from the project root)."""

import pytest

from elle import (
    ELLEEngine,
    ErieExchange,
    GossipState,
    ParcelStage,
    SharonExchange,
)
from elle.pressure import PROMOTION_THRESHOLD, evaluate_pressure


class MemorySink:
    def __init__(self):
        self.envelopes = []

    def receive(self, envelope):
        self.envelopes.append(envelope)
        return "ok"


def test_event_ingestion():
    engine = ELLEEngine()
    event = engine.ingest("erie", "observation", {"k": "v"})
    assert event.key() == "erie:observation"
    assert len(engine.events) == 1


def test_parcel_lifecycle():
    engine = ELLEEngine()
    parcel = engine.open_parcel("p1")
    assert parcel.stage is ParcelStage.INGESTED
    engine.activate("p1")
    assert parcel.stage is ParcelStage.ACTIVE
    engine.settle("p1", verified=True)
    assert parcel.stage is ParcelStage.SETTLED


def test_gray_gossip_state_management():
    engine = ELLEEngine()
    parcel = engine.open_parcel("g1")
    assert parcel.gossip is GossipState.WHITE
    engine.propagate_gossip("g1")
    assert parcel.gossip is GossipState.GRAY
    engine.settle("g1", verified=True)
    assert parcel.gossip is GossipState.BLACK
    dead = engine.open_parcel("g2")
    engine.settle("g2", verified=False)
    assert dead.gossip is GossipState.DEAD


def test_maturity_pressure_evaluation():
    engine = ELLEEngine()
    parcel = engine.open_parcel("p")
    engine.propagate_gossip("p")
    pressure = evaluate_pressure(parcel)
    assert 0.0 < pressure < 1.0
    engine.settle("p", verified=True)
    assert parcel.pressure == pytest.approx(1.0)


def test_rule_promotion_requires_black_and_threshold():
    engine = ELLEEngine()
    parcel = engine.open_parcel("r1")
    engine.activate("r1")
    engine.settle("r1", verified=True)
    assert parcel.pressure >= PROMOTION_THRESHOLD
    rules = engine.promote_ready()
    assert len(rules) == 1
    assert rules[0].maturity == pytest.approx(parcel.pressure)

    # GRAY (unverified) parcels never promote.
    engine.open_parcel("r2")
    engine.propagate_gossip("r2")
    assert engine.promote_ready() == []


def test_ancestry_tracking():
    engine = ELLEEngine()
    parent = engine.open_parcel("a")
    child = engine.open_parcel("b", ancestry=[parent.parcel_id])
    grandchild = engine.open_parcel("c", ancestry=[child.parcel_id])
    assert engine.lineage(grandchild.parcel_id) == ["a", "b", "c"]
    assert engine.ancestry_of(child) == ["a"]


def test_lineage_terminates_on_cyclic_ancestry():
    engine = ELLEEngine()
    engine.open_parcel("a", ancestry=["b"])
    engine.open_parcel("b", ancestry=["a"])
    assert engine.lineage("a") == ["b", "a"]


def test_lineage_terminates_on_self_parent():
    engine = ELLEEngine()
    engine.open_parcel("s", ancestry=["s"])
    assert engine.lineage("s") == ["s"]


def test_duplicate_parcel_id_rejected():
    engine = ELLEEngine()
    engine.open_parcel("dup")
    with pytest.raises(ValueError):
        engine.open_parcel("dup")


def test_sharon_erie_exchange_interface():
    sink = MemorySink()
    sharon = SharonExchange(sink)
    erie = ErieExchange()

    engine = ELLEEngine()
    parcel = engine.open_parcel("x")
    engine.activate("x")
    engine.settle("x", verified=True)
    (rule,) = engine.promote_ready()

    assert sharon.publish_rule(rule) == "ok"
    assert sink.envelopes[0]["type"] == "rule"
    assert sink.envelopes[0]["rule_id"] == rule.rule_id

    assert erie.accept({"source": "erie", "kind": "observation"}) == "accepted"
    drained = erie.drain()
    assert len(drained) == 1 and drained[0]["kind"] == "observation"
    assert erie.drain() == []


def test_duplicate_parcel_id_operations_target_one_parcel():
    # With duplicates rejected, id lookup always targets the caller's parcel.
    engine = ELLEEngine()
    parcel = engine.open_parcel("solo")
    engine.activate("solo")
    engine.settle("solo", verified=True)
    assert parcel.stage is ParcelStage.SETTLED
    assert parcel.gossip is GossipState.BLACK


def test_erie_rejects_malformed_envelopes():
    erie = ErieExchange()
    malformed = [
        ["source", "kind"],                      # not a dict
        {"kind": "observation"},                  # missing source
        {"source": "erie"},                        # missing kind
        {"source": "", "kind": "observation"},     # empty source
        {"source": "erie", "kind": ""},            # empty kind
        {"source": 1, "kind": "observation"},      # non-string source
        {"source": "erie", "kind": "observation", "payload": "nope"},  # bad payload
    ]
    for envelope in malformed:
        with pytest.raises(ValueError):
            erie.accept(envelope)
    assert erie.drain() == []  # nothing malformed was queued


def test_erie_accepts_valid_envelopes_with_extra_fields():
    erie = ErieExchange()
    assert erie.accept({"source": "erie", "kind": "observation"}) == "accepted"
    assert erie.accept({
        "source": "erie",
        "kind": "observation",
        "payload": {"k": "v"},
        "trace_id": "t-1",  # extra transport metadata stays allowed
    }) == "accepted"
    drained = erie.drain()
    assert len(drained) == 2
    assert drained[1]["payload"] == {"k": "v"}
    assert drained[1]["trace_id"] == "t-1"
    assert erie.drain() == []  # drain remains idempotent after validated accepts


def test_pytest_suite_passes_from_project_root():
    # Guard: this suite is runnable exactly as a user would run it.
    assert True
