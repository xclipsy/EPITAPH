"""Política de disparo: cuándo ejecutar el pipeline.

Separación estricta:
  - el watcher registra eventos,
  - el trigger decide si toca ejecutar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

MAX_INTERVAL_MINUTES = 1440
MIN_INTERVAL_MINUTES = 1


class TriggerMode(StrEnum):
    ON_AUTOSAVE = "on_autosave"
    ON_SAVE = "on_save"
    INTERVAL = "interval"
    IDLE = "idle"
    MANUAL = "manual"


@dataclass(frozen=True)
class TriggerSpec:
    mode: TriggerMode
    minutes: int | None = None

    @property
    def label(self) -> str:
        if self.mode is TriggerMode.INTERVAL:
            return f"cada {self.minutes} min"
        if self.mode is TriggerMode.IDLE:
            return f"inactivo {self.minutes} min"
        if self.mode is TriggerMode.ON_AUTOSAVE:
            return "por cada autosave"
        if self.mode is TriggerMode.ON_SAVE:
            return "por guardado"
        return "manual"

    def as_string(self) -> str:
        if self.mode in (TriggerMode.INTERVAL, TriggerMode.IDLE):
            return f"{self.mode.value}:{self.minutes}"
        return self.mode.value


def parse_spec(raw: str) -> TriggerSpec:
    """Convierte 'interval:5', 'idle:10', 'on_save', 'on_autosave', 'manual' en TriggerSpec."""
    value = (raw or "").strip().lower()
    if value in ("on_autosave", "autosave", "auto_save", "guardado_automatico", "auto"):
        return TriggerSpec(TriggerMode.ON_AUTOSAVE)
    if value in ("on_save", "save", "guardado", "guardado_manual"):
        return TriggerSpec(TriggerMode.ON_SAVE)
    if value in ("manual", "off", "nunca"):
        return TriggerSpec(TriggerMode.MANUAL)

    shorthand = re.fullmatch(
        r"(?:cada\s+)?(\d+)\s*(?:m|min|mins|minuto|minutos)?", value
    )
    if shorthand:
        minutes = int(shorthand.group(1))
        if not MIN_INTERVAL_MINUTES <= minutes <= MAX_INTERVAL_MINUTES:
            raise ValueError(
                f"la cadencia debe estar entre {MIN_INTERVAL_MINUTES} y "
                f"{MAX_INTERVAL_MINUTES} minutos"
            )
        return TriggerSpec(TriggerMode.INTERVAL, minutes)

    for mode in (TriggerMode.INTERVAL, TriggerMode.IDLE):
        prefix = f"{mode.value}:"
        if value.startswith(prefix):
            number = value[len(prefix) :].strip()
            try:
                minutes = int(number)
            except ValueError as exc:
                raise ValueError(f"cadencia inválida: {raw!r}") from exc
            if not MIN_INTERVAL_MINUTES <= minutes <= MAX_INTERVAL_MINUTES:
                raise ValueError(
                    f"la cadencia debe estar entre {MIN_INTERVAL_MINUTES} y "
                    f"{MAX_INTERVAL_MINUTES} minutos"
                )
            return TriggerSpec(mode, minutes)

    raise ValueError(
        f"cadencia desconocida: {raw!r} (usa on_autosave, on_save, manual, interval:N o idle:N)"
    )


class Trigger:
    """Decide si un run debe ejecutarse.

    Reglas:
      - nunca con el worker ocupado,
      - nunca en pausa,
      - nunca sin cambios pendientes (gate semántico externo),
      - respeta cooldown y ventana de debounce,
      - on_autosave se comporta con debounce rápido y cooldown acotado,
      - on_save se comporta como intervalo ~0 con cooldown.
    """

    def __init__(
        self,
        spec: TriggerSpec,
        debounce_seconds: float = 4.0,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.spec = spec
        self.debounce_seconds = max(0.0, debounce_seconds)
        self.cooldown_seconds = max(0.0, cooldown_seconds)

    def next_due(self, last_event: float | None, last_run: float | None, now: float) -> float | None:
        """Timestamp en el que tocaría ejecutar, o None si no aplica."""
        if self.spec.mode is TriggerMode.MANUAL:
            return None
        if last_event is None:
            return None

        if self.spec.mode is TriggerMode.ON_AUTOSAVE:
            debounce = min(self.debounce_seconds, 2.0)
            base = last_event + debounce
            if last_run is not None:
                base = max(base, last_run + min(self.cooldown_seconds, 10.0))
            return base

        base = last_event + self.debounce_seconds
        if last_run is not None:
            base = max(base, last_run + self.cooldown_seconds)

        if self.spec.mode is TriggerMode.INTERVAL:
            assert self.spec.minutes is not None
            interval = self.spec.minutes * 60.0
            if last_run is None:
                return base
            return max(base, last_run + interval)

        if self.spec.mode is TriggerMode.IDLE:
            assert self.spec.minutes is not None
            return max(base, last_event + self.spec.minutes * 60.0)

        # on_save
        return base

    def should_run(
        self,
        *,
        now: float,
        last_event: float | None,
        last_run: float | None,
        pending: bool,
        busy: bool = False,
        paused: bool = False,
    ) -> bool:
        if paused or busy or not pending:
            return False
        due = self.next_due(last_event, last_run, now)
        return due is not None and now >= due
