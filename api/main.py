"""API HTTP para o GateKeeper — expõe a lógica Python (guardrails, scope,
runner do GateKeeper AI, relatório) pra qualquer frontend consumir,
incluindo um gerado no Lovable.

Isto NÃO reimplementa nada da lógica de autorização — só expõe o que já
existe em core/ e modules/. O objetivo explícito é que o frontend NUNCA
precise decidir sozinho se uma execução é permitida; ele só chama
/agents/{nome}/run e recebe 200 (rodou) ou 403 (bloqueado + motivo).

Rodar localmente:
    pip install -r api/requirements.txt
    uvicorn api.main:app --reload --port 8000

Documentação interativa gerada automaticamente em /docs.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.audit import log_authorization, log_run_completed, log_run_failed, read_recent
from core.guardrails import authorize
from core.scope import Scope
from modules.ai_llm.runner import load_adapter, load_probes, execute
from modules.reporting.generate import build_markdown_report

app = FastAPI(
    title="GateKeeper API",
    description="API da plataforma GateKeeper — hoje só o agente GateKeeper AI é funcional.",
    version="0.1.0",
)

# CORS aberto por padrão pra facilitar o preview do Lovable durante o
# desenvolvimento. ANTES de ir pra produção, restrinja allow_origins ao
# domínio real do frontend — ver api/README.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _scope() -> Scope:
    return Scope.load_or_blank()


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------

class AuthorizationIn(BaseModel):
    approved_by: str
    roe_document: str = ""
    valid_from: dt.date
    valid_until: dt.date


class ActiveWindowIn(BaseModel):
    days: list[str]
    start_time: str  # "HH:MM"
    end_time: str
    timezone: str = "America/Sao_Paulo"


class AgentIn(BaseModel):
    name: str
    environment: str
    api_format: str  # "simple" | "openai"
    endpoint: str
    api_key: str = ""
    text_field: str = "response"


class RunRequest(BaseModel):
    confirm: bool = True


# --------------------------------------------------------------------------
# Status / guardrail
# --------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    scope = _scope()
    scope_file_exists = (ROOT / "config" / "scope.yaml").exists()
    try:
        authz_ok = scope.authorization_valid()
    except Exception:
        authz_ok = False
    return {
        "scope_file_exists": scope_file_exists,
        "authorization_valid": authz_ok,
        "active_window_open_now": scope.active_window.is_open(),
        "agents_registered": len(scope.targets_for("ai_llm")),
    }


@app.get("/api/roadmap")
def get_roadmap():
    """Lista estática dos 5 agentes e seu status — usada pela tela 'Início'."""
    return [
        {"agent": "GateKeeper AI", "icon": "🤖", "description": "Agentes de IA / LLM (OWASP Top 10 for LLM)", "status": "functional"},
        {"agent": "GateKeeper API", "icon": "🌐", "description": "Web / APIs (OWASP Top 10, API Security Top 10)", "status": "planned", "phase": 2},
        {"agent": "GateKeeper Cloud", "icon": "☁️", "description": "Postura de configuração AWS/Azure/GCP", "status": "planned", "phase": 3},
        {"agent": "GateKeeper Network", "icon": "🖧", "description": "Rede interna / Active Directory", "status": "planned", "phase": 4},
        {"agent": "GateKeeper Mobile", "icon": "📱", "description": "Apps mobile (OWASP MASVS/MASTG)", "status": "planned", "phase": 5},
    ]


# --------------------------------------------------------------------------
# Autorização (ROE) e janela de teste
# --------------------------------------------------------------------------

@app.get("/api/authorization")
def get_authorization():
    scope = _scope()
    return scope.raw.get("authorization", {})


@app.put("/api/authorization")
def put_authorization(body: AuthorizationIn):
    scope = _scope()
    scope.raw["authorization"] = {
        "roe_document": body.roe_document,
        "approved_by": body.approved_by,
        "valid_from": body.valid_from.isoformat(),
        "valid_until": body.valid_until.isoformat(),
    }
    scope.save()
    return scope.raw["authorization"]


@app.get("/api/active-window")
def get_active_window():
    scope = _scope()
    return scope.raw.get("active_test_window", {})


@app.put("/api/active-window")
def put_active_window(body: ActiveWindowIn):
    scope = _scope()
    scope.raw["active_test_window"] = body.model_dump()
    scope.save()
    return scope.raw["active_test_window"]


# --------------------------------------------------------------------------
# Agentes (GateKeeper AI)
# --------------------------------------------------------------------------

@app.get("/api/agents")
def list_agents():
    scope = _scope()
    out = []
    for t in scope.targets_for("ai_llm"):
        out.append(
            {
                "name": t.get("name"),
                "environment": t.get("environment"),
                "endpoint": t.get("adapter", {}).get("kwargs", {}).get("endpoint", ""),
                "api_format": "simple" if "simple_json_adapter" in t.get("adapter", {}).get("path", "") else "openai",
            }
        )
    return out


@app.post("/api/agents")
def upsert_agent(body: AgentIn):
    scope = _scope()
    if body.api_format == "simple":
        adapter_cfg = {
            "path": "modules.ai_llm.adapters.http_adapter:simple_json_adapter",
            "kwargs": {"endpoint": body.endpoint, "api_key": body.api_key, "text_field": body.text_field},
        }
    else:
        adapter_cfg = {
            "path": "modules.ai_llm.adapters.http_adapter:example_openai_style_adapter",
            "kwargs": {"endpoint": body.endpoint, "api_key": body.api_key},
        }
    scope.upsert_target(
        "ai_llm", {"name": body.name, "environment": body.environment, "adapter": adapter_cfg, "allow_active": False}
    )
    scope.save()
    return {"ok": True}


@app.delete("/api/agents/{name}")
def delete_agent(name: str):
    scope = _scope()
    scope.remove_target("ai_llm", name)
    scope.save()
    return {"ok": True}


# --------------------------------------------------------------------------
# Probes (consulta, sem tocar no agente)
# --------------------------------------------------------------------------

@app.get("/api/probes")
def list_probes():
    probes = load_probes()
    out = []
    for p in probes:
        out.append(
            {
                "id": p["id"],
                "category": p["category"],
                "source_file": p["_source_file"],
                "prompt": p.get("prompt") or " -> ".join(p.get("multi_turn", [])),
                "note": p.get("note"),
            }
        )
    return out


# --------------------------------------------------------------------------
# Executar teste — é aqui que o guardrail de verdade entra
# --------------------------------------------------------------------------

@app.post("/api/agents/{name}/run")
def run_agent_test(name: str, body: RunRequest):
    scope = _scope()
    targets = {t["name"]: t for t in scope.targets_for("ai_llm")}
    if name not in targets:
        raise HTTPException(status_code=404, detail=f"Agente '{name}' não cadastrado.")

    result = authorize(scope, module="ai_llm", target_identifier=name, mode="passive", confirm=body.confirm)
    log_authorization(result, "ai_llm", name)
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason)

    target_cfg = targets[name]
    probes = load_probes()
    adapter = load_adapter(target_cfg["adapter"]["path"], target_cfg["adapter"].get("kwargs", {}))

    try:
        results, out_path = execute(adapter, probes, name)
    except Exception as exc:  # noqa: BLE001
        log_run_failed("ai_llm", name, str(exc))
        raise HTTPException(status_code=502, detail=f"Erro ao chamar o agente: {exc}") from exc

    flagged = [r for r in results if r["flagged"]]
    log_run_completed("ai_llm", name, len(results), len(flagged))

    report_md = build_markdown_report(name, target_cfg.get("environment", ""), results)

    return {
        "target": name,
        "total": len(results),
        "flagged": len(flagged),
        "results": results,
        "report_markdown": report_md,
        "raw_report_path": str(out_path),
    }


# --------------------------------------------------------------------------
# Checklist manual e auditoria
# --------------------------------------------------------------------------

@app.get("/api/checklist")
def get_checklist():
    path = ROOT / "docs" / "CHECKLIST_LLM_MANUAL.md"
    return {"markdown": path.read_text(encoding="utf-8")}


@app.get("/api/audit")
def get_audit(limit: int = 50):
    return read_recent(limit=limit)
