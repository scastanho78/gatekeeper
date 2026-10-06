"""Runner do módulo ai_llm: carrega probes, aplica guardrails, chama o
adapter do agente alvo, avalia heuristicamente e grava relatório JSON.

Uso:
    python -m modules.ai_llm.runner --target meu-agente-v1 --dry-run
    python -m modules.ai_llm.runner --target meu-agente-v1
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import pathlib
import sys

import yaml

from core.guardrails import GuardrailViolation, authorize, require
from core.scope import Scope, ScopeError
from modules.ai_llm.adapters.base import AgentAdapter

PROBES_DIR = pathlib.Path(__file__).parent / "probes"
REPORTS_DIR = pathlib.Path(__file__).parent.parent.parent / "reports" / "ai_llm"


def load_probes() -> list[dict]:
    probes: list[dict] = []
    for probe_file in sorted(PROBES_DIR.glob("*.yaml")):
        content = yaml.safe_load(probe_file.read_text()) or []
        for probe in content:
            probe["_source_file"] = probe_file.name
            probes.append(probe)
    return probes


def evaluate(probe: dict, response_text: str, latency: float, tokens: int | None, tool_calls: list[str]) -> dict:
    flagged = False
    reasons = []

    for needle in probe.get("expect_contains_any", []):
        if needle.lower() in response_text.lower():
            flagged = True
            reasons.append(f"resposta contém trecho esperado de falha: '{needle}'")

    unconfirmed = probe.get("expect_tool_calls_without_confirmation", [])
    if unconfirmed and any(tc in unconfirmed for tc in tool_calls):
        flagged = True
        hit = [tc for tc in tool_calls if tc in unconfirmed]
        reasons.append(f"agente chamou ferramenta sensível sem confirmação aparente: {hit}")

    lat_limit = probe.get("flag_if_latency_above_seconds")
    if lat_limit is not None and latency > lat_limit:
        flagged = True
        reasons.append(f"latência {latency:.1f}s acima do limite {lat_limit}s")

    tok_limit = probe.get("flag_if_tokens_above")
    if tok_limit is not None and tokens is not None and tokens > tok_limit:
        flagged = True
        reasons.append(f"tokens usados {tokens} acima do limite {tok_limit}")

    return {"flagged": flagged, "reasons": reasons}


def load_adapter(adapter_path: str, adapter_kwargs: dict) -> AgentAdapter:
    """adapter_path no formato 'modules.ai_llm.adapters.http_adapter:example_openai_style_adapter'"""
    module_name, _, attr = adapter_path.partition(":")
    module = importlib.import_module(module_name)
    factory_or_class = getattr(module, attr)
    return factory_or_class(**adapter_kwargs)


def execute(adapter: AgentAdapter, probes: list[dict], target_name: str, save_report: bool = True) -> tuple[list[dict], pathlib.Path | None]:
    """Roda todas as `probes` contra `adapter` e retorna (resultados, caminho_do_relatorio).

    Extraído de `run()` para ser reutilizável tanto pela CLI quanto pela
    interface web (ui/app.py) — a lógica de avaliação é a mesma nos dois
    casos, só a origem do adapter/target muda.
    """
    results = []
    for probe in probes:
        if "multi_turn" in probe:
            history: list[str] = []
            response = None
            for turn in probe["multi_turn"][:-1]:
                response = adapter.send(turn, history=history)
                history.append(turn)
            response = adapter.send(probe["multi_turn"][-1], history=history)
        else:
            response = adapter.send(probe["prompt"])

        verdict = evaluate(probe, response.text, response.latency_seconds, response.tokens_used, response.tool_calls)
        results.append(
            {
                "probe_id": probe["id"],
                "category": probe["category"],
                "source_file": probe["_source_file"],
                "prompt": probe.get("prompt") or " -> ".join(probe.get("multi_turn", [])),
                "note": probe.get("note"),
                "response_text": response.text,
                "latency_seconds": response.latency_seconds,
                "tokens_used": response.tokens_used,
                "tool_calls": response.tool_calls,
                **verdict,
            }
        )

    out_path = None
    if save_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = REPORTS_DIR / f"{target_name}-{timestamp}.json"
        out_path.write_text(json.dumps({"target": target_name, "results": results}, indent=2, ensure_ascii=False))

    return results, out_path


def run(target_name: str, dry_run: bool, confirm: bool, scope_path: pathlib.Path | None = None) -> int:
    try:
        scope = Scope.load(scope_path)
    except ScopeError as exc:
        print(f"[ERRO DE ESCOPO] {exc}", file=sys.stderr)
        return 2

    result = authorize(scope, module="ai_llm", target_identifier=target_name, mode="passive", confirm=confirm)
    try:
        require(result)
    except GuardrailViolation as exc:
        print(f"[BLOQUEADO PELO GUARDRAIL] {exc}", file=sys.stderr)
        return 3

    target_cfg = next(t for t in scope.targets_for("ai_llm") if t.get("name") == target_name)
    probes = load_probes()
    print(f"{len(probes)} probes carregadas de {PROBES_DIR}")

    if dry_run:
        for p in probes:
            print(f"  [DRY-RUN] {p['id']} ({p['category']}) — {p['_source_file']}")
        print("Dry-run concluído. Nenhuma chamada foi feita ao agente.")
        return 0

    adapter_cfg = target_cfg.get("adapter")
    if not adapter_cfg:
        print(
            f"[ERRO] target '{target_name}' não tem bloco 'adapter' em scope.yaml. "
            "Veja modules/ai_llm/adapters/http_adapter.py para o formato esperado.",
            file=sys.stderr,
        )
        return 4

    adapter = load_adapter(adapter_cfg["path"], adapter_cfg.get("kwargs", {}))
    results, out_path = execute(adapter, probes, target_name)
    for r in results:
        print(f"  [{'FLAGGED' if r['flagged'] else 'ok'}] {r['probe_id']}")

    flagged_count = sum(1 for r in results if r["flagged"])
    print(f"\n{flagged_count}/{len(results)} probes marcadas como flagged.")
    print(f"Relatório salvo em: {out_path}")
    print("Revise manualmente cada 'flagged' antes de decidir sobre publicação do agente.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa um agente de IA contra probes adversariais antes de publicá-lo.")
    parser.add_argument("--target", required=True, help="Nome do target em targets.ai_llm no scope.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Lista as probes sem chamar o agente")
    parser.add_argument("--confirm", action="store_true", help="Confirma execução (exigido para modo ativo; aqui reservado para uso futuro)")
    parser.add_argument("--scope", type=pathlib.Path, default=None, help="Caminho alternativo para scope.yaml")
    args = parser.parse_args()
    sys.exit(run(args.target, args.dry_run, args.confirm, args.scope))


if __name__ == "__main__":
    main()
