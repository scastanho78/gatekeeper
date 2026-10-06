"""Carrega e valida config/scope.yaml — fonte única de verdade sobre o que
pode ser testado, quando, e em que modo (passivo vs. ativo).

Nenhum módulo deve tocar em um alvo sem passar por aqui primeiro.
"""
from __future__ import annotations

import datetime as dt
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

DEFAULT_SCOPE_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "scope.yaml"


class ScopeError(Exception):
    """Erro de configuração ou violação de escopo."""


@dataclass
class ActiveWindow:
    days: list[str]
    start_time: str
    end_time: str
    timezone: str

    def is_open(self, now: dt.datetime | None = None) -> bool:
        # Checagem simples por dia-da-semana/horário local. Não depende de
        # libs externas de timezone para manter o core sem dependências
        # pesadas; se a empresa precisar de precisão de fuso, trocar por
        # zoneinfo mais adiante.
        now = now or dt.datetime.now()
        weekday = now.strftime("%a").lower()[:3]
        if weekday not in [d.lower()[:3] for d in self.days]:
            return False
        current = now.strftime("%H:%M")
        return self.start_time <= current <= self.end_time


@dataclass
class Scope:
    raw: dict[str, Any]
    active_window: ActiveWindow
    excluded: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: pathlib.Path | None = None) -> "Scope":
        path = path or DEFAULT_SCOPE_PATH
        if not path.exists():
            raise ScopeError(
                f"Arquivo de escopo não encontrado em {path}. "
                "Copie config/scope.yaml.example para config/scope.yaml e "
                "preencha com os alvos autorizados antes de rodar qualquer módulo."
            )
        data = yaml.safe_load(path.read_text()) or {}
        window_cfg = data.get("active_test_window") or {}
        window = ActiveWindow(
            days=window_cfg.get("days", []),
            start_time=window_cfg.get("start_time", "00:00"),
            end_time=window_cfg.get("end_time", "00:00"),
            timezone=window_cfg.get("timezone", "UTC"),
        )
        return cls(raw=data, active_window=window, excluded=data.get("excluded", []))

    def targets_for(self, module: str) -> list[dict[str, Any]]:
        return self.raw.get("targets", {}).get(module, []) or []

    def is_excluded(self, identifier: str) -> bool:
        # Checagem literal/substring simples. Para CIDR real, trocar por
        # ipaddress.ip_network quando o módulo network for implementado.
        return any(excl.strip("*") in identifier for excl in self.excluded)

    def authorization_valid(self, now: dt.datetime | None = None) -> bool:
        auth = self.raw.get("authorization", {})
        now = now or dt.datetime.now()
        try:
            valid_from = dt.datetime.fromisoformat(auth["valid_from"])
            valid_until = dt.datetime.fromisoformat(auth["valid_until"])
        except (KeyError, ValueError) as exc:
            raise ScopeError(
                "authorization.valid_from / valid_until ausentes ou com "
                "formato inválido em scope.yaml (use YYYY-MM-DD)."
            ) from exc
        return valid_from.date() <= now.date() <= valid_until.date()
