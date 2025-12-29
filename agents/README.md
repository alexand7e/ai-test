# Diretório de Agentes

Este diretório contém as configurações dos agentes em formato YAML ou JSON.

## Formato

Cada arquivo deve seguir o schema:

```yaml
id: identificador_unico
model: gpt-4o-mini
system_prompt: |
  Prompt do sistema para o agente

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
  index_name: nome_do_indice
  top_k: 5

tools:
  - name: nome_ferramenta
    type: http
    url: https://api.exemplo.com
    description: Descrição

webhook_output_url: null
```

## Exemplos

- `faq_educacao.yaml`: Agente especializado em políticas educacionais
- `chatbot_simples.yaml`: Chatbot genérico simples

## Reload

Após modificar um agente, execute:

```bash
curl -X POST http://localhost:8000/agents/reload
```

Ou reinicie a aplicação.

