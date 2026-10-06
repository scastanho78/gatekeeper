"""Trilha de auditoria dos guardrails: registra quem tentou rodar o quê,
quando, e se foi liberado ou bloqueado — e por qual motivo.

Sem isso, "ter guardrail" é só confiar que o código funciona. Com isso,
dá pra provar depois (pra compliance, auditoria externa, ou só pra você
mesmo) que nenhuma execução passou sem checagem.

Grava em logs/guardrail_audit.log, uma linha JSON por evento. O arquivo
fica fora do git (pode conter nomes de agentes/endpoints internos).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any

AUDIT_LOG_PATH = pathlib.Path(__file__).resolve().parent.parent / "logs" / "guardrail_audit.log"


def log_event(event_type: str, **fields: Any) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        **fields,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_authorization(result, module: str, target_identifier: str) -> None:
    """Registra o resultado de um authorize() no momento em que ele de
    fato gate-ia uma execução (não em toda checagem de status da tela,
    senão o log vira ruído a cada rerender).
    """
    log_event(
        "authorization_check",
        module=module,
        target=target_identifier,
        mode=result.mode,
        allowed=result.allowed,
        reason=result.reason,
    )


def log_run_completed(module: str, target_identifier: str, total: int, flagged: int) -> None:
    log_event(
        "run_completed",
        module=module,
        target=target_identifier,
        total_probes=total,
        flagged=flagged,
    )


def log_run_failed(module: str, target_identifier: str, error: str) -> None:
    log_event("run_failed", module=module, target=target_identifier, error=error)


def read_recent(limit: int = 50) -> list[dict]:
    """Lê as últimas `limit` entradas do log, mais recente primeiro.
    Usado pela aba de Configuração para mostrar a trilha na tela.
    """
    if not AUDIT_LOG_PATH.exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    records = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))
