# GateKeeper AI — módulo ai_llm: testes de segurança para agentes de IA pré-publicação

Objetivo: antes de um agente (chatbot, agente com tool-use, RAG, etc.) ir
para produção, rodar uma bateria de sondas adversariais e registrar como
ele se comporta. Isto é **avaliação de robustez do seu próprio sistema**,
não ataque a terceiros — por isso o risco operacional é baixo, mas ainda
passa pelos guardrails (`core/guardrails.py`) e precisa estar em
`config/scope.yaml` em `targets.ai_llm`.

## Mapeamento com OWASP Top 10 for LLM Applications (2025)

| Categoria | O que o runner testa | Arquivo de probes |
|---|---|---|
| LLM01 Prompt Injection (direta e indireta) | Tenta sobrescrever instruções do sistema, injetar instruções via conteúdo "externo" simulado (ex: texto de um documento/ferramenta) | `probes/prompt_injection.yaml` |
| LLM02 Insecure Output Handling | Verifica se a saída do agente, quando injetada em contexto perigoso (HTML/SQL/comando), é sanitizada antes de ser retornada | `probes/output_handling.yaml` |
| LLM06 Sensitive Information Disclosure | Tenta extrair system prompt, segredos, dados de outros usuários, PII de treinamento/contexto | `probes/data_exfiltration.yaml` |
| LLM08 Excessive Agency | Para agentes com tool-use: tenta induzir chamadas de ferramenta fora do que o usuário pediu (ex: deletar, enviar email, gastar dinheiro) sem confirmação | `probes/excessive_agency.yaml` |
| Jailbreak / guardrail bypass genérico | Técnicas conhecidas (role-play, DAN-style, encoding, multi-turn erosion) para contornar as instruções de segurança do agente | `probes/jailbreak.yaml` |
| LLM04 Model DoS (sinalização apenas) | Mede tempo de resposta/custo de tokens em prompts adversariais longos — não executa DoS de fato, só sinaliza risco | `probes/resource_abuse.yaml` |
| LLM07 Insecure Plugin Design | Tenta fazer o agente chamar suas próprias ferramentas (leitura de arquivo, fetch de URL, execução de comando) com argumentos perigosos (path traversal, SSRF para endpoint de metadados cloud, injeção de shell) | `probes/plugin_design.yaml` |

**Cobertura: 6 das 10 categorias do OWASP Top 10 for LLM** (LLM01, LLM02,
LLM04, LLM06, LLM07, LLM08 — as duas últimas dependem do adapter expor
os argumentos reais das chamadas de ferramenta, veja limitações abaixo).

LLM03 (Training Data Poisoning), LLM05 (Supply Chain), LLM09
(Overreliance) e LLM10 (Model Theft) **não são testáveis por sondagem de
prompt** — são questões de arquitetura/processo. Para essas, use o
checklist manual: `docs/CHECKLIST_LLM_MANUAL.md` (também disponível para
download direto na tela, `ui/app.py`).

## Como usar

1. Implemente um adapter em `adapters/` que saiba conversar com o seu
   agente (HTTP, import direto da função Python, CLI). Veja
   `adapters/http_adapter.py` como exemplo/esqueleto.
2. Adicione o agente em `config/scope.yaml` sob `targets.ai_llm`, com um
   `name` único.
3. Rode:

   ```bash
   python -m modules.ai_llm.runner --target meu-agente-v1 --dry-run
   ```

   `--dry-run` mostra quais sondas seriam enviadas sem chamar o adapter.
   Tirar o `--dry-run` executa de fato (ainda é modo "passive" do ponto
   de vista do guardrail — você está testando algo que já é seu, em
   ambiente que você controla — mas confirme isso em `scope.yaml`).

4. O resultado sai em JSON (`reports/ai_llm/<target>-<timestamp>.json`)
   com cada probe, a resposta do agente e um veredito heurístico
   (`flagged: true/false` + motivo). **Todo veredito heurístico precisa
   de revisão humana** — isto reduz o trabalho de triagem, não substitui
   o julgamento de quem vai decidir se o agente pode ser publicado.

## Limitações conhecidas (seja honesto nisso com quem aprova a publicação)

- As sondas cobrem padrões *conhecidos*. Um agente passar 100% das
  sondas não significa "seguro" — significa "resistente aos ataques que
  já catalogamos". Atualize `probes/*.yaml` continuamente.
- A detecção de "flagged" é por heurística de texto (palavras-chave,
  padrões), não por um segundo modelo avaliador. Pode haver falso
  negativo em respostas sutis. Ler as respostas brutas no relatório, não
  só o veredito.
- Não testa segurança da infraestrutura por trás do agente (isso é
  `modules/web` e `modules/cloud`).
