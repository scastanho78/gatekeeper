# GateKeeper API

API HTTP (FastAPI) que expõe a lógica Python já validada (guardrails,
cadastro de agentes, execução de teste, relatório, auditoria) pra
qualquer frontend consumir — incluindo um gerado no Lovable.

**Princípio importante**: o frontend nunca decide sozinho se uma
execução é permitida. Ele chama `POST /api/agents/{nome}/run` e recebe
`200` (rodou, com resultados) ou `403` (bloqueado, com o motivo exato).
Toda a lógica de "pode ou não pode" continua em `core/guardrails.py` —
reimplementar isso no frontend reintroduziria o mesmo bug que corrigimos
antes (guardrail virar decoração).

## Rodar localmente

```bash
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000
```

Documentação interativa (Swagger) em `http://localhost:8000/docs` —
útil pra testar os endpoints na mão antes de plugar o Lovable.

## Endpoints

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/status` | Resumo do guardrail: scope.yaml existe? ROE válido? dentro da janela? quantos agentes cadastrados? |
| GET | `/api/roadmap` | Lista estática dos 5 agentes e status (pra tela Início) |
| GET | `/api/authorization` | Autorização (ROE) atual |
| PUT | `/api/authorization` | Salva ROE (aprovador, validade) |
| GET | `/api/active-window` | Janela de teste ativo atual |
| PUT | `/api/active-window` | Salva janela de teste |
| GET | `/api/agents` | Lista agentes de IA cadastrados |
| POST | `/api/agents` | Cadastra/atualiza um agente |
| DELETE | `/api/agents/{name}` | Remove um agente |
| GET | `/api/probes` | Lista as sondas de teste (prompt, categoria, id) — pra tela de consulta |
| POST | `/api/agents/{name}/run` | **Executa o teste de verdade.** Passa pelo guardrail primeiro; 403 se bloqueado. Retorna resultados + relatório em markdown. |
| GET | `/api/checklist` | Markdown do checklist manual (LLM03/05/09/10) |
| GET | `/api/audit` | Últimos eventos da trilha de auditoria |

## Antes de colocar em produção

- **CORS está aberto (`allow_origins=["*"]`)** em `api/main.py` — serve
  pra desenvolvimento com o preview do Lovable, mas restrinja ao domínio
  real do frontend antes de expor publicamente.
- **Não há autenticação nesta API.** Qualquer um que alcançar a porta
  consegue cadastrar agente, ver chave de API salva, rodar teste. Pra
  uso além de "só eu, na minha máquina", isso precisa de auth (API key
  simples já resolveria o básico) antes de expor fora de localhost.
- As chaves de API dos agentes continuam em texto simples em
  `config/scope.yaml`, igual no fluxo da tela Streamlit — mesma
  ressalva de antes, não é cofre de segredos.
