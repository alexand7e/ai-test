# Script PowerShell para resetar métricas no Redis
# Uso: .\scripts\reset_metrics.ps1 [agent_id]

param(
    [string]$AgentId = ""
)

Write-Host "Resetando métricas..." -ForegroundColor Yellow

if ([string]::IsNullOrEmpty($AgentId)) {
    Write-Host "Resetando TODAS as métricas..." -ForegroundColor Yellow
    docker exec ai-agent-redis redis-cli --eval - <<EOF
local keys = redis.call('keys', 'metrics:*')
for i=1,#keys do
    redis.call('del', keys[i])
end
return #keys
EOF
    Write-Host "Todas as métricas foram resetadas." -ForegroundColor Green
} else {
    Write-Host "Resetando métricas do agente: $AgentId" -ForegroundColor Yellow
    docker exec ai-agent-redis redis-cli --eval - <<EOF
local agent_id = ARGV[1]
local keys = redis.call('keys', 'metrics:agent:' .. agent_id .. ':*')
for i=1,#keys do
    redis.call('del', keys[i])
end
return #keys
EOF
    Write-Host "Métricas do agente $AgentId foram resetadas." -ForegroundColor Green
}

Write-Host "Pronto! Envie novas mensagens para ver métricas atualizadas." -ForegroundColor Green

