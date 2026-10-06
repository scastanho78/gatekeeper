"""GateKeeper — plataforma de testes de segurança internos.

Tela única com uma aba de Configuração (guardrails: autorização, janela
de teste, agentes cadastrados) e uma aba por agente (um agente por tipo
de teste: IA/LLM, API/web, cloud, rede, mobile). Hoje só a aba
"GateKeeper AI" tem lógica de verdade — as outras existem para mostrar
o que está planejado (ver docs/ROADMAP.md) sem fingir que já funcionam.

Para abrir:
    streamlit run ui/app.py

Isso abre uma aba no seu navegador em http://localhost:8501
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.guardrails import authorize
from core.scope import Scope
from modules.ai_llm.runner import PROBES_DIR, execute, load_adapter, load_probes
from modules.reporting.generate import build_markdown_report

ROOT = pathlib.Path(__file__).resolve().parent.parent

st.set_page_config(page_title="GateKeeper", page_icon="🛡️", layout="wide")

DAYS_PT = {"mon": "Seg", "tue": "Ter", "wed": "Qua", "thu": "Qui", "fri": "Sex", "sat": "Sáb", "sun": "Dom"}
AI_FORMATS = [
    "Formato simples: eu envio {\"message\": \"...\"} e recebo {\"response\": \"...\"}",
    "Formato OpenAI (chat completions)",
]


def _probe_prompt_text(p: dict) -> str:
    """Mesmo critério usado em runner.execute() para exibir o prompt."""
    return p.get("prompt") or " -> ".join(p.get("multi_turn", []))


def _get_scope() -> Scope:
    # Recarrega do disco a cada rerender — é um app local de uso individual,
    # não precisa de cache; e garante que uma edição salva na aba
    # Configuração apareça imediatamente nas abas de agente.
    return Scope.load_or_blank()


def render_home() -> None:
    st.title("🛡️ GateKeeper")
    st.caption("Plataforma interna de testes de segurança — um agente por frente de teste, antes de publicar.")

    st.markdown(
        """
Cada aba acima é um **agente especializado** numa frente de teste de
segurança. A ideia é simples: antes de publicar algo (um agente de IA,
uma API, uma configuração de cloud, etc.), você roda o agente
correspondente aqui e decide com base no relatório — não publica "no
escuro".
        """
    )

    st.divider()
    st.subheader("Agentes")
    st.markdown(
        """
| Agente | O que testa | Status |
|---|---|---|
| **GateKeeper AI** | Agentes de IA / LLM — prompt injection, jailbreak, vazamento de dados, uso indevido de ferramentas (OWASP Top 10 for LLM) | ✅ Funcional |
| **GateKeeper API** | Aplicações web e APIs — OWASP Top 10 / API Security Top 10 | 🔜 Planejado (Fase 2) |
| **GateKeeper Cloud** | Postura de configuração AWS/Azure/GCP (IAM, exposição de dados) | 📋 Planejado (Fase 3) |
| **GateKeeper Network** | Rede interna e Active Directory | 📋 Planejado (Fase 4) |
| **GateKeeper Mobile** | Apps mobile (OWASP MASVS/MASTG) | 📋 Planejado (Fase 5) |
        """
    )
    st.caption("Status detalhado e critério de 'pronto' por agente: `docs/ROADMAP.md`.")

    st.divider()
    st.subheader("Antes de usar qualquer agente")
    st.markdown(
        """
1. Preencha a aba **⚙️ Configuração** — autorização (ROE), janela de
   teste e cadastro do(s) agente(s). Sem isso, nenhum agente libera o
   botão de executar.
2. Leia o relatório gerado por cada agente — nenhum veredito automático
   substitui decisão humana sobre publicar ou não.
        """
    )


def render_config() -> None:
    st.header("⚙️ Configuração — guardrails")
    st.caption(
        "Isto é o que impede qualquer agente de rodar contra um alvo sem autorização. "
        "Preencha aqui uma vez; as abas de agente passam a usar esse cadastro."
    )

    scope = _get_scope()
    auth = scope.raw.setdefault("authorization", {})
    window_cfg = scope.raw.setdefault(
        "active_test_window", {"days": [], "start_time": "08:00", "end_time": "20:00", "timezone": "America/Sao_Paulo"}
    )

    # --- Status atual, antes de qualquer edição ---
    st.subheader("Status atual")
    scope_path_exists = (ROOT / "config" / "scope.yaml").exists()
    try:
        authz_ok = scope.authorization_valid()
    except Exception:
        authz_ok = False
    window_open_now = scope.active_window.is_open()

    c1, c2, c3 = st.columns(3)
    c1.metric("Arquivo de escopo", "Existe" if scope_path_exists else "Não criado ainda")
    c2.metric("Autorização (ROE)", "✅ Válida" if authz_ok else "🚫 Vencida / não preenchida")
    c3.metric("Dentro da janela de teste agora", "✅ Sim" if window_open_now else "⏸️ Não (informativo)")

    st.divider()
    st.subheader("1. Autorização (ROE)")
    st.caption("Sem isto válido, o botão de executar fica bloqueado em todas as abas de agente.")

    col1, col2 = st.columns(2)
    with col1:
        approved_by = st.text_input("Aprovado por (nome/cargo)", value=auth.get("approved_by", ""), key="cfg_approved_by")
        roe_document = st.text_input(
            "Referência do documento de ROE assinado (ex: caminho/link)", value=auth.get("roe_document", ""), key="cfg_roe_document"
        )
    with col2:
        try:
            default_from = dt.date.fromisoformat(auth["valid_from"]) if auth.get("valid_from") else dt.date.today()
        except ValueError:
            default_from = dt.date.today()
        try:
            default_until = (
                dt.date.fromisoformat(auth["valid_until"]) if auth.get("valid_until") else dt.date.today() + dt.timedelta(days=90)
            )
        except ValueError:
            default_until = dt.date.today() + dt.timedelta(days=90)
        valid_from = st.date_input("Válido a partir de", value=default_from, key="cfg_valid_from")
        valid_until = st.date_input("Válido até", value=default_until, key="cfg_valid_until")

    st.subheader("2. Janela de teste ativo")
    st.caption("Informativo para agentes com ação ativa (ex: varredura de rede). O GateKeeper AI roda a qualquer hora dentro da autorização válida.")
    col3, col4, col5 = st.columns(3)
    with col3:
        selected_days = st.multiselect(
            "Dias permitidos",
            list(DAYS_PT.keys()),
            default=window_cfg.get("days", []),
            format_func=lambda d: DAYS_PT[d],
            key="cfg_days",
        )
    with col4:
        start_time = st.time_input(
            "Início", value=dt.time.fromisoformat(window_cfg.get("start_time", "08:00")), key="cfg_start_time"
        )
    with col5:
        end_time = st.time_input(
            "Fim", value=dt.time.fromisoformat(window_cfg.get("end_time", "20:00")), key="cfg_end_time"
        )
    timezone = st.text_input("Fuso horário", value=window_cfg.get("timezone", "America/Sao_Paulo"), key="cfg_timezone")

    if st.button("💾 Salvar autorização e janela de teste", type="primary", key="cfg_save_auth"):
        scope.raw["authorization"] = {
            "roe_document": roe_document,
            "approved_by": approved_by,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }
        scope.raw["active_test_window"] = {
            "days": selected_days,
            "start_time": start_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "timezone": timezone,
        }
        scope.save()
        st.success("Salvo em `config/scope.yaml`. Recarregando status...")
        st.rerun()

    st.divider()
    st.subheader("3. Agentes cadastrados — GateKeeper AI")
    st.caption(
        "Cadastre aqui o(s) agente(s) de IA que você vai testar. A chave de API fica salva em texto "
        "simples em `config/scope.yaml` (fora do git) — não é um cofre de segredos; aceitável para "
        "uso local de uma pessoa/equipe pequena, não para múltiplos usuários sem controle de acesso."
    )

    existing = scope.targets_for("ai_llm")
    if existing:
        st.dataframe(
            [
                {
                    "nome": t.get("name"),
                    "ambiente": t.get("environment"),
                    "endpoint": t.get("adapter", {}).get("kwargs", {}).get("endpoint", ""),
                }
                for t in existing
            ],
            use_container_width=True,
            hide_index=True,
        )
        remove_name = st.selectbox(
            "Remover agente cadastrado", ["(nenhum)"] + [t["name"] for t in existing], key="cfg_remove_select"
        )
        if remove_name != "(nenhum)" and st.button(f"🗑️ Remover '{remove_name}'", key="cfg_remove_btn"):
            scope.remove_target("ai_llm", remove_name)
            scope.save()
            st.success(f"Agente '{remove_name}' removido.")
            st.rerun()
    else:
        st.info("Nenhum agente de IA cadastrado ainda. Cadastre um abaixo.", icon="ℹ️")

    with st.form("cfg_new_agent_form"):
        st.markdown("**Cadastrar novo agente**")
        col_a, col_b = st.columns(2)
        with col_a:
            new_name = st.text_input("Nome do agente", placeholder="ex: chatbot-atendimento-v1")
            new_environment = st.selectbox("Ambiente", ["staging / teste", "desenvolvimento", "produção (cuidado!)"])
            new_endpoint = st.text_input("Endereço (URL) do agente", placeholder="https://meu-agente-staging.exemplo.com/chat")
        with col_b:
            new_format = st.selectbox("Como o agente responde?", AI_FORMATS)
            new_api_key = st.text_input("Chave de API / token (se precisar)", type="password")
            new_text_field = "response"
            if new_format.startswith("Formato simples"):
                new_text_field = st.text_input("Nome do campo com o texto na resposta JSON", value="response")

        submitted = st.form_submit_button("💾 Salvar agente")
        if submitted:
            if not new_name or not new_endpoint:
                st.error("Nome e endereço (URL) são obrigatórios.")
            else:
                if new_format.startswith("Formato simples"):
                    adapter_cfg = {
                        "path": "modules.ai_llm.adapters.http_adapter:simple_json_adapter",
                        "kwargs": {"endpoint": new_endpoint, "api_key": new_api_key, "text_field": new_text_field},
                    }
                else:
                    adapter_cfg = {
                        "path": "modules.ai_llm.adapters.http_adapter:example_openai_style_adapter",
                        "kwargs": {"endpoint": new_endpoint, "api_key": new_api_key},
                    }
                scope.upsert_target(
                    "ai_llm",
                    {"name": new_name, "environment": new_environment, "adapter": adapter_cfg, "allow_active": False},
                )
                scope.save()
                st.success(f"Agente '{new_name}' salvo.")
                st.rerun()


def render_gatekeeper_ai() -> None:
    st.header("🤖 GateKeeper AI — robustez de agentes de IA pré-publicação")
    st.caption(
        "Envia uma bateria de tentativas conhecidas de ataque (prompt injection, "
        "jailbreak, vazamento de dados, etc. — baseadas no OWASP Top 10 for LLM) "
        "contra o seu agente, antes de ele ir para produção."
    )

    checklist_path = ROOT / "docs" / "CHECKLIST_LLM_MANUAL.md"
    st.download_button(
        "📋 Baixar checklist manual (itens do OWASP LLM Top 10 que não dá pra testar automaticamente)",
        data=checklist_path.read_text(),
        file_name="checklist-llm-manual.md",
        mime="text/markdown",
        key="ai_checklist_download",
    )
    st.caption(
        "O teste automático abaixo cobre 6 das 10 categorias do OWASP Top 10 for LLM. "
        "As outras 4 (dados de treinamento, cadeia de suprimentos, excesso de confiança, "
        "roubo de modelo) exigem revisão manual de arquitetura/processo — use o checklist acima."
    )

    with st.expander("⚠️ Leia antes de usar", expanded=False):
        st.markdown(
            """
- Use isto apenas contra agentes que **você tem autorização para testar**
  (seus próprios agentes, em ambiente de dev/staging).
- Passar todos os testes **não significa que o agente é seguro** — significa
  que ele resistiu aos ataques já catalogados aqui. Leia as respostas, não
  só o veredito.
- Não aponte isto para o agente de outra empresa ou para produção com
  usuários reais sem avaliar o risco com sua equipe primeiro.
            """
        )

    scope = _get_scope()
    targets = scope.targets_for("ai_llm")

    st.divider()
    st.subheader("1. Escolher agente cadastrado")

    if not targets:
        st.warning(
            "Nenhum agente cadastrado. Vá para a aba **⚙️ Configuração** e cadastre um agente antes de testar.",
            icon="⚠️",
        )
        target_cfg = None
    else:
        target_names = [t["name"] for t in targets]
        selected_name = st.selectbox("Agente", target_names, key="ai_selected_target")
        target_cfg = next(t for t in targets if t["name"] == selected_name)
        endpoint = target_cfg.get("adapter", {}).get("kwargs", {}).get("endpoint", "")
        st.caption(f"Ambiente: **{target_cfg.get('environment', '?')}** · Endpoint: `{endpoint}`")
        if target_cfg.get("environment") == "produção (cuidado!)":
            st.warning(
                "Este agente está cadastrado como 'produção'. Os testes enviam prompts adversariais "
                "reais — se o agente atende usuários reais agora, essas mensagens vão aparecer nas "
                "conversas reais. Prefira sempre staging/teste.",
                icon="⚠️",
            )

    st.divider()
    st.subheader("2. Status do guardrail")

    can_run = False
    block_reason = ""
    if target_cfg is None:
        block_reason = "Nenhum agente cadastrado/selecionado."
    else:
        guardrail_result = authorize(scope, module="ai_llm", target_identifier=target_cfg["name"], mode="passive", confirm=False)
        try:
            authz_ok = scope.authorization_valid()
        except Exception:
            authz_ok = False

        if not guardrail_result.allowed:
            block_reason = guardrail_result.reason
        elif not authz_ok:
            block_reason = "Autorização (ROE) vencida ou não preenchida na aba Configuração."
        else:
            can_run = True

    if can_run:
        st.success("Guardrail OK: agente no escopo autorizado, dentro da validade do ROE.", icon="✅")
    else:
        st.error(f"Bloqueado: {block_reason}", icon="🚫")

    probes = load_probes()
    st.caption(f"{len(probes)} testes carregados de `{PROBES_DIR}` (categorias OWASP LLM Top 10 + jailbreak genérico).")

    st.divider()
    st.subheader("2.1 Consultar os prompts de teste")
    st.caption(
        "Veja exatamente o texto que será enviado ao agente em cada teste baseado em prompt — "
        "útil para auditoria antes de autorizar a execução, ou para entender um achado do relatório."
    )

    col_q1, col_q2 = st.columns([2, 1])
    with col_q1:
        search_query = st.text_input(
            "Buscar por palavra no prompt, no ID do teste ou na categoria",
            placeholder="ex: system prompt, SSRF, jb-01, LLM07...",
            key="ai_search_query",
        )
    with col_q2:
        categories = sorted({p["category"] for p in probes})
        selected_categories = st.multiselect("Filtrar por categoria", categories, key="ai_selected_categories")

    filtered_probes = probes
    if selected_categories:
        filtered_probes = [p for p in filtered_probes if p["category"] in selected_categories]
    if search_query:
        q = search_query.lower()
        filtered_probes = [
            p
            for p in filtered_probes
            if q in p["id"].lower() or q in p["category"].lower() or q in _probe_prompt_text(p).lower()
        ]

    st.caption(f"{len(filtered_probes)} de {len(probes)} testes correspondem ao filtro.")
    for p in filtered_probes:
        with st.expander(f"{p['id']} — {p['category']} ({p['_source_file']})"):
            st.markdown("**Prompt enviado ao agente:**")
            st.code(_probe_prompt_text(p), language=None)
            if p.get("note"):
                st.caption(f"Observação: {p['note']}")
            if p.get("expect_contains_any"):
                st.caption(f"Sinal de falha procurado na resposta: {p['expect_contains_any']}")
            if p.get("expect_tool_calls_without_confirmation"):
                st.caption(f"Ferramentas sensíveis monitoradas: {p['expect_tool_calls_without_confirmation']}")
            if p.get("expect_dangerous_tool_args_patterns"):
                st.caption(
                    f"Padrões perigosos monitorados nos argumentos de ferramenta: {p['expect_dangerous_tool_args_patterns']}"
                )

    st.divider()
    st.subheader("3. Executar")

    col_a, col_b = st.columns(2)
    preview_clicked = col_a.button("👀 Ver quais testes serão enviados (não chama o agente)", key="ai_preview_btn")
    run_clicked = col_b.button("▶️ Rodar teste de verdade", disabled=not can_run, type="primary", key="ai_run_btn")

    if preview_clicked:
        st.write("Estes são os testes que seriam enviados (nenhuma chamada foi feita ainda):")
        st.dataframe(
            [{"id": p["id"], "categoria": p["category"], "arquivo": p["_source_file"]} for p in probes],
            use_container_width=True,
            hide_index=True,
        )

    if run_clicked and target_cfg is not None:
        adapter = load_adapter(target_cfg["adapter"]["path"], target_cfg["adapter"].get("kwargs", {}))

        progress = st.progress(0.0, text="Rodando testes...")
        results = []
        try:
            results, out_path = execute(adapter, probes, target_cfg["name"])
        except Exception as exc:  # noqa: BLE001 — queremos mostrar qualquer erro de conexão pro usuário
            st.error(
                f"Não consegui falar com o agente '{target_cfg['name']}'. Erro técnico: {exc}\n\n"
                "Causas comuns: URL errada, agente exige outra chave/autenticação, "
                "ou o formato de resposta é diferente do cadastrado."
            )
        progress.progress(1.0, text="Concluído.")

        if results:
            flagged = [r for r in results if r["flagged"]]
            ok = [r for r in results if not r["flagged"]]

            c1, c2, c3 = st.columns(3)
            c1.metric("Total de testes", len(results))
            c2.metric("🚩 Sinalizados (revisar)", len(flagged))
            c3.metric("✅ Sem sinal de problema", len(ok))

            report_md = build_markdown_report(target_cfg["name"], target_cfg.get("environment", ""), results)
            st.download_button(
                "⬇️ Baixar relatório (.md — abre em Word/Google Docs, ou use 'imprimir' do navegador para gerar PDF)",
                data=report_md,
                file_name=f"relatorio-{target_cfg['name'].replace(' ', '-')}.md",
                mime="text/markdown",
                key="ai_report_download",
            )
            st.caption(f"Dado bruto também salvo em: `{out_path}`")

            if flagged:
                st.markdown("### 🚩 Testes sinalizados — revise antes de publicar o agente")
                for r in flagged:
                    with st.expander(f"{r['probe_id']} — {r['category']}"):
                        st.markdown(f"**O que foi enviado ao agente:**\n\n> {r['prompt']}")
                        st.markdown(f"**O que o agente respondeu:**\n\n> {r['response_text']}")
                        st.markdown(f"**Por que foi sinalizado:** {'; '.join(r['reasons'])}")
                        if r.get("note"):
                            st.caption(r["note"])

            with st.expander("Ver todos os testes (incluindo os que passaram)"):
                st.dataframe(
                    [
                        {"id": r["probe_id"], "categoria": r["category"], "sinalizado": "🚩" if r["flagged"] else "✅"}
                        for r in results
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.info(
                "Lembrete: um teste sinalizado precisa de leitura humana — pode ser falso positivo. "
                "Um agente sem nenhum sinal não está 'aprovado' automaticamente; decida com sua equipe.",
                icon="ℹ️",
            )


def render_placeholder(agent_name: str, icon: str, phase_label: str, description: str, module_dir: str) -> None:
    st.header(f"{icon} {agent_name}")
    st.info(
        f"**Ainda não implementado.** Previsto como {phase_label} do roadmap — ver `docs/ROADMAP.md`.",
        icon="🚧",
    )
    st.markdown(description)
    readme_path = ROOT / "modules" / module_dir / "README.md"
    if readme_path.exists():
        with st.expander(f"Ver README técnico de `modules/{module_dir}/`"):
            st.markdown(readme_path.read_text())


home_tab, config_tab, ai_tab, api_tab, cloud_tab, network_tab, mobile_tab = st.tabs(
    [
        "🏠 Início",
        "⚙️ Configuração",
        "🤖 GateKeeper AI",
        "🌐 GateKeeper API",
        "☁️ GateKeeper Cloud",
        "🖧 GateKeeper Network",
        "📱 GateKeeper Mobile",
    ]
)

with home_tab:
    render_home()

with config_tab:
    render_config()

with ai_tab:
    render_gatekeeper_ai()

with api_tab:
    render_placeholder(
        "GateKeeper API",
        "🌐",
        "Fase 2",
        "Vai testar aplicações web e APIs contra o OWASP Top 10 e o OWASP API Security Top 10 "
        "(injeção, autenticação quebrada, exposição de dados, falta de rate limiting, etc.), "
        "orquestrando ferramentas como OWASP ZAP e Nuclei.",
        "web",
    )

with cloud_tab:
    render_placeholder(
        "GateKeeper Cloud",
        "☁️",
        "Fase 3",
        "Vai revisar postura de configuração em AWS/Azure/GCP — IAM permissivo, buckets/serviços "
        "expostos publicamente, segredos mal guardados — por leitura de configuração, sem ação ativa.",
        "cloud",
    )

with network_tab:
    render_placeholder(
        "GateKeeper Network",
        "🖧",
        "Fase 4",
        "Vai varrer rede interna e Active Directory. É o agente de maior risco operacional "
        "(pode degradar serviço ou travar contas) — por isso só entra depois dos outros estarem maduros.",
        "network",
    )

with mobile_tab:
    render_placeholder(
        "GateKeeper Mobile",
        "📱",
        "Fase 5",
        "Vai testar apps mobile contra o OWASP MASVS/MASTG — armazenamento inseguro, comunicação "
        "sem TLS pinning, binário sem proteção contra engenharia reversa.",
        "mobile",
    )
