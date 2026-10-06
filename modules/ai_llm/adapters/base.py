"""Interface que todo adapter de agente precisa implementar.

Um adapter é a ponte entre o runner (que só sabe falar "probes" e
"resultados") e o agente real da empresa (que pode ser um endpoint HTTP,
uma função Python importada, um processo CLI, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AgentResponse:
    text: str
    latency_seconds: float
    tokens_used: int | None = None
    tool_calls: list[str] = field(default_factory=list)
    raw: dict | None = None


class AgentAdapter(Protocol):
    """Qualquer adapter concreto deve implementar este método."""

    def send(self, prompt: str, *, history: list[str] | None = None) -> AgentResponse:
        """Envia `prompt` ao agente (com `history` de turnos anteriores,
        se o probe for multi-turn) e retorna a resposta padronizada.
        """
        ...
