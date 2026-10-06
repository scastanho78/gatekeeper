# Checklist manual — OWASP Top 10 for LLM (itens não testáveis por sondagem de prompt)

Quatro das dez categorias do OWASP Top 10 for LLM Applications não têm
como ser verificadas automaticamente enviando prompts a um agente — são
questões de arquitetura, processo de dados e governança, que exigem
revisão humana contra a documentação técnica real do agente.

Use este checklist **antes de aprovar a publicação** de qualquer agente,
em conjunto com o relatório automático gerado pela tela de testes
(`ui/app.py`), que cobre as outras 6 categorias.

> Preencha com Sim/Não/Não se aplica + evidência (link, print, nome de
> quem verificou). "Não sei" deve ser tratado como "Não" até ser
> verificado — não assuma que está ok.

---

## LLM03 — Training Data Poisoning

| Item | Resposta | Evidência |
|---|---|---|
| Os dados usados para treinar/ajustar (fine-tuning) o modelo têm origem rastreável e confiável? | | |
| Se usa RAG (busca em base própria), a base de documentos é controlada por acesso (só gente autorizada escreve nela)? | | |
| Existe processo de revisão para novos documentos/dados antes de entrarem na base que o agente consulta? | | |
| Se o agente aprende com feedback de usuários em produção, há filtro contra manipulação deliberada desse feedback? | | |

## LLM05 — Supply Chain Vulnerabilities

| Item | Resposta | Evidência |
|---|---|---|
| O modelo usado (próprio ou de terceiro — OpenAI, Anthropic, modelo open-source) tem procedência conhecida e contrato/termos de uso revisados? | | |
| As bibliotecas/frameworks de orquestração (LangChain, etc.) estão em versões sem CVEs críticos conhecidos? (rodar `pip-audit` / `npm audit` / similar) | | |
| Plugins/ferramentas de terceiros conectados ao agente foram revisados quanto à origem e permissões que exigem? | | |
| Existe inventário de quais serviços externos o agente chama (LLM provider, bases vetoriais, APIs de terceiros)? | | |

## LLM09 — Overreliance

| Item | Resposta | Evidência |
|---|---|---|
| A saída do agente é claramente identificada como gerada por IA para o usuário final (não passa por humano sem aviso)? | | |
| Existe revisão humana obrigatória antes de qualquer ação de alto impacto decidida com base na saída do agente (ex: decisão financeira, jurídica, de segurança)? | | |
| Há mecanismo para o usuário reportar resposta errada/alucinada, e esse canal é monitorado? | | |
| A equipe que vai operar/supervisionar o agente foi treinada sobre os limites dele (ele pode "inventar" com confiança)? | | |

## LLM10 — Model Theft

| Item | Resposta | Evidência |
|---|---|---|
| Os pesos do modelo (se for modelo próprio/fine-tuned) ficam em armazenamento com controle de acesso e auditoria? | | |
| A API do agente tem rate limiting para dificultar extração do modelo por consultas em massa? | | |
| Chaves de API do agente são rotacionadas e não ficam hardcoded em repositório/frontend? | | |
| Há monitoramento de uso anômalo da API (volume muito acima do padrão, vindo de poucos IPs)? | | |

---

## Itens parcialmente automatizados — confirme a leitura, não só o veredito

- **LLM02 (Insecure Output Handling)**: o teste automático só checa se o
  payload aparece na resposta em texto. Confirme manualmente se o
  **frontend** de fato sanitiza antes de renderizar.
- **LLM04 (Model DoS)**: o teste automático só sinaliza latência/custo
  alto — não testa resiliência sob carga real. Se o agente for crítico,
  rode um teste de carga separado (fora deste projeto).
- **LLM07 (Insecure Plugin Design)** e **LLM08 (Excessive Agency)**: só
  detectam problema se o seu agente expõe os argumentos reais das
  chamadas de ferramenta para o adapter. Se o relatório automático não
  mostrou nenhum `tool_call` com argumentos, **isso não significa que
  está seguro** — pode ser que o adapter não tenha conseguido capturar
  essa informação. Confirme com quem construiu o agente.

---

## Aprovação final

| | |
|---|---|
| Responsável pela revisão deste checklist: | |
| Data: | |
| Resultado do teste automático (LLM01, LLM02, LLM04, LLM06, LLM07, LLM08): anexar relatório gerado pela tela | |
| Decisão: ( ) Aprovado para publicação  ( ) Aprovado com ressalvas  ( ) Reprovado | |
| Ressalvas / plano de ação (se houver): | |
