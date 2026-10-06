"""Tela simples (navegador) para testar um agente de IA antes de
publicá-lo, sem precisar usar linha de comando.

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

st.set_page_config(page_title="Teste de Agentes de IA", page_icon="🛡️", layout="wide")

st.title("🛡️ Teste de robustez de agentes de IA — pré-publicação")
st.caption(
    "Envia uma bateria de tentativas conhecidas de ataque (prompt injection, "
    "jailbreak, vazamento de dados, etc. — baseadas no OWASP Top 10 for LLM) "
    "contra o seu agente, antes de ele ir para produção."
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
    target_name = st.text_input("Nome do agente (livre, só para identificar nos relatórios)", placeholder="ex: chatbot-atendimento-v1")
    environment = st.selectbox("Ambiente", ["staging / teste", "desenvolvimento", "produção (cuidado!)"])
    endpoint = st.text_input("Endereço (URL) do agente", placeholder="https://meu-agente-staging.exemplo.com/chat")

with col2:
    api_format = st.selectbox(
        "Como o agente responde?",
        [
            "Formato simples: eu envio {\"message\": \"...\"} e recebo {\"response\": \"...\"}",
            "Formato OpenAI (chat completions)",
        ],
    )
    api_key = st.text_input("Chave de API / token (se precisar)", type="password", placeholder="deixe em branco se não precisar")
    text_field = "response"
    if api_format.startswith("Formato simples"):
        text_field = st.text_input("Nome do campo com o texto na resposta JSON", value="response")

st.divider()
st.subheader("2. Confirmação")

confirmed = st.checkbox(
    "Confirmo que tenho autorização para testar este agente, e que ele está em ambiente de teste "
    "(não é produção com usuários reais sendo afetados por esses testes)."
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
st.subheader("3. Executar")

col_a, col_b = st.columns(2)
preview_clicked = col_a.button("👀 Ver quais testes serão enviados (não chama o agente)")
run_clicked = col_b.button("▶️ Rodar teste de verdade", disabled=not (target_name and endpoint and confirmed), type="primary")

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

        st.caption(f"Relatório completo salvo em: `{out_path}`")

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
