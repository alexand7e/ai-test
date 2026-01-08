#!/bin/bash
# Script para resetar métricas no Redis
# Uso: ./scripts/reset_metrics.sh [agent_id]

AGENT_ID=${1:-""}

echo "Resetando métricas..."

if [ -z "$AGENT_ID" ]; then
    echo "Resetando TODAS as métricas..."
    docker exec -it ai-agent-redis redis-cli --eval - <<EOF
local keys = redis.call('keys', 'metrics:*')
for i=1,#keys do
    redis.call('del', keys[i])
end
return #keys
EOF
    echo "Todas as métricas foram resetadas."
else
    echo "Resetando métricas do agente: $AGENT_ID"
    docker exec -it ai-agent-redis redis-cli --eval - <<EOF
local agent_id = ARGV[1]
local keys = redis.call('keys', 'metrics:agent:' .. agent_id .. ':*')
for i=1,#keys do
    redis.call('del', keys[i])
end
return #keys
EOF
    echo "Métricas do agente $AGENT_ID foram resetadas."
fi

echo "Pronto! Envie novas mensagens para ver métricas atualizadas."

