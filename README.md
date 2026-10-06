# Pentester — Agente interno de testes de segurança

Plataforma para orquestrar testes de segurança **internos e autorizados**
(web/API, cloud, rede/AD, mobile e IA/LLM), reduzindo a dependência de
consultorias externas. Mantida pelo CISO da empresa.

> ⚠️ Isto não é uma ferramenta de "hacking automático". É um orquestrador
> de testes com **guardrails obrigatórios**: nenhuma ação ativa roda contra
> um alvo que não esteja explicitamente listado em `config/scope.yaml`,
> dentro da janela de teste autorizada.

## Por que existe

A partir de 2027 a empresa não terá orçamento para pentest externo
recorrente. Este projeto automatiza o que pode ser automatizado com
segurança (recon, varredura de configuração, SAST/SCA, varredura de rede
e web autorizada, testes de robustez de LLM) e organiza o fluxo de
decisão humana para o que não pode (exploração ativa, engenharia social,
red team completo).

## Estrutura

```
config/            Escopo autorizado, janelas de teste, exclusões
core/               Guardrails, orquestrador, modelo de scope
docs/
  ROE_TEMPLATE.md   Modelo de Regras de Engajamento / autorização formal
  ROADMAP.md        Fases de implementação e status de cada módulo
modules/
  recon/            Reconhecimento passivo/ativo de superfície
  web/              Testes OWASP Top 10 / API Security Top 10 (Fase 1 — ativo)
  cloud/            Postura de configuração AWS/Azure/GCP (Fase 2)
  network/          Varredura de rede interna e AD (Fase 3)
  mobile/           OWASP MASVS / MASTG (Fase 4)
  ai_llm/           OWASP Top 10 for LLM Applications (Fase 5)
  reporting/        Geração de relatório consolidado
```

## Modo tela (recomendado se você não usa linha de comando)

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

Isso abre uma aba no navegador em `http://localhost:8501` com um
formulário: nome do agente, endereço (URL), chave de API e um botão
"Rodar teste de verdade". Não precisa editar nenhum arquivo YAML nem
usar terminal para o teste em si.

## Pré-requisitos antes de usar em qualquer alvo real

1. `config/scope.yaml` preenchido e revisado — todo alvo fora dele é
   bloqueado pelo guardrail (`core/guardrails.py`).
2. Documento de autorização assinado (ver `docs/ROE_TEMPLATE.md`) com
   escopo, janela de execução e contato de emergência.
3. Nenhum módulo de varredura **ativa** roda sem o CISO (ou quem ele
   delegar) confirmar execução manualmente (`--confirm`).

## Status

Ver `docs/ROADMAP.md` para o que está implementado vs. planejado.
