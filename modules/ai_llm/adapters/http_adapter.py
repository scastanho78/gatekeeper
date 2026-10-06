"""Adapter genérico para agentes expostos via HTTP (ex: endpoint REST
interno do seu agente, antes de publicá-lo).

Ajuste `request_builder`/`response_parser` para o formato real da sua
API — isto é um esqueleto, não vai funcionar "out of the box" contra um
endpoint que o runner nunca viu.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from modules.ai_llm.adapters.base import AgentResponse


@dataclass
class HttpAdapter:
    endpoint: str
    headers: dict[str, str]
    # Monta o corpo da requisição a partir do prompt + histórico.
    request_builder: Callable[[str, list[str] | None], dict[str, Any]]
    # Extrai (texto, tokens_usados, tool_calls) da resposta JSON crua.
    response_parser: Callable[[dict[str, Any]], tuple[str, int | None, list[str]]]
    timeout_seconds: float = 30.0

    def send(self, prompt: str, *, history: list[str] | None = None) -> AgentResponse:
        body = self.request_builder(prompt, history)
        start = time.monotonic()
        resp = requests.post(
            self.endpoint, json=body, headers=self.headers, timeout=self.timeout_seconds
        )
        latency = time.monotonic() - start
        resp.raise_for_status()
        data = resp.json()
        text, tokens, tool_calls = self.response_parser(data)
        return AgentResponse(
            text=text,
            latency_seconds=latency,
            tokens_used=tokens,
            tool_calls=tool_calls,
            raw=data,
        )


def example_openai_style_adapter(endpoint: str, api_key: str) -> HttpAdapter:
    """Exemplo de fábrica para um agente que expõe uma API no estilo
    OpenAI chat completions. Adapte conforme o formato real.
    """

    def build(prompt: str, history: list[str] | None) -> dict[str, Any]:
        messages = [{"role": "user", "content": h} for h in (history or [])]
        messages.append({"role": "user", "content": prompt})
        return {"messages": messages}

    def parse(data: dict[str, Any]) -> tuple[str, int | None, list[str]]:
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens")
        tool_calls = [
            tc.get("function", {}).get("name", "")
            for tc in data.get("choices", [{}])[0].get("message", {}).get("tool_calls", []) or []
        ]
        return text, tokens, tool_calls

    return HttpAdapter(
        endpoint=endpoint,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        request_builder=build,
        response_parser=parse,
    )


def simple_json_adapter(endpoint: str, api_key: str = "", text_field: str = "response") -> HttpAdapter:
    """Para agentes caseiros que recebem {"message": "..."} e devolvem
    algo como {"response": "..."} (ou outro nome de campo, configurável
    em `text_field`). Pensado para ser usado pela tela (ui/app.py) sem
    o usuário precisar escrever código.
    """

    def build(prompt: str, history: list[str] | None) -> dict[str, Any]:
        return {"message": prompt, "history": history or []}

    def parse(data: dict[str, Any]) -> tuple[str, int | None, list[str]]:
        text = data.get(text_field, "")
        tokens = data.get("tokens_used") or data.get("usage", {}).get("total_tokens")
        tool_calls = data.get("tool_calls", []) or []
        return str(text), tokens, [str(t) for t in tool_calls]

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return HttpAdapter(
        endpoint=endpoint,
        headers=headers,
        request_builder=build,
        response_parser=parse,
    )
