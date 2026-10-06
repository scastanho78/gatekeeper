"""Guardrails: ponto único de decisão "pode executar isso ou não".

Todo módulo deve chamar `authorize()` antes de qualquer chamada ativa
contra um alvo. Isto é intencionalmente burocrático — o objetivo é que
seja impossível rodar algo ativo "por engano" fora do escopo autorizado.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from core.scope import Scope, ScopeError


class GuardrailViolation(Exception):
    """Levantado quando uma execução é bloqueada pelos guardrails."""


@dataclass
class AuthorizationResult:
    allowed: bool
    reason: str
    mode: str  # "passive" | "active"


def authorize(
    scope: Scope,
    module: str,
    target_identifier: str,
    mode: str,
    confirm: bool,
    now: dt.datetime | None = None,
) -> AuthorizationResult:
    """Decide se uma ação pode rodar.

    Em ambos os modos: o alvo precisa estar em scope.yaml, não pode estar
    na lista de exclusão, e a autorização (ROE) precisa estar dentro da
    validade.

    - mode="passive": recon/leitura, sem interação com o alvo que gere
      carga ou mude estado (ex: sondar um agente de IA com prompts). Não
      exige --confirm nem janela de horário, mas ainda exige ROE válido.
    - mode="active": qualquer coisa que envie payloads, faça brute force,
      explore, etc. Exige adicionalmente: alvo com allow_active=true,
      dentro da janela de teste, e --confirm explícito.
    """
    if mode not in ("passive", "active"):
        raise ValueError(f"mode inválido: {mode!r}")

    if scope.is_excluded(target_identifier):
        return AuthorizationResult(False, f"'{target_identifier}' está na lista de exclusão.", mode)

    targets = scope.targets_for(module)
    match = next(
        (t for t in targets if _matches(t, target_identifier)),
        None,
    )
    if match is None:
        return AuthorizationResult(
            False,
            f"'{target_identifier}' não está em targets.{module} do scope.yaml.",
            mode,
        )

    # Validade do ROE é checada para QUALQUER modo — inclusive "passive".
    # Antes só era checada no modo "active", o que deixava os módulos
    # passivos (como o ai_llm) rodarem com autorização vencida ou nunca
    # preenchida sem o guardrail bloquear nada. Testar o próprio agente
    # de IA ainda é uma ação que precisa de autorização formal registrada.
    try:
        if not scope.authorization_valid(now):
            return AuthorizationResult(False, "Autorização (ROE) vencida ou não preenchida em scope.yaml.", mode)
    except ScopeError as exc:
        return AuthorizationResult(False, str(exc), mode)

    if mode == "passive":
        return AuthorizationResult(True, "Execução passiva, dentro do escopo e com ROE válido.", mode)

    # mode == "active": checagens extras
    if not match.get("allow_active", False):
        return AuthorizationResult(
            False,
            f"'{target_identifier}' está em escopo, mas allow_active=false.",
            mode,
        )

    if not scope.active_window.is_open(now):
        return AuthorizationResult(
            False,
            "Fora da janela de teste ativo definida em active_test_window.",
            mode,
        )

    if not confirm:
        return AuthorizationResult(
            False,
            "Execução ativa requer --confirm explícito na linha de comando.",
            mode,
        )

    return AuthorizationResult(True, "Execução ativa autorizada.", mode)


def require(result: AuthorizationResult) -> None:
    """Levanta GuardrailViolation se o resultado não autorizou a execução."""
    if not result.allowed:
        raise GuardrailViolation(result.reason)


def _matches(target_cfg: dict, identifier: str) -> bool:
    for key in ("host", "account_id", "name", "id"):
        if target_cfg.get(key) == identifier:
            return True
    return False
