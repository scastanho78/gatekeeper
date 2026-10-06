# GateKeeper AI — Roadmap

Ordem de implementação pensada por: (a) superfície de risco/retorno,
(b) complexidade de guardrails necessários, (c) o que já existe em
ferramentas open source maduras vs. o que precisa de lógica própria.

| Fase | Módulo | Status | Por quê nessa ordem |
|---|---|---|---|
| 0 | `core` (guardrails + orquestrador) | ✅ Implementado | Sem isso, nenhum outro módulo deveria rodar. |
| 1 | `ai_llm` (OWASP Top 10 for LLM / agentes) | ✅ Esqueleto funcional | **Reprioritizado**: driver real agora é testar agentes de IA próprios antes de publicá-los — ambiente controlado (dev/staging interno), risco operacional baixo, valor alto (evita publicar agente vulnerável a prompt injection / excessive agency). |
| 2 | `web` (OWASP Top 10 / API Top 10) | ✅ Esqueleto funcional | Maior superfície de ataque típica, ferramentas maduras (ZAP, Nuclei, sqlmap), menor risco de indisponibilidade comparado a varredura de rede. Muitos agentes de IA são expostos via API web — este módulo complementa o `ai_llm`. |
| 3 | `recon` + `cloud` | 🔜 Próxima | Recon passivo é baixo risco; postura de configuração cloud (IAM, buckets expostos) tem alto impacto e baixo risco operacional (é leitura de config, não exploração). |
| 4 | `network` (rede interna / AD) | 📋 Planejado | Alto risco operacional (varredura pode degradar serviços, travar contas no AD por tentativa de senha). Precisa de guardrails extras (rate limiting, horário restrito, lista de exclusão de sistemas críticos). |
| 5 | `mobile` (OWASP MASVS/MASTG) | 📋 Planejado | Depende de infraestrutura separada (MobSF, emuladores/dispositivos), ciclo de build dos apps da empresa. |
| — | `reporting` | 🔜 Em paralelo com Fase 1 | Cresce junto com os módulos; começa simples (markdown) e evolui. |

## Critério de "pronto" por módulo

Um módulo só sai de 🔜/📋 para ✅ quando tiver:
- Guardrail de escopo aplicado antes de qualquer chamada ativa.
- Modo `--dry-run` que mostra o que seria executado sem tocar em nada.
- Saída estruturada (JSON) consumível pelo `reporting`.
- Mapeamento explícito para a metodologia de referência (OWASP Testing
  Guide, OWASP API Top 10, OWASP MASVS, OWASP LLM Top 10, MITRE ATT&CK
  conforme o caso).

## Próximos passos imediatos sugeridos

1. Preencher `config/scope.yaml` com os ativos web reais já autorizados.
2. Rodar `modules/web` em modo `--dry-run` contra um ambiente de staging
   para validar o fluxo antes de qualquer execução ativa em produção.
3. Definir quem além do CISO pode usar `--confirm` (registrar em ROE).
