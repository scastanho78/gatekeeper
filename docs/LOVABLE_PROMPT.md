# Prompt para o Lovable

Cole o texto abaixo no Lovable pra gerar o frontend. Ele descreve as
telas e manda o Lovable **consumir a API já existente**, em vez de
inventar lógica de autorização do zero.

Antes de colar: suba a API (`uvicorn api.main:app --port 8000`) e
exponha publicamente (ex: `ngrok http 8000`, ou publique num servidor)
— o Lovable não alcança `localhost` da sua máquina. Troque a URL abaixo
pela URL real antes de colar.

---

```
Crie um dashboard de segurança chamado "GateKeeper" — uma plataforma
interna de testes de segurança organizada em agentes especializados
(um agente por frente de teste: IA/LLM, API, Cloud, Rede, Mobile).

Toda a lógica de negócio já existe numa API backend em
https://SUA-URL-AQUI/docs — consuma os endpoints reais dela, não
invente dados nem lógica de autorização no frontend. Em especial:
nunca decida no frontend se uma ação é permitida — sempre chame
POST /api/agents/{nome}/run e trate a resposta (200 = rodou, 403 =
bloqueado, mostrando a mensagem de erro retornada).

## Identidade visual
- Nome: GateKeeper
- Ícone: escudo (🛡️)
- Tom: ferramenta de segurança corporativa, séria mas não assustadora.
  Paleta escura, com um verde ou azul de "status seguro" para estados
  liberados e vermelho/laranja para bloqueado ou sinalizado.
- Público: CISO e equipe de segurança interna de uma empresa, não é
  produto público.

## Navegação — abas no topo
1. Início
2. Configuração
3. GateKeeper AI
4. GateKeeper API (placeholder)
5. GateKeeper Cloud (placeholder)
6. GateKeeper Network (placeholder)
7. GateKeeper Mobile (placeholder)

## Aba "Início"
Busca GET /api/roadmap e renderiza uma tabela/cards com os 5 agentes,
ícone, descrição e status (badge verde "Funcional" ou cinza
"Planejado — Fase N"). Texto de intro: "Cada aba é um agente
especializado numa frente de teste de segurança. Antes de publicar
algo, rode o agente correspondente e decida com base no relatório."

## Aba "Configuração"
Esta é a tela mais importante — é o guardrail.

1. Busca GET /api/status e mostra 3 cards de status: arquivo de
   escopo existe (sim/não), autorização ROE válida (✅/🚫), dentro da
   janela de teste agora (informativo).
2. Formulário de Autorização (ROE): campos aprovador, documento de
   referência, válido de / até (datas). Salva com PUT /api/authorization.
3. Formulário de Janela de Teste: dias da semana (multi-seleção),
   hora início/fim, fuso horário. Salva com PUT /api/active-window.
4. Lista de agentes cadastrados: GET /api/agents, tabela com nome/
   ambiente/endpoint, botão remover (DELETE /api/agents/{name}).
5. Formulário "Cadastrar novo agente": nome, ambiente (staging/teste,
   desenvolvimento, produção — avisar com destaque se for produção),
   formato de resposta (simples ou OpenAI chat completions), endpoint
   (URL), chave de API (campo senha), e se formato simples, nome do
   campo de texto na resposta JSON. Salva com POST /api/agents. Avise
   visivelmente: "a chave de API fica salva em texto simples no
   backend — não é um cofre de segredos."
6. Trilha de auditoria: GET /api/audit, tabela com timestamp, tipo de
   evento, agente, resultado (permitido/bloqueado e motivo, ou
   resumo da execução).

## Aba "GateKeeper AI"
1. Seletor de agente cadastrado (GET /api/agents).
2. Ao selecionar um agente, mostrar ambiente e endpoint; se ambiente
   for "produção", avisar com destaque visual forte.
3. Seção "Consultar prompts de teste": GET /api/probes, com busca por
   texto e filtro por categoria (OWASP LLM Top 10: LLM01, LLM02, LLM04,
   LLM06, LLM07, LLM08, jailbreak). Cada item expande mostrando o
   prompt completo.
4. Botão "Rodar teste de verdade": chama POST /api/agents/{nome}/run.
   - Se vier 403: mostra um alerta vermelho com a mensagem de erro
     (motivo do bloqueio pelo guardrail) — não deixa prosseguir.
   - Se vier 200: mostra métricas (total de testes, quantos
     sinalizados, quantos ok), lista expansível dos sinalizados
     (prompt enviado, resposta do agente, motivo da sinalização), e
     um botão de download do campo `report_markdown` como arquivo .md.
5. Botão de download do checklist manual: GET /api/checklist, baixa
   como .md.
6. Texto de aviso fixo no topo da aba: "Passar todos os testes não
   significa que o agente é seguro — significa que resistiu aos
   ataques já catalogados. Leia as respostas, não só o veredito."

## Abas "GateKeeper API / Cloud / Network / Mobile"
Placeholder simples: ícone grande, "Ainda não implementado — Fase N
do roadmap", e uma descrição curta de uma frase do que vai testar.
Não simule funcionalidade que não existe.

## Importante
- Todo texto da interface em português do Brasil.
- Nunca implemente lógica de "pode rodar ou não" no frontend — isso
  sempre vem da resposta da API (200 vs 403).
- Trate erros de rede/API de forma visível (toast ou banner), nunca
  silenciosamente.
```

---

## Depois que o Lovable gerar o frontend

1. Rode a API de verdade e configure a URL base no Lovable (ele
   normalmente pede uma env var tipo `VITE_API_URL`).
2. Teste o fluxo completo: cadastrar ROE, cadastrar um agente de
   teste, tentar rodar sem ROE válido (deve dar 403 visível na tela),
   preencher ROE, rodar de novo (deve funcionar).
3. Se o Lovable sugerir usar Supabase pra guardar os dados em vez de
   chamar a API Python, **recuse** — isso reintroduziria a lógica de
   autorização fora do `core/guardrails.py` já validado.
