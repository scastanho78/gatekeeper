"""Gera um relatório legível (Markdown) a partir dos resultados de um
teste de ai_llm — pensado para ser lido por alguém não-técnico (board,
compliance) ou anexado a um processo de aprovação de publicação.
"""
from __future__ import annotations

import datetime as dt


def build_markdown_report(target_name: str, environment: str, results: list[dict]) -> str:
    total = len(results)
    flagged = [r for r in results if r["flagged"]]
    ok = [r for r in results if not r["flagged"]]
    now = dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = [
        f"# Relatório de teste de robustez — {target_name}",
        "",
        f"**Data do teste:** {now}  ",
        f"**Ambiente testado:** {environment}  ",
        f"**Metodologia:** OWASP Top 10 for LLM Applications + jailbreak genérico  ",
        "",
        "## Resumo executivo",
        "",
        f"- Total de testes enviados: **{total}**",
        f"- Sinalizados para revisão: **{len(flagged)}**",
        f"- Sem sinal de problema: **{len(ok)}**",
        "",
    ]

    if flagged:
        lines.append(
            f"⚠️ **{len(flagged)} de {total} testes foram sinalizados.** "
            "Isso não significa necessariamente que o agente está inseguro — "
            "cada item abaixo precisa de leitura humana antes de qualquer decisão "
            "sobre publicação. Pode haver falso positivo."
        )
    else:
        lines.append(
            "✅ Nenhum teste foi sinalizado pela bateria atual. **Isto não é uma "
            "certificação de segurança** — significa apenas que o agente resistiu "
            "aos ataques catalogados nesta versão da suíte de testes."
        )
    lines.append("")

    lines.append("## Achados sinalizados (requerem decisão humana)")
    lines.append("")
    if not flagged:
        lines.append("_Nenhum achado nesta execução._")
    else:
        for r in flagged:
            lines += [
                f"### {r['probe_id']} — categoria {r['category']}",
                "",
                f"**O que foi enviado ao agente:**",
                "",
                f"> {r['prompt']}",
                "",
                f"**O que o agente respondeu:**",
                "",
                f"> {r['response_text']}",
                "",
                f"**Motivo da sinalização:** {'; '.join(r['reasons'])}",
                "",
            ]
            if r.get("note"):
                lines.append(f"_Observação: {r['note']}_")
                lines.append("")
            lines.append("**Decisão / ação tomada:** ___________________________")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## Todos os testes executados")
    lines.append("")
    lines.append("| ID | Categoria | Resultado |")
    lines.append("|---|---|---|")
    for r in results:
        status = "🚩 Sinalizado" if r["flagged"] else "✅ OK"
        lines.append(f"| {r['probe_id']} | {r['category']} | {status} |")
    lines.append("")

    lines.append("## Limitações deste teste")
    lines.append("")
    lines += [
        "- Cobre apenas padrões de ataque já catalogados nesta suíte — não é uma",
        "  avaliação completa de segurança do agente.",
        "- A sinalização é por heurística de texto, não por revisão humana — todo",
        "  item sinalizado (e uma amostra dos não sinalizados) deveria ser lido",
        "  manualmente antes de aprovar a publicação.",
        "- Não avalia a infraestrutura por trás do agente (isso é outro módulo:",
        "  `modules/web` / `modules/cloud`, ainda não implementado neste projeto).",
    ]

    return "\n".join(lines)
