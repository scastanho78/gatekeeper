"""GateKeeper — plataforma de testes de segurança internos.

Tela única com uma aba por agente (um agente por tipo de teste: IA/LLM,
API/web, cloud, rede, mobile). Hoje só a aba "GateKeeper AI" tem lógica
de verdade — as outras existem para mostrar o que está planejado
(ver docs/ROADMAP.md) sem fingir que já funcionam.

Para abrir:
    streamlit run ui/app.py

Isso abre uma aba no seu navegador em http://localhost:8501
"""
from __future__ import annotations

import pathlib
import sys

import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from modules.ai_llm.adapters.http_adapter import example_openai_style_adapter, simple_json_adapter
from modules.ai_llm.runner import PROBES_DIR, execute, load_probes
from modules.reporting.generate import build_markdown_report

ROOT = pathlib.Path(__file__).resolve().parent.parent

st.set_page_config(page_title="GateKeeper", page_icon="🛡️", layout="wide")


def _probe_prompt_text(p: dict) -> str:
    """Mesmo critério usado em runner.execute() para exibir o prompt."""
    return p.get("prompt") or " -> ".join(p.get("multi_turn", []))


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
1. Tenha autorização formal registrada (`docs/ROE_TEMPLATE.md`).
2. O alvo precisa estar listado em `config/scope.yaml` — nenhum agente
   roda contra um alvo fora do escopo autorizado.
3. Leia o relatório gerado por cada agente — nenhum veredito automático
   substitui decisão humana sobre publicar ou não.
        """
    )


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

    st.divider()
    st.subheader("1. Dados do agente")

    col1, col2 = st.columns(2)
    with col1:
        target_name = st.text_input(
            "Nome do agente (livre, só para identificar nos relatórios)",
            placeholder="ex: chatbot-atendimento-v1",
            key="ai_target_name",
        )
        environment = st.selectbox(
            "Ambiente", ["staging / teste", "desenvolvimento", "produção (cuidado!)"], key="ai_environment"
        )
        endpoint = st.text_input(
            "Endereço (URL) do agente", placeholder="https://meu-agente-staging.exemplo.com/chat", key="ai_endpoint"
        )

    with col2:
        api_format = st.selectbox(
            "Como o agente responde?",
            [
                "Formato simples: eu envio {\"message\": \"...\"} e recebo {\"response\": \"...\"}",
                "Formato OpenAI (chat completions)",
            ],
            key="ai_api_format",
        )
        api_key = st.text_input(
            "Chave de API / token (se precisar)", type="password", placeholder="deixe em branco se não precisar", key="ai_api_key"
        )
        text_field = "response"
        if api_format.startswith("Formato simples"):
            text_field = st.text_input("Nome do campo com o texto na resposta JSON", value="response", key="ai_text_field")

    st.divider()
    st.subheader("2. Confirmação")

    confirmed = st.checkbox(
        "Confirmo que tenho autorização para testar este agente, e que ele está em ambiente de teste "
        "(não é produção com usuários reais sendo afetados por esses testes).",
        key="ai_confirmed",
    )

    if environment == "produção (cuidado!)" and confirmed:
        st.warning(
            "Você marcou 'produção'. Os testes aqui enviam prompts adversariais reais ao agente. "
            "Se ele estiver atendendo usuários reais agora, essas mensagens vão aparecer nas "
            "conversas reais. Prefira sempre staging/teste.",
            icon="⚠️",
        )

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
    run_clicked = col_b.button(
        "▶️ Rodar teste de verdade", disabled=not (target_name and endpoint and confirmed), type="primary", key="ai_run_btn"
    )

    if preview_clicked:
        st.write("Estes são os testes que seriam enviados (nenhuma chamada foi feita ainda):")
        st.dataframe(
            [{"id": p["id"], "categoria": p["category"], "arquivo": p["_source_file"]} for p in probes],
            use_container_width=True,
            hide_index=True,
        )

    if run_clicked:
        if api_format.startswith("Formato simples"):
            adapter = simple_json_adapter(endpoint=endpoint, api_key=api_key, text_field=text_field)
        else:
            adapter = example_openai_style_adapter(endpoint=endpoint, api_key=api_key)

        progress = st.progress(0.0, text="Rodando testes...")
        results = []
        try:
            results, out_path = execute(adapter, probes, target_name or "agente-sem-nome")
        except Exception as exc:  # noqa: BLE001 — queremos mostrar qualquer erro de conexão pro usuário
            st.error(
                f"Não consegui falar com o agente em '{endpoint}'. Erro técnico: {exc}\n\n"
                "Causas comuns: URL errada, agente exige outra chave/autenticação, "
                "ou o formato de resposta é diferente do que foi selecionado acima."
            )
        progress.progress(1.0, text="Concluído.")

        if results:
            flagged = [r for r in results if r["flagged"]]
            ok = [r for r in results if not r["flagged"]]

            c1, c2, c3 = st.columns(3)
            c1.metric("Total de testes", len(results))
            c2.metric("🚩 Sinalizados (revisar)", len(flagged))
            c3.metric("✅ Sem sinal de problema", len(ok))

            report_md = build_markdown_report(target_name or "agente-sem-nome", environment, results)
            st.download_button(
                "⬇️ Baixar relatório (.md — abre em Word/Google Docs, ou use 'imprimir' do navegador para gerar PDF)",
                data=report_md,
                file_name=f"relatorio-{(target_name or 'agente').replace(' ', '-')}.md",
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


home_tab, ai_tab, api_tab, cloud_tab, network_tab, mobile_tab = st.tabs(
    [
        "🏠 Início",
        "🤖 GateKeeper AI",
        "🌐 GateKeeper API",
        "☁️ GateKeeper Cloud",
        "🖧 GateKeeper Network",
        "📱 GateKeeper Mobile",
    ]
)

with home_tab:
    render_home()

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
