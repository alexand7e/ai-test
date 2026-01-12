const API_BASE_URL = (window.SIAUtils && window.SIAUtils.getApiBaseUrl)
    ? window.SIAUtils.getApiBaseUrl()
    : (window.location && window.location.origin ? window.location.origin : 'http://localhost:8000');

// Elementos DOM
const refreshBtn = document.getElementById('refresh-btn');
const agentsGrid = document.getElementById('agents-grid');
const globalMetrics = document.getElementById('global-metrics');
const ragIndexSelect = document.getElementById('rag-index-select');
const refreshRagBtn = document.getElementById('refresh-rag-btn');
const addDocBtn = document.getElementById('add-doc-btn');
const uploadFileBtn = document.getElementById('upload-file-btn');
const ragSearchQuery = document.getElementById('rag-search-query');
const ragSearchTopK = document.getElementById('rag-search-topk');
const ragSearchBtn = document.getElementById('rag-search-btn');
const ragStats = document.getElementById('rag-stats');
const ragDocuments = document.getElementById('rag-documents');
const docModal = document.getElementById('doc-modal');
const docForm = document.getElementById('doc-form');
const closeDocModal = document.querySelector('#doc-modal .close');
const fileModal = document.getElementById('file-modal');
const fileForm = document.getElementById('file-form');
const closeFileModal = document.getElementById('file-modal-close');

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    loadGlobalMetrics();
    loadAgents();
    loadRAGIndexes();
    setupEventListeners();
});

function setupEventListeners() {
    refreshBtn.addEventListener('click', () => {
        loadGlobalMetrics();
        loadAgents();
    });
    
    refreshRagBtn.addEventListener('click', () => {
        loadRAGIndexes();
    });
    
    addDocBtn.addEventListener('click', () => {
        docModal.style.display = 'block';
    });

    uploadFileBtn.addEventListener('click', () => {
        fileModal.style.display = 'block';
    });
    
    closeDocModal.addEventListener('click', () => {
        docModal.style.display = 'none';
    });

    closeFileModal.addEventListener('click', () => {
        fileModal.style.display = 'none';
    });
    
    window.addEventListener('click', (e) => {
        if (e.target === docModal) {
            docModal.style.display = 'none';
        }
        if (e.target === fileModal) {
            fileModal.style.display = 'none';
        }
    });
    
    ragIndexSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            loadRAGDocuments(e.target.value);
            loadRAGStats(e.target.value);
        }
    });

    ragSearchBtn.addEventListener('click', async () => {
        const indexName = ragIndexSelect.value;
        const query = (ragSearchQuery.value || '').trim();
        const topK = parseInt(ragSearchTopK.value || '5', 10) || 5;
        if (!indexName) {
            alert('Selecione um índice');
            return;
        }
        if (!query) {
            alert('Digite um termo para buscar');
            return;
        }
        await searchRAG(indexName, query, topK);
    });
    
    docForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await addDocument();
    });

    fileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await uploadRAGFile();
    });
}

// Carregar métricas globais
async function loadGlobalMetrics() {
    try {
        const response = await fetch(`${API_BASE_URL}/metrics/global?days=7`);
        const data = await response.json();
        
        document.getElementById('total-messages').textContent = 
            formatNumber(data.total_messages || 0);
        document.getElementById('total-tokens').textContent = 
            formatNumber(data.total_tokens || 0);
        document.getElementById('avg-tokens').textContent = 
            formatNumber(data.avg_tokens_per_message || 0, 1);
    } catch (error) {
        console.error('Erro ao carregar métricas globais:', error);
    }
}

// Carregar agentes
async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE_URL}/agents`);
        const data = await response.json();
        
        agentsGrid.innerHTML = '';
        
        if (data.agents.length === 0) {
            agentsGrid.innerHTML = '<div class="loading">Nenhum agente configurado</div>';
            return;
        }
        
        // Carregar métricas de cada agente
        const agentsWithMetrics = await Promise.all(
            data.agents.map(async (agent) => {
                try {
                    const metricsResponse = await fetch(
                        `${API_BASE_URL}/metrics/agents/${agent.id}?days=7`
                    );
                    const metrics = await metricsResponse.json();
                    return { ...agent, metrics };
                } catch (e) {
                    return { ...agent, metrics: null };
                }
            })
        );
        
        agentsWithMetrics.forEach(agent => {
            const card = createAgentCard(agent);
            agentsGrid.appendChild(card);
        });
        
        await loadRAGIndexes();
    } catch (error) {
        console.error('Erro ao carregar agentes:', error);
        agentsGrid.innerHTML = '<div class="error">Erro ao carregar agentes</div>';
    }
}

function createAgentCard(agent) {
    const card = document.createElement('div');
    card.className = 'agent-card';
    
    const metrics = agent.metrics || {};
    
    card.innerHTML = `
        <h3>${agent.id}</h3>
        <div class="agent-info">
            <span><strong>Modelo:</strong> ${agent.model}</span>
            <span><strong>RAG:</strong> ${agent.has_rag ? 'Ativo' : 'Desativado'}</span>
            <span><strong>Tools:</strong> ${agent.tools_count || 0}</span>
        </div>
        ${metrics.messages !== undefined ? `
            <div class="agent-metrics">
                <h4>Métricas (7 dias)</h4>
                <div class="agent-metrics-grid">
                    <div class="agent-metric-item">
                        <span>Mensagens:</span>
                        <strong>${formatNumber(metrics.messages || 0)}</strong>
                    </div>
                    <div class="agent-metric-item">
                        <span>Tokens:</span>
                        <strong>${formatNumber(metrics.tokens_used || 0)}</strong>
                    </div>
                    <div class="agent-metric-item">
                        <span>Taxa Sucesso:</span>
                        <strong>${((metrics.success_rate || 0) * 100).toFixed(1)}%</strong>
                    </div>
                    <div class="agent-metric-item">
                        <span>Tempo Médio:</span>
                        <strong>${(metrics.avg_response_time || 0).toFixed(2)}s</strong>
                    </div>
                </div>
            </div>
        ` : ''}
        <div class="agent-actions">
            <a class="btn btn-secondary btn-small btn-with-icon" href="/create-agent?agent_id=${encodeURIComponent(agent.id)}">
                <svg class="icon"><use href="#icon-edit"></use></svg>
                Editar
            </a>
            <button class="btn btn-outline-danger btn-small btn-with-icon" data-agent-id="${agent.id}">
                <svg class="icon"><use href="#icon-trash"></use></svg>
                Excluir
            </button>
        </div>
    `;

    const deleteBtn = card.querySelector('button[data-agent-id]');
    deleteBtn.addEventListener('click', async () => {
        const agentId = deleteBtn.getAttribute('data-agent-id');
        await deleteAgent(agentId);
    });
    
    return card;
}

// RAG Management
async function loadRAGIndexes() {
    try {
        const current = ragIndexSelect.value;
        const response = await fetch(`${API_BASE_URL}/rag/indexes`);
        const data = await response.json();

        ragIndexSelect.innerHTML = '<option value="">Selecione um índice...</option>';
        (data.indexes || []).forEach(index => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = index;
            ragIndexSelect.appendChild(option);
        });

        if (current && (data.indexes || []).includes(current)) {
            ragIndexSelect.value = current;
        }
    } catch (error) {
        console.error('Erro ao carregar índices RAG:', error);
    }
}

async function loadRAGStats(indexName) {
    try {
        const response = await fetch(`${API_BASE_URL}/rag/${indexName}/stats`);
        const data = await response.json();
        
        ragStats.innerHTML = `
            <strong>Estatísticas do Índice:</strong>
            <span style="margin-left: 20px;">Documentos: ${data.document_count || 0}</span>
        `;
    } catch (error) {
        console.error('Erro ao carregar estatísticas RAG:', error);
        ragStats.innerHTML = '<div class="error">Erro ao carregar estatísticas</div>';
    }
}

async function loadRAGDocuments(indexName) {
    try {
        const response = await fetch(`${API_BASE_URL}/rag/${indexName}/documents?limit=50`);
        const data = await response.json();
        
        ragDocuments.innerHTML = '';
        
        if (data.documents.length === 0) {
            ragDocuments.innerHTML = '<div class="loading">Nenhum documento encontrado</div>';
            return;
        }
        
        data.documents.forEach(doc => {
            const card = createDocumentCard(doc, indexName);
            ragDocuments.appendChild(card);
        });
    } catch (error) {
        console.error('Erro ao carregar documentos RAG:', error);
        ragDocuments.innerHTML = '<div class="error">Erro ao carregar documentos</div>';
    }
}

function createDocumentCard(doc, indexName) {
    const card = document.createElement('div');
    card.className = 'document-card';
    
    const contentPreview = doc.content.length > 200 
        ? doc.content.substring(0, 200) + '...' 
        : doc.content;
    
    card.innerHTML = `
        <div class="document-card-header">
            <span class="document-id">ID: ${doc.id}</span>
            <button class="btn btn-danger btn-small btn-with-icon" onclick="deleteDocument('${indexName}', '${doc.id}')">
                <svg class="icon"><use href="#icon-trash"></use></svg>
                Excluir
            </button>
        </div>
        <div class="document-content">${escapeHtml(contentPreview)}</div>
        ${doc.metadata && Object.keys(doc.metadata).length > 0 ? `
            <div style="font-size: 12px; color: #718096;">
                Metadados: ${JSON.stringify(doc.metadata)}
            </div>
        ` : ''}
    `;
    
    return card;
}

async function addDocument() {
    const indexName = document.getElementById('doc-index').value;
    const content = document.getElementById('doc-content').value;
    const metadataText = document.getElementById('doc-metadata').value;
    
    let metadata = {};
    if (metadataText.trim()) {
        try {
            metadata = JSON.parse(metadataText);
        } catch (e) {
            alert('Erro: Metadados devem ser um JSON válido');
            return;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/rag/${indexName}/documents?backend=qdrant`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content,
                metadata
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            alert(`Documento adicionado com sucesso! ID: ${data.document_id}`);
            docModal.style.display = 'none';
            docForm.reset();
            
            if (ragIndexSelect.value === indexName) {
                loadRAGDocuments(indexName);
                loadRAGStats(indexName);
            }
        } else {
            const error = await response.json();
            alert(`Erro: ${error.detail || 'Erro desconhecido'}`);
        }
    } catch (error) {
        console.error('Erro ao adicionar documento:', error);
        alert('Erro ao adicionar documento');
    }
}

async function uploadRAGFile() {
    const indexName = document.getElementById('file-index').value;
    const fileInput = document.getElementById('rag-file');
    const metadataText = document.getElementById('file-metadata').value;

    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Selecione um arquivo');
        return;
    }

    let metadataJson = '';
    if (metadataText.trim()) {
        try {
            JSON.parse(metadataText);
            metadataJson = metadataText;
        } catch (e) {
            alert('Erro: Metadados devem ser um JSON válido');
            return;
        }
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('backend', 'qdrant');
    formData.append('chunk_size', '1500');
    formData.append('overlap', '300');
    if (metadataJson) {
        formData.append('metadata_json', metadataJson);
    }

    try {
        const response = await fetch(`${API_BASE_URL}/rag/${indexName}/files`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            alert(`Arquivo carregado! Chunks: ${data.chunks}`);
            fileModal.style.display = 'none';
            fileForm.reset();
            if (ragIndexSelect.value === indexName) {
                loadRAGDocuments(indexName);
                loadRAGStats(indexName);
            }
        } else {
            const error = await response.json();
            alert(`Erro: ${error.detail || 'Erro desconhecido'}`);
        }
    } catch (error) {
        console.error('Erro ao carregar arquivo:', error);
        alert('Erro ao carregar arquivo');
    }
}

async function searchRAG(indexName, query, topK) {
    try {
        ragDocuments.innerHTML = '<div class="loading">Buscando...</div>';
        const params = new URLSearchParams({ query, top_k: String(topK), backend: 'qdrant' });
        const response = await fetch(`${API_BASE_URL}/rag/${indexName}/search?${params.toString()}`, {
            method: 'POST'
        });
        const data = await response.json();

        ragDocuments.innerHTML = '';
        const results = data.results || [];
        if (results.length === 0) {
            ragDocuments.innerHTML = '<div class="loading">Nenhum resultado encontrado</div>';
            return;
        }

        results.forEach(res => {
            const card = document.createElement('div');
            card.className = 'document-card';
            const contentPreview = (res.content || '').length > 260 ? (res.content || '').substring(0, 260) + '...' : (res.content || '');
            card.innerHTML = `
                <div class="document-card-header">
                    <span class="document-id">ID: ${res.id}</span>
                    <span class="document-id">Score: ${(res.score || 0).toFixed(4)}</span>
                </div>
                <div class="document-content">${escapeHtml(contentPreview)}</div>
                ${res.metadata && Object.keys(res.metadata).length > 0 ? `
                    <div style="font-size: 12px; color: #718096;">
                        Metadados: ${JSON.stringify(res.metadata)}
                    </div>
                ` : ''}
            `;
            ragDocuments.appendChild(card);
        });
    } catch (error) {
        console.error('Erro ao buscar no RAG:', error);
        ragDocuments.innerHTML = '<div class="error">Erro ao buscar no índice</div>';
    }
}

async function deleteDocument(indexName, documentId) {
    if (!confirm('Tem certeza que deseja deletar este documento?')) {
        return;
    }
    
    try {
        const response = await fetch(
            `${API_BASE_URL}/rag/${indexName}/documents/${documentId}`,
            { method: 'DELETE' }
        );
        
        if (response.ok) {
            loadRAGDocuments(indexName);
            loadRAGStats(indexName);
        } else {
            const error = await response.json();
            alert(`Erro: ${error.detail || 'Erro desconhecido'}`);
        }
    } catch (error) {
        console.error('Erro ao deletar documento:', error);
        alert('Erro ao deletar documento');
    }
}

async function deleteAgent(agentId) {
    if (!confirm(`Tem certeza que deseja excluir o agente "${agentId}"?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/agents/${encodeURIComponent(agentId)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadAgents();
            await loadRAGIndexes();
        } else {
            const error = await response.json();
            alert(`Erro: ${error.detail || 'Erro desconhecido'}`);
        }
    } catch (error) {
        console.error('Erro ao excluir agente:', error);
        alert('Erro ao excluir agente');
    }
}

// Utilitários
function formatNumber(num, decimals = 0) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(num);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expor função globalmente
window.deleteDocument = deleteDocument;

