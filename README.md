# AI Agent API

Sistema de agentes de IA com RAG (Retrieval Augmented Generation), webhooks e processamento assíncrono usando FastAPI, OpenAI e Redis.

## Arquitetura

- **FastAPI (ASGI)**: API HTTP assíncrona para receber webhooks e gerenciar agentes
- **Workers assíncronos**: Processam jobs em background consumindo filas Redis
- **Redis Stack**: Cache, fila de jobs (Streams) e armazenamento vetorial
- **API de IA** (compatível com OpenAI): Embeddings e completions de chat com streaming usando Qwen/Qwen2.5-3B-Instruct
- **Agentes como configuração**: Cada agente é definido via arquivo YAML/JSON

## Estrutura do Projeto

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── worker.py            # Worker assíncrono
│   ├── config.py            # Configurações
│   ├── models.py            # Modelos Pydantic
│   ├── agent_loader.py      # Carregador de agentes
│   ├── domain/              # Camada de domínio
│   │   ├── agent_service.py
│   │   └── rag_service.py
│   └── infrastructure/      # Camada de infraestrutura
│       ├── redis_client.py
│       └── openai_client.py
├── agents/                  # Configurações de agentes (YAML/JSON)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Pré-requisitos

- Docker e Docker Compose
- Python 3.11+ (para desenvolvimento local)
- Chave da API (compatível com OpenAI)

## Configuração

1. **Clone o repositório**

2. **Configure variáveis de ambiente**

Copie `env.example` para `.env` e configure:

```bash
cp env.example .env
```

Edite `.env` (já vem pré-configurado para a API proprietária):
```env
OPENAI_API_KEY=sk-7dsNTpHKhBOzoJTDAo3Nsw
OPENAI_BASE_URL=https://api.sobdemanda.mandu.piaui.pro/v1
REDIS_HOST=redis
REDIS_PORT=6379
```

**Nota**: A aplicação está configurada para usar uma API proprietária compatível com OpenAI, rodando em `https://api.sobdemanda.mandu.piaui.pro` com o modelo `Qwen/Qwen2.5-3B-Instruct`.

3. **Crie agentes**

Os agentes são definidos como arquivos YAML ou JSON na pasta `agents/`. Veja exemplos em `agents/faq_educacao.yaml`.

## Execução

### Com Docker Compose (Recomendado)

```bash
docker-compose up --build
```

Isso inicia:
- **API**: http://localhost:8000
- **Redis**: localhost:6379
- **Worker**: Processa jobs em background

### Desenvolvimento Local

1. Instale dependências:
```bash
pip install -r requirements.txt
```

2. Inicie Redis (ou use Docker):
```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

3. Configure `.env` com as variáveis de ambiente

4. Inicie a API:
```bash
uvicorn app.main:app --reload
```

5. Em outro terminal, inicie o worker:
```bash
python -m app.worker
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Listar Agentes
```bash
GET /agents
```

### Obter Agente
```bash
GET /agents/{agent_id}
```

### Recarregar Agentes
```bash
POST /agents/reload
POST /agents/{agent_id}/reload
```

### Webhook de Entrada
```bash
POST /webhooks/{agent_id}
Content-Type: application/json

{
  "user_id": "user123",
  "channel": "whatsapp",
  "text": "Qual o calendário escolar?",
  "conversation_id": "conv123",
  "stream": false  # true para streaming via SSE
}
```

Com `stream: true`, a resposta é enviada via Server-Sent Events (SSE).

## Configuração de Agentes

Cada agente é um arquivo YAML/JSON na pasta `agents/`:

```yaml
id: meu_agente
model: Qwen/Qwen2.5-3B-Instruct
system_prompt: |
  Você é um assistente especializado em...

input_schema:
  type: object
  properties:
    question:
      type: string

output_schema:
  type: object
  properties:
    answer:
      type: string

rag:
  type: redis
  index_name: minha_colecao
  top_k: 5

tools:
  - name: minha_ferramenta
    type: http
    url: https://api.exemplo.com
    description: Descrição da ferramenta

webhook_output_url: null  # URL para enviar respostas
```

## Fluxo de Processamento

1. **Webhook recebe mensagem** → Valida e normaliza
2. **Enfileira job no Redis** (se não for streaming)
3. **Worker consome job** → Carrega config do agente
4. **Pipeline RAG**:
   - Gera embedding da query
   - Busca vetorial no Redis
   - Monta prompt com contextos
5. **Chama API de IA** → Gera resposta usando Qwen/Qwen2.5-3B-Instruct
6. **Envia resposta**:
   - Via webhook de saída (se configurado)
   - Via pub/sub Redis
   - Via SSE (se streaming)

## RAG (Retrieval Augmented Generation)

O sistema suporta RAG usando Redis Stack com busca vetorial. Para usar:

1. Configure `rag` no YAML do agente ou via interface web
2. Certifique-se de que Redis Stack está rodando
3. Popule o índice vetorial usando `POST /rag/{index_name}/documents`

**Nota**: A implementação de busca vetorial está simplificada. Para produção, implemente completamente usando RediSearch ou outro store vetorial.

## Análise de Dados

O sistema suporta análise de dados usando pandas. Agentes podem ter arquivos CSV, JSON ou XLSX carregados e executar queries pandas nesses dados.

**Funcionalidades:**
- Upload de arquivos via interface web ou API
- Queries pandas executadas automaticamente quando o LLM chama a tool `query_data`
- Suporte a métodos comuns: head(), tail(), describe(), query(), filtros, etc.
- Teste de queries via `POST /agents/{agent_id}/data/query`

**Exemplos de queries:**
- `head(10)` - Primeiras 10 linhas
- `describe()` - Estatísticas descritivas
- `query("coluna > 10")` - Filtrar dados
- `df[df['coluna'] == 'valor']` - Filtro avançado

## Observabilidade

- Logs estruturados com `conversation_id` e `agent_id`
- Health check endpoint
- Pub/sub para monitoramento de respostas

## Desenvolvimento

### Criar Novo Agente

**Via Interface Web:**
1. Acesse `/create-agent` no navegador
2. Preencha o formulário com as informações do agente
3. Configure RAG (base de conhecimento) se necessário
4. Habilite análise de dados e faça upload de arquivos (CSV, JSON, XLSX)
5. O agente será salvo automaticamente e estará disponível em `/webhooks/{agent_id}` ou `/webhook/{webhook_name}`

**Via API:**
1. Envie `POST /agents/create` com os dados do agente
2. Faça upload de arquivos via `POST /agents/{agent_id}/files` se necessário
3. Execute `POST /agents/reload` ou reinicie a API
4. Agente estará disponível em `/webhooks/{agent_id}`

**Via Arquivo YAML:**
1. Crie arquivo YAML em `agents/`
2. Execute `POST /agents/reload` ou reinicie a API
3. Agente estará disponível em `/webhooks/{agent_id}`

### Modificar Código

O código está organizado em camadas:
- **Infrastructure**: Redis, OpenAI clients
- **Domain**: Lógica de negócio (RAG, agentes)
- **API**: Endpoints HTTP
- **Worker**: Processamento assíncrono

## Troubleshooting

### Redis não conecta
- Verifique se Redis está rodando: `docker ps`
- Verifique variáveis `REDIS_HOST` e `REDIS_PORT`

### Agente não encontrado
- Verifique se arquivo YAML está em `agents/`
- Verifique sintaxe YAML
- Execute `POST /agents/reload`

### Worker não processa jobs
- Verifique logs do worker
- Verifique conexão Redis
- Verifique se jobs estão sendo enfileirados

## Próximos Passos

- [ ] Implementação completa de busca vetorial no Redis
- [ ] Sistema de retry para jobs falhos
- [ ] Métricas e monitoramento (Prometheus)
- [ ] Autenticação de webhooks
- [ ] Suporte a múltiplos canais (WhatsApp, Telegram, etc.)
- [ ] UI para gerenciar agentes

## Licença

MIT

