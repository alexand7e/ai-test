# Documentação do Projeto - AI Agent API

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Diagramas](#diagramas)
   - [Casos de Uso](#diagrama-de-casos-de-uso)
   - [Classes](#diagrama-de-classes)
   - [Sequência - Processamento de Mensagem](#diagrama-de-sequência)
   - [Componentes](#diagrama-de-componentes)
   - [Deploy](#diagrama-de-deploy)
4. [Estrutura do Projeto](#estrutura-do-projeto)
5. [Fluxos Principais](#fluxos-principais)
6. [Tecnologias Utilizadas](#tecnologias-utilizadas)

---

## Visão Geral

O **AI Agent API** é um sistema de agentes de IA conversacionais com suporte a RAG (Retrieval Augmented Generation), processamento assíncrono e webhooks. O sistema permite criar e gerenciar múltiplos agentes configuráveis via arquivos YAML/JSON, cada um com suas próprias características, modelos de IA, contextos RAG e ferramentas.

### Principais Características

- 🤖 **Agentes Configuráveis**: Cada agente é definido via arquivo YAML/JSON
- 🔍 **RAG (Retrieval Augmented Generation)**: Busca vetorial para enriquecer respostas com contexto
- ⚡ **Processamento Assíncrono**: Workers em background para processar mensagens
- 🔄 **Streaming**: Suporte a Server-Sent Events (SSE) para respostas em tempo real
- 🔌 **Webhooks**: Entrada e saída via webhooks para integração com sistemas externos
- 🛠️ **Tools/Functions**: Suporte a function calling para integração com APIs externas
- 📊 **Multi-canal**: Suporte a WhatsApp, Telegram, Slack e Web

---

## Arquitetura do Sistema

O sistema segue uma arquitetura em camadas com separação de responsabilidades:

```
┌─────────────────────────────────────────────────────────────┐
│                      Camada de Apresentação                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web UI     │  │  REST API    │  │   Webhooks   │      │
│  │  (Static)    │  │  (FastAPI)   │  │   (HTTP)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                      Camada de Domínio                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ AgentService │  │  RAGService  │  │ AgentLoader  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Camada de Infraestrutura                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ RedisClient  │  │OpenAIClient  │  │   Worker     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Serviços Externos                         │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │     Redis    │  │  OpenAI API  │                        │
│  │   (Stack)    │  │  (Compatible)│                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Diagramas

### Diagrama de Casos de Uso

```mermaid
graph TB
    Usuario[👤 Usuário] --> EnviarMensagem[Enviar Mensagem]
    SistemaExterno[🔌 Sistema Externo] --> Webhook[Enviar via Webhook]
    Admin[👨‍💼 Administrador] --> GerenciarAgentes[Gerenciar Agentes]
    Admin --> MonitorarSistema[Monitorar Sistema]
    
    EnviarMensagem --> ProcessarMensagem[Processar Mensagem]
    Webhook --> ProcessarMensagem
    
    ProcessarMensagem --> BuscarRAG[Buscar Contexto RAG]
    ProcessarMensagem --> ChamarIA[Chamar API de IA]
    ProcessarMensagem --> ExecutarTools[Executar Tools]
    
    BuscarRAG --> Redis[(Redis Vector Store)]
    ChamarIA --> OpenAI[OpenAI API]
    ExecutarTools --> APIExterna[APIs Externas]
    
    ProcessarMensagem --> RetornarResposta[Retornar Resposta]
    RetornarResposta --> Streaming[Streaming SSE]
    RetornarResposta --> WebhookSaida[Webhook de Saída]
    RetornarResposta --> PubSub[Pub/Sub Redis]
    
    GerenciarAgentes --> CriarAgente[Criar/Editar Agente]
    GerenciarAgentes --> RecarregarAgente[Recarregar Agente]
    GerenciarAgentes --> ListarAgentes[Listar Agentes]
    
    MonitorarSistema --> HealthCheck[Health Check]
    MonitorarSistema --> VerLogs[Ver Logs]
    MonitorarSistema --> VerMetricas[Ver Métricas]
    
    style Usuario fill:#e1f5ff
    style SistemaExterno fill:#e1f5ff
    style Admin fill:#ffe1f5
    style ProcessarMensagem fill:#fff4e1
    style Redis fill:#ffcccc
    style OpenAI fill:#ffcccc
```

### Diagrama de Classes

```mermaid
classDiagram
    class AgentConfig {
        +str id
        +str model
        +str system_prompt
        +dict input_schema
        +dict output_schema
        +AgentRAGConfig rag
        +List~AgentTool~ tools
        +str webhook_output_url
    }
    
    class AgentRAGConfig {
        +str type
        +str index_name
        +int top_k
    }
    
    class AgentTool {
        +str name
        +str type
        +str url
        +str description
        +dict parameters
    }
    
    class WebhookMessage {
        +str user_id
        +MessageChannel channel
        +str text
        +dict metadata
        +str conversation_id
    }
    
    class AgentResponse {
        +str agent_id
        +str conversation_id
        +str response
        +List~RAGContext~ contexts
        +int tokens_used
        +datetime created_at
    }
    
    class RAGContext {
        +str content
        +float score
        +dict metadata
    }
    
    class AgentLoader {
        -Path agents_dir
        -Dict~str,AgentConfig~ agents
        +get_agent(agent_id) AgentConfig
        +list_agents() Dict
        +reload()
        +reload_agent(agent_id) bool
    }
    
    class AgentService {
        -RedisClient redis
        -OpenAIClient openai
        -RAGService rag
        +process_message(agent, message, stream) AsyncIterator
        +process_message_sync(agent, message) AgentResponse
        -_prepare_tools(tools) List
    }
    
    class RAGService {
        -RedisClient redis
        -OpenAIClient openai
        +retrieve_context(query, agent_config) List~RAGContext~
        +build_rag_prompt(query, contexts, system_prompt) str
    }
    
    class RedisClient {
        -Redis client
        +connect()
        +disconnect()
        +ping() bool
        +get_cache(key) Any
        +set_cache(key, value, ttl)
        +enqueue_job(job_data) str
        +read_job(consumer_group, consumer_name) Dict
        +ack_job(msg_id)
        +publish(channel, message)
        +vector_search(index_name, query_vector, top_k) List
    }
    
    class OpenAIClient {
        -AsyncOpenAI client
        +get_embedding(text, model) List~float~
        +chat_completion_stream(messages, model, tools) AsyncIterator
        +chat_completion(messages, model, tools) Dict
    }
    
    class Worker {
        -AgentLoader agent_loader
        -RedisClient redis
        -OpenAIClient openai
        -RAGService rag_service
        -AgentService agent_service
        -bool running
        +start()
        +consume_loop(consumer_name)
        +process_job(job, consumer_name)
        +send_webhook_response(url, response)
    }
    
    AgentConfig --> AgentRAGConfig
    AgentConfig --> AgentTool
    AgentService --> AgentConfig
    AgentService --> WebhookMessage
    AgentService --> AgentResponse
    AgentService --> RAGService
    AgentService --> RedisClient
    AgentService --> OpenAIClient
    RAGService --> RAGContext
    RAGService --> RedisClient
    RAGService --> OpenAIClient
    AgentLoader --> AgentConfig
    Worker --> AgentLoader
    Worker --> AgentService
    Worker --> RedisClient
```

### Diagrama de Sequência

#### Processamento de Mensagem (Modo Assíncrono)

```mermaid
sequenceDiagram
    participant Cliente
    participant API as FastAPI
    participant Redis
    participant Worker
    participant RAG as RAGService
    participant OpenAI as OpenAIClient
    participant Webhook as Webhook Saída
    
    Cliente->>API: POST /webhooks/{agent_id}
    Note over Cliente,API: {text, user_id, channel, stream: false}
    
    API->>API: Validar agente
    API->>API: Normalizar mensagem
    API->>Redis: Enfileirar job (XADD)
    Redis-->>API: job_id
    API-->>Cliente: {status: "enqueued", job_id}
    
    Worker->>Redis: Ler job (XREADGROUP)
    Redis-->>Worker: job_data
    
    Worker->>Worker: Carregar AgentConfig
    Worker->>Worker: Parse WebhookMessage
    
    alt RAG configurado
        Worker->>RAG: retrieve_context(query, agent_config)
        RAG->>OpenAI: get_embedding(query)
        OpenAI-->>RAG: embedding vector
        RAG->>Redis: vector_search(index_name, query_vector)
        Redis-->>RAG: contexts[]
        RAG-->>Worker: List[RAGContext]
    end
    
    Worker->>Worker: Construir mensagens com histórico
    Worker->>Worker: Preparar tools (se houver)
    
    Worker->>OpenAI: chat_completion(messages, model, tools)
    OpenAI-->>Worker: response{content, tokens_used}
    
    Worker->>Worker: Criar AgentResponse
    
    alt Webhook de saída configurado
        Worker->>Webhook: POST response
        Webhook-->>Worker: 200 OK
    end
    
    Worker->>Redis: publish("agent_response:{agent_id}", response)
    Worker->>Redis: ACK job (XACK)
    
    Note over Worker,Redis: Job processado com sucesso
```

#### Processamento de Mensagem (Modo Streaming)

```mermaid
sequenceDiagram
    participant Cliente
    participant API as FastAPI
    participant RAG as RAGService
    participant OpenAI as OpenAIClient
    
    Cliente->>API: POST /webhooks/{agent_id}
    Note over Cliente,API: {text, user_id, channel, stream: true}
    
    API->>API: Validar agente
    API->>API: Normalizar mensagem
    
    alt RAG configurado
        API->>RAG: retrieve_context(query, agent_config)
        RAG->>OpenAI: get_embedding(query)
        OpenAI-->>RAG: embedding vector
        RAG->>Redis: vector_search(index_name, query_vector)
        Redis-->>RAG: contexts[]
        RAG-->>API: List[RAGContext]
    end
    
    API->>API: Construir mensagens com histórico
    API->>API: Preparar tools (se houver)
    
    API->>OpenAI: chat_completion_stream(messages, model, tools)
    
    loop Para cada token
        OpenAI-->>API: token
        API-->>Cliente: SSE: data: {token}
    end
    
    Note over Cliente,API: Resposta completa via streaming
```

### Diagrama de Componentes

```mermaid
graph TB
    subgraph "Camada de Apresentação"
        WebUI[Web UI<br/>Static Files]
        FastAPI[FastAPI Application<br/>REST API]
        WebhookEndpoint[Webhook Endpoints<br/>/webhooks/{agent_id}]
    end
    
    subgraph "Camada de Domínio"
        AgentService[AgentService<br/>Orquestração]
        RAGService[RAGService<br/>Retrieval Augmented Generation]
        AgentLoader[AgentLoader<br/>Carregamento de Agentes]
    end
    
    subgraph "Camada de Infraestrutura"
        RedisClient[RedisClient<br/>Cache, Queue, Pub/Sub, Vector]
        OpenAIClient[OpenAIClient<br/>Embeddings & Chat]
        Worker[Worker<br/>Processamento Assíncrono]
    end
    
    subgraph "Armazenamento"
        Redis[(Redis Stack<br/>Cache, Streams, Vector Store)]
        AgentsFS[Agents Directory<br/>YAML/JSON Files]
    end
    
    subgraph "Serviços Externos"
        OpenAIAPI[OpenAI Compatible API<br/>Qwen/Qwen2.5-3B-Instruct]
        ExternalAPIs[APIs Externas<br/>Tools/Functions]
        WebhookOut[Webhooks de Saída<br/>Sistemas Externos]
    end
    
    WebUI --> FastAPI
    FastAPI --> WebhookEndpoint
    WebhookEndpoint --> AgentService
    WebhookEndpoint --> RedisClient
    
    AgentService --> RAGService
    AgentService --> OpenAIClient
    AgentService --> AgentLoader
    AgentService --> RedisClient
    
    RAGService --> RedisClient
    RAGService --> OpenAIClient
    
    AgentLoader --> AgentsFS
    
    RedisClient --> Redis
    OpenAIClient --> OpenAIAPI
    
    Worker --> AgentService
    Worker --> RedisClient
    Worker --> WebhookOut
    
    AgentService -.->|Tools| ExternalAPIs
    
    style FastAPI fill:#4CAF50
    style AgentService fill:#2196F3
    style RAGService fill:#FF9800
    style Redis fill:#DC143C
    style OpenAIAPI fill:#9C27B0
```

### Diagrama de Deploy

```mermaid
graph TB
    subgraph "Docker Compose"
        subgraph "Container: api"
            FastAPIApp[FastAPI Application<br/>Port 8000]
            StaticFiles[Static Files<br/>/static]
        end
        
        subgraph "Container: worker"
            Worker1[Worker Process 1]
            Worker2[Worker Process 2]
            Worker3[Worker Process 3]
        end
        
        subgraph "Container: redis"
            RedisStack[Redis Stack Server<br/>Port 6379]
            RedisStreams[Redis Streams<br/>agent_stream]
            RedisVector[Vector Store<br/>RediSearch]
            RedisPubSub[Pub/Sub Channels]
        end
    end
    
    subgraph "External Services"
        OpenAIAPI[OpenAI Compatible API<br/>api.sobdemanda.mandu.piaui.pro]
        ExternalWebhooks[Webhooks Externos<br/>WhatsApp, Telegram, etc.]
    end
    
    subgraph "File System"
        AgentsDir[./agents/<br/>YAML/JSON Files]
        StaticDir[./static/<br/>HTML/CSS/JS]
    end
    
    FastAPIApp --> RedisStack
    FastAPIApp --> AgentsDir
    FastAPIApp --> StaticFiles
    StaticFiles --> StaticDir
    
    Worker1 --> RedisStack
    Worker2 --> RedisStack
    Worker3 --> RedisStack
    Worker1 --> AgentsDir
    Worker2 --> AgentsDir
    Worker3 --> AgentsDir
    
    FastAPIApp --> OpenAIAPI
    Worker1 --> OpenAIAPI
    Worker2 --> OpenAIAPI
    Worker3 --> OpenAIAPI
    
    FastAPIApp -.->|Webhook In| ExternalWebhooks
    Worker1 -.->|Webhook Out| ExternalWebhooks
    Worker2 -.->|Webhook Out| ExternalWebhooks
    Worker3 -.->|Webhook Out| ExternalWebhooks
    
    RedisStack --> RedisStreams
    RedisStack --> RedisVector
    RedisStack --> RedisPubSub
    
    style FastAPIApp fill:#4CAF50
    style Worker1 fill:#2196F3
    style Worker2 fill:#2196F3
    style Worker3 fill:#2196F3
    style RedisStack fill:#DC143C
    style OpenAIAPI fill:#9C27B0
```

---

## Estrutura do Projeto

```
ai-test/
├── app/                          # Código da aplicação
│   ├── __init__.py
│   ├── main.py                   # FastAPI application e endpoints
│   ├── worker.py                 # Worker assíncrono para processar jobs
│   ├── config.py                 # Configurações (Settings)
│   ├── models.py                 # Modelos Pydantic
│   ├── agent_loader.py           # Carregador de agentes YAML/JSON
│   │
│   ├── domain/                   # Camada de domínio (lógica de negócio)
│   │   ├── __init__.py
│   │   ├── agent_service.py      # Serviço de orquestração de agentes
│   │   └── rag_service.py         # Serviço de RAG
│   │
│   └── infrastructure/           # Camada de infraestrutura
│       ├── __init__.py
│       ├── redis_client.py        # Cliente Redis (cache, queue, pub/sub, vector)
│       └── openai_client.py       # Cliente OpenAI (embeddings, chat)
│
├── agents/                       # Configurações de agentes
│   ├── chatbot_simples.yaml      # Agente simples de exemplo
│   ├── faq_educacao.yaml         # Agente especializado em educação
│   └── README.md
│
├── static/                       # Arquivos estáticos (UI web)
│   ├── index.html
│   ├── script.js
│   └── styles.css
│
├── docker-compose.yml            # Orquestração de containers
├── Dockerfile                    # Imagem Docker da aplicação
├── requirements.txt              # Dependências Python
├── env.example                   # Exemplo de variáveis de ambiente
├── README.md                     # Documentação básica
└── DOCUMENTACAO.md               # Esta documentação
```

---

## Fluxos Principais

### 1. Fluxo de Criação e Carregamento de Agente

```mermaid
flowchart TD
    A[Administrador cria arquivo YAML] --> B[Arquivo salvo em agents/]
    B --> C{API iniciada?}
    C -->|Não| D[AgentLoader carrega na inicialização]
    C -->|Sim| E[POST /agents/reload]
    E --> D
    D --> F[AgentLoader lê arquivo YAML]
    F --> G[Valida e cria AgentConfig]
    G --> H[Armazena em memória]
    H --> I[Agente disponível em /webhooks/{agent_id}]
```

### 2. Fluxo de Processamento RAG

```mermaid
flowchart TD
    A[Mensagem recebida] --> B{Agente tem RAG?}
    B -->|Não| C[Pula RAG]
    B -->|Sim| D[RAGService.retrieve_context]
    D --> E[OpenAIClient.get_embedding]
    E --> F[Gera embedding da query]
    F --> G[RedisClient.vector_search]
    G --> H[Busca vetorial no índice]
    H --> I[Retorna top_k contextos]
    I --> J[Constrói prompt com contextos]
    J --> K[Envia para API de IA]
    C --> K
```

### 3. Fluxo de Processamento com Tools

```mermaid
flowchart TD
    A[Mensagem recebida] --> B{Agente tem tools?}
    B -->|Não| C[Processa sem tools]
    B -->|Sim| D[Prepara tools para function calling]
    D --> E[Chama API de IA com tools]
    E --> F{IA solicita tool?}
    F -->|Não| G[Retorna resposta]
    F -->|Sim| H[Executa tool HTTP]
    H --> I[Retorna resultado para IA]
    I --> E
    C --> G
```

---

## Tecnologias Utilizadas

### Backend

- **Python 3.11+**: Linguagem principal
- **FastAPI**: Framework web assíncrono para API REST
- **Uvicorn**: Servidor ASGI de alta performance
- **Pydantic**: Validação de dados e modelos
- **Redis (asyncio)**: Cliente assíncrono para Redis
- **OpenAI SDK**: Cliente para APIs compatíveis com OpenAI
- **PyYAML**: Parser para arquivos YAML
- **httpx**: Cliente HTTP assíncrono

### Infraestrutura

- **Docker & Docker Compose**: Containerização e orquestração
- **Redis Stack**: Cache, filas (Streams), busca vetorial (RediSearch)
- **Nginx** (opcional): Reverse proxy e load balancing

### APIs e Serviços

- **OpenAI Compatible API**: API proprietária compatível com OpenAI
  - Modelo: `Qwen/Qwen2.5-3B-Instruct`
  - Base URL: `https://api.sobdemanda.mandu.piaui.pro/v1`
  - Suporta: embeddings, chat completions, streaming

### Padrões e Arquitetura

- **Arquitetura em Camadas**: Separação entre apresentação, domínio e infraestrutura
- **Clean Architecture**: Princípios SOLID e separação de responsabilidades
- **Async/Await**: Programação assíncrona para alta concorrência
- **Event-Driven**: Pub/Sub para comunicação entre componentes
- **Queue-Based**: Processamento assíncrono via Redis Streams

---

## Configuração de Agentes

### Estrutura de um Agente YAML

```yaml
id: identificador_unico
model: Qwen/Qwen2.5-3B-Instruct
system_prompt: |
  Instruções do sistema para o agente

input_schema:
  type: object
  properties:
    question:
      type: string
      description: Pergunta do usuário

output_schema:
  type: object
  properties:
    answer:
      type: string
      description: Resposta do agente

rag:
  type: redis
  index_name: nome_do_indice
  top_k: 5

tools:
  - name: nome_da_ferramenta
    type: http
    url: https://api.exemplo.com/endpoint
    description: Descrição da ferramenta
    parameters:
      type: object
      properties:
        parametro1:
          type: string
      required:
        - parametro1

webhook_output_url: https://webhook.exemplo.com/callback
```

### Campos do Agente

- **id**: Identificador único do agente (obrigatório)
- **model**: Modelo de IA a ser usado (padrão: Qwen/Qwen2.5-3B-Instruct)
- **system_prompt**: Instruções do sistema para o agente
- **input_schema**: Schema JSON Schema para validação de entrada
- **output_schema**: Schema JSON Schema para validação de saída
- **rag**: Configuração de RAG (opcional)
  - **type**: Tipo de RAG (atualmente apenas "redis")
  - **index_name**: Nome do índice vetorial no Redis
  - **top_k**: Número de contextos a recuperar
- **tools**: Lista de ferramentas disponíveis (opcional)
- **webhook_output_url**: URL para enviar respostas (opcional)

---

## Endpoints da API

### Health Check
```
GET /health
```
Retorna status do sistema e conexões.

### Listar Agentes
```
GET /agents
```
Lista todos os agentes configurados.

### Obter Agente
```
GET /agents/{agent_id}
```
Retorna configuração completa de um agente.

### Recarregar Agentes
```
POST /agents/reload
POST /agents/{agent_id}/reload
```
Recarrega todos os agentes ou um agente específico.

### Webhook de Entrada
```
POST /webhooks/{agent_id}
Content-Type: application/json

{
  "user_id": "user123",
  "channel": "whatsapp",
  "text": "Mensagem do usuário",
  "conversation_id": "conv123",
  "history": [
    {"role": "user", "content": "Mensagem anterior"},
    {"role": "assistant", "content": "Resposta anterior"}
  ],
  "stream": false,
  "metadata": {}
}
```

**Parâmetros:**
- `user_id`: Identificador do usuário (obrigatório)
- `channel`: Canal de comunicação (whatsapp, telegram, slack, web)
- `text`: Texto da mensagem (obrigatório)
- `conversation_id`: ID da conversa (opcional, gerado automaticamente se não fornecido)
- `history`: Histórico de mensagens anteriores (opcional)
- `stream`: Se `true`, retorna resposta via SSE (opcional, padrão: false)
- `metadata`: Metadados adicionais (opcional)

**Resposta (stream: false):**
```json
{
  "status": "enqueued",
  "job_id": "uuid-do-job",
  "agent_id": "identificador"
}
```

**Resposta (stream: true):**
Server-Sent Events (SSE) com tokens da resposta em tempo real.

---

## Processamento Assíncrono

O sistema utiliza **Redis Streams** para processamento assíncrono de mensagens:

1. **Enfileiramento**: API enfileira job no Redis Stream
2. **Consumo**: Workers consomem jobs usando Consumer Groups
3. **Processamento**: Worker processa mensagem com agente
4. **Resposta**: Worker envia resposta via webhook ou pub/sub
5. **ACK**: Worker confirma processamento (XACK)

### Vantagens

- **Escalabilidade**: Múltiplos workers podem processar em paralelo
- **Resiliência**: Jobs não são perdidos se worker falhar
- **Performance**: API responde rapidamente sem bloquear
- **Balanceamento**: Redis distribui jobs entre workers

---

## RAG (Retrieval Augmented Generation)

O sistema implementa RAG para enriquecer respostas com contexto relevante:

1. **Embedding**: Gera embedding vetorial da query do usuário
2. **Busca Vetorial**: Busca documentos similares no Redis Vector Store
3. **Contexto**: Monta prompt com contextos encontrados
4. **Geração**: IA gera resposta baseada no contexto

### Configuração

1. Configure `rag` no YAML do agente
2. Popule o índice vetorial no Redis (processo externo)
3. O sistema automaticamente usa RAG quando configurado

---

## Monitoramento e Observabilidade

### Logs

O sistema gera logs estruturados com:
- Timestamp
- Nível (INFO, WARNING, ERROR)
- Componente
- Mensagem
- Contexto (agent_id, conversation_id, etc.)

### Health Check

Endpoint `/health` retorna:
- Status geral do sistema
- Status da conexão Redis
- Número de agentes carregados

### Pub/Sub

Respostas são publicadas no canal Redis:
```
agent_response:{agent_id}
```

Permite monitoramento em tempo real de respostas.

---

## Desenvolvimento

### Adicionar Novo Agente

1. Crie arquivo YAML em `agents/`
2. Execute `POST /agents/reload` ou reinicie a API
3. Agente estará disponível em `/webhooks/{agent_id}`

### Modificar Código

O código está organizado em camadas:
- **Infrastructure**: Clientes externos (Redis, OpenAI)
- **Domain**: Lógica de negócio (RAG, agentes)
- **API**: Endpoints HTTP (FastAPI)
- **Worker**: Processamento assíncrono

### Testes

```bash
# Teste local
python -m pytest

# Teste com Docker
docker-compose up --build
```

---

## Próximos Passos

- [ ] Implementação completa de busca vetorial no Redis
- [ ] Sistema de retry para jobs falhos
- [ ] Métricas e monitoramento (Prometheus/Grafana)
- [ ] Autenticação de webhooks
- [ ] Suporte a múltiplos canais (WhatsApp, Telegram, etc.)
- [ ] UI para gerenciar agentes
- [ ] Testes automatizados
- [ ] Documentação OpenAPI/Swagger
- [ ] Rate limiting
- [ ] Cache de respostas

---

## Licença

MIT

---

**Documentação gerada em:** 2024  
**Versão do Sistema:** 1.0.0

