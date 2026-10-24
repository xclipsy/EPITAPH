from __future__ import annotations

import pytest

from epitaph.scheduler.trigger import Trigger, TriggerMode, parse_spec


def test_parse_on_save() -> None:
    spec = parse_spec("on_save")
    assert spec.mode is TriggerMode.ON_SAVE
    assert spec.as_string() == "on_save"
    assert spec.label == "por guardado"


def test_parse_on_autosave() -> None:
    for alias in ("on_autosave", "autosave", "auto_save", "guardado_automatico"):
        spec = parse_spec(alias)
        assert spec.mode is TriggerMode.ON_AUTOSAVE
        assert spec.as_string() == "on_autosave"
        assert spec.label == "por cada autosave"


def test_on_autosave_respects_fast_debounce() -> None:
    trigger = Trigger(parse_spec("on_autosave"), debounce_seconds=4, cooldown_seconds=30)
    # Debounce is capped to 2s for autosave
    assert trigger.next_due(last_event=0.0, last_run=None, now=0.0) == 2.0
    assert trigger.next_due(last_event=100.0, last_run=95.0, now=100.0) == 105.0


def test_parse_manual_and_aliases() -> None:
    assert parse_spec("manual").mode is TriggerMode.MANUAL
    assert parse_spec("off").mode is TriggerMode.MANUAL
    assert parse_spec("nunca").mode is TriggerMode.MANUAL


def test_parse_interval_and_idle() -> None:
    interval = parse_spec("interval:5")
    assert interval.mode is TriggerMode.INTERVAL
    assert interval.minutes == 5
    assert interval.as_string() == "interval:5"
    assert interval.label == "cada 5 min"

    idle = parse_spec("idle:10")
    assert idle.mode is TriggerMode.IDLE
    assert idle.label == "inactivo 10 min"


def test_parse_user_friendly_numbers() -> None:
    for raw in ("10", "10m", "10 min", "cada 10 minutos"):
        spec = parse_spec(raw)
        assert spec.mode is TriggerMode.INTERVAL
        assert spec.minutes == 10
        assert spec.as_string() == "interval:10"


def test_parse_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        parse_spec("interval:0")
    with pytest.raises(ValueError):
        parse_spec("interval:1441")


def test_parse_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        parse_spec("cada rato")


def test_on_save_respects_debounce_and_cooldown() -> None:
    trigger = Trigger(parse_spec("on_save"), debounce_seconds=4, cooldown_seconds=30)
    assert trigger.next_due(last_event=0.0, last_run=None, now=0.0) == 4.0
    assert trigger.next_due(last_event=100.0, last_run=90.0, now=100.0) == 120.0
    assert trigger.should_run(
        now=3.9, last_event=0.0, last_run=None, pending=True
    ) is False
    assert trigger.should_run(
        now=4.0, last_event=0.0, last_run=None, pending=True
    ) is True


def test_interval_waits_for_next_window() -> None:
    trigger = Trigger(parse_spec("interval:5"), debounce_seconds=4, cooldown_seconds=30)
    due = trigger.next_due(last_event=100.0, last_run=100.0, now=100.0)
    assert due == 400.0
    assert trigger.should_run(now=399.0, last_event=100.0, last_run=100.0, pending=True) is False
    assert trigger.should_run(now=400.0, last_event=100.0, last_run=100.0, pending=True) is True


def test_idle_waits_for_inactivity() -> None:
    trigger = Trigger(parse_spec("idle:10"), debounce_seconds=4, cooldown_seconds=30)
    assert trigger.next_due(last_event=0.0, last_run=0.0, now=0.0) == 600.0


def test_manual_never_runs() -> None:
    trigger = Trigger(parse_spec("manual"))
    assert trigger.next_due(last_event=0.0, last_run=None, now=0.0) is None
    assert trigger.should_run(now=10_000.0, last_event=0.0, last_run=None, pending=True) is False


def test_gates_block_runs() -> None:
    trigger = Trigger(parse_spec("on_save"), debounce_seconds=0, cooldown_seconds=0)
    assert trigger.should_run(now=10.0, last_event=0.0, last_run=None, pending=False) is False
    assert (
        trigger.should_run(now=10.0, last_event=0.0, last_run=None, pending=True, busy=True)
        is False
    )
    assert (
        trigger.should_run(now=10.0, last_event=0.0, last_run=None, pending=True, paused=True)
        is False
    )
