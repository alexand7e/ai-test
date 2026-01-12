// Estado dos arquivos
let uploadedFiles = [];

// Elementos do DOM
const form = document.getElementById('agent-form');
const fileUploadArea = document.getElementById('file-upload-area');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const ragEnabled = document.getElementById('rag-enabled');
const ragConfig = document.getElementById('rag-config');
const ragFileUploadArea = document.getElementById('rag-file-upload-area');
const ragFileInput = document.getElementById('rag-file-input');
const ragFileList = document.getElementById('rag-file-list');
const dataAnalysisEnabled = document.getElementById('data-analysis-enabled');
const dataAnalysisConfig = document.getElementById('data-analysis-config');
const errorMessage = document.getElementById('error-message');
const successMessage = document.getElementById('success-message');
const modelSelect = document.getElementById('agent-model');
const pageTitle = document.getElementById('page-title');
const submitBtn = document.getElementById('submit-btn');

let editAgentId = null;
let loadedAgent = null;
let ragUploadedFiles = [];

// Carrega modelos ao carregar a página
async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();
        
        // Limpa opções existentes
        modelSelect.innerHTML = '';
        
        if (data.models && data.models.length > 0) {
            // Agrupa modelos por categoria
            const modelsByCategory = {};
            data.models.forEach(model => {
                const category = model.categoria || 'Outros';
                if (!modelsByCategory[category]) {
                    modelsByCategory[category] = [];
                }
                modelsByCategory[category].push(model);
            });
            
            // Cria grupos de opções por categoria
            Object.keys(modelsByCategory).sort().forEach(category => {
                const optgroup = document.createElement('optgroup');
                optgroup.label = category;
                
                modelsByCategory[category].forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.model_id;
                    option.textContent = `${model.model_id} - ${model.uso_adequado || ''}`;
                    optgroup.appendChild(option);
                });
                
                modelSelect.appendChild(optgroup);
            });
        } else {
            // Fallback se não houver modelos
            const option = document.createElement('option');
            option.value = 'Qwen/Qwen2.5-3B-Instruct';
            option.textContent = 'Qwen/Qwen2.5-3B-Instruct';
            modelSelect.appendChild(option);
        }
    } catch (error) {
        console.error('Erro ao carregar modelos:', error);
        // Fallback em caso de erro
        modelSelect.innerHTML = '<option value="Qwen/Qwen2.5-3B-Instruct">Qwen/Qwen2.5-3B-Instruct</option>';
    }
}

// Carrega modelos quando a página carrega
document.addEventListener('DOMContentLoaded', async () => {
    await loadModels();
    await loadAgentForEditIfNeeded();
});

window.removeRagFile = removeRagFile;

async function loadAgentForEditIfNeeded() {
    const params = new URLSearchParams(window.location.search || '');
    const agentId = params.get('agent_id');
    if (!agentId) {
        return;
    }

    editAgentId = agentId;
    try {
        const response = await fetch(`/agents/${encodeURIComponent(agentId)}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Erro ao carregar agente');
        }

        loadedAgent = await response.json();

        pageTitle.innerHTML = `
            <svg class="icon icon-title"><use href="#icon-users"></use></svg>
            Editar Agente
        `;
        submitBtn.innerHTML = `
            <svg class="icon"><use href="#icon-save"></use></svg>
            Salvar Alterações
        `;

        const idInput = document.getElementById('agent-id');
        idInput.value = loadedAgent.id || agentId;
        idInput.disabled = true;

        document.getElementById('agent-nome').value = loadedAgent.nome || '';
        document.getElementById('agent-model').value = loadedAgent.model || '';
        document.getElementById('agent-api-key').value = loadedAgent.api_key || '';
        document.getElementById('agent-webhook-name').value = loadedAgent.webhook_name || '';
        document.getElementById('agent-prompt').value = loadedAgent.system_prompt || '';

        document.getElementById('input-schema').value = JSON.stringify(loadedAgent.input_schema || {}, null, 2);
        document.getElementById('output-schema').value = JSON.stringify(loadedAgent.output_schema || {}, null, 2);

        if (loadedAgent.rag) {
            ragEnabled.checked = true;
            ragConfig.style.display = 'block';
            document.getElementById('rag-index-name').required = true;
            document.getElementById('rag-index-name').value = loadedAgent.rag.index_name || '';
            document.getElementById('rag-top-k').value = loadedAgent.rag.top_k || 5;
            document.getElementById('rag-chunk-size').value = loadedAgent.rag.chunk_size || 1500;
            document.getElementById('rag-overlap').value = loadedAgent.rag.overlap || 300;
        }

        if (loadedAgent.data_analysis && loadedAgent.data_analysis.enabled) {
            dataAnalysisEnabled.checked = true;
            dataAnalysisConfig.style.display = 'block';
        }
    } catch (error) {
        showError(error.message || 'Erro ao carregar agente para edição');
    }
}

// Toggle RAG config
ragEnabled.addEventListener('change', (e) => {
    ragConfig.style.display = e.target.checked ? 'block' : 'none';
    if (e.target.checked) {
        document.getElementById('rag-index-name').required = true;
    } else {
        document.getElementById('rag-index-name').required = false;
    }
});

// Toggle Data Analysis config
dataAnalysisEnabled.addEventListener('change', (e) => {
    dataAnalysisConfig.style.display = e.target.checked ? 'block' : 'none';
});

// File upload handlers
fileUploadArea.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    handleFiles(Array.from(e.target.files));
});

fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadArea.classList.add('dragover');
});

fileUploadArea.addEventListener('dragleave', () => {
    fileUploadArea.classList.remove('dragover');
});

fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadArea.classList.remove('dragover');
    handleFiles(Array.from(e.dataTransfer.files));
});

function handleFiles(files) {
    const allowedTypes = ['.csv', '.json', '.xlsx', '.xls'];
    
    files.forEach(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedTypes.includes(ext)) {
            showError(`Tipo de arquivo não suportado: ${file.name}. Use CSV, JSON ou XLSX.`);
            return;
        }
        
        // Verifica se arquivo já foi adicionado
        if (uploadedFiles.find(f => f.name === file.name)) {
            showError(`Arquivo ${file.name} já foi adicionado.`);
            return;
        }
        
        uploadedFiles.push(file);
        renderFileList();
    });
}

ragFileUploadArea.addEventListener('click', () => {
    ragFileInput.click();
});

ragFileInput.addEventListener('change', (e) => {
    handleRagFiles(Array.from(e.target.files));
});

ragFileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    ragFileUploadArea.classList.add('dragover');
});

ragFileUploadArea.addEventListener('dragleave', () => {
    ragFileUploadArea.classList.remove('dragover');
});

ragFileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    ragFileUploadArea.classList.remove('dragover');
    handleRagFiles(Array.from(e.dataTransfer.files));
});

function handleRagFiles(files) {
    const allowedTypes = ['.pdf', '.docx', '.xlsx', '.xls', '.txt', '.md'];

    files.forEach(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedTypes.includes(ext)) {
            showError(`Tipo de arquivo não suportado: ${file.name}. Use PDF, DOCX, XLSX, TXT ou MD.`);
            return;
        }

        if (ragUploadedFiles.find(f => f.name === file.name)) {
            showError(`Arquivo ${file.name} já foi adicionado.`);
            return;
        }

        ragUploadedFiles.push(file);
        renderRagFileList();
    });
}

function removeRagFile(filename) {
    ragUploadedFiles = ragUploadedFiles.filter(f => f.name !== filename);
    renderRagFileList();
}

function renderRagFileList() {
    ragFileList.innerHTML = '';
    if (ragUploadedFiles.length === 0) {
        return;
    }

    ragUploadedFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span class="file-item-name">${file.name} (${formatFileSize(file.size)})</span>
            <span class="file-item-remove" onclick="removeRagFile('${file.name}')">✕ Remover</span>
        `;
        ragFileList.appendChild(fileItem);
    });
}

function removeFile(filename) {
    uploadedFiles = uploadedFiles.filter(f => f.name !== filename);
    renderFileList();
}

function renderFileList() {
    fileList.innerHTML = '';
    
    if (uploadedFiles.length === 0) {
        return;
    }
    
    uploadedFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span class="file-item-name">${file.name} (${formatFileSize(file.size)})</span>
            <span class="file-item-remove" onclick="removeFile('${file.name}')">✕ Remover</span>
        `;
        fileList.appendChild(fileItem);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Form submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideMessages();
    
    try {
        // Valida schemas JSON
        const inputSchemaText = document.getElementById('input-schema').value;
        const outputSchemaText = document.getElementById('output-schema').value;
        
        let inputSchema, outputSchema;
        try {
            inputSchema = JSON.parse(inputSchemaText);
        } catch (err) {
            showError('Input Schema inválido. Verifique o JSON.');
            return;
        }
        
        try {
            outputSchema = JSON.parse(outputSchemaText);
        } catch (err) {
            showError('Output Schema inválido. Verifique o JSON.');
            return;
        }
        
        // Prepara dados do agente
        const agentData = {
            id: document.getElementById('agent-id').value,
            nome: document.getElementById('agent-nome').value || null,
            model: document.getElementById('agent-model').value,
            api_key: document.getElementById('agent-api-key').value || null,
            webhook_name: document.getElementById('agent-webhook-name').value || null,
            system_prompt: document.getElementById('agent-prompt').value,
            input_schema: inputSchema,
            output_schema: outputSchema,
            tools: (loadedAgent && loadedAgent.tools) ? loadedAgent.tools : [],
            webhook_output_url: (loadedAgent && loadedAgent.webhook_output_url !== undefined) ? loadedAgent.webhook_output_url : null
        };
        
        // Adiciona RAG se habilitado
        if (ragEnabled.checked) {
            agentData.rag = {
                type: 'qdrant',
                index_name: document.getElementById('rag-index-name').value,
                top_k: parseInt(document.getElementById('rag-top-k').value) || 5,
                chunk_size: parseInt(document.getElementById('rag-chunk-size').value) || 1500,
                overlap: parseInt(document.getElementById('rag-overlap').value) || 300
            };
        }
        
        // Adiciona Data Analysis se habilitado
        if (dataAnalysisEnabled.checked) {
            agentData.data_analysis = {
                enabled: true,
                files: uploadedFiles.map(f => f.name),
                query_engine: 'pandas'
            };
        }
        
        const url = editAgentId ? `/agents/${encodeURIComponent(editAgentId)}` : '/agents/create';
        const method = editAgentId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(agentData)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Erro ao criar agente');
        }
        
        // Upload de arquivos se houver
        if (uploadedFiles.length > 0 && dataAnalysisEnabled.checked) {
            for (const file of uploadedFiles) {
                const formData = new FormData();
                formData.append('file', file);
                
                const uploadResponse = await fetch(`/agents/${agentData.id}/files`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!uploadResponse.ok) {
                    console.warn(`Erro ao fazer upload de ${file.name}`);
                }
            }
        }

        if (ragEnabled.checked && ragUploadedFiles.length > 0) {
            const indexName = document.getElementById('rag-index-name').value;
            const chunkSize = parseInt(document.getElementById('rag-chunk-size').value) || 1500;
            const overlap = parseInt(document.getElementById('rag-overlap').value) || 300;

            for (const file of ragUploadedFiles) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('backend', 'qdrant');
                formData.append('chunk_size', String(chunkSize));
                formData.append('overlap', String(overlap));
                formData.append('metadata_json', JSON.stringify({
                    source: 'agent_upload',
                    agent_id: agentData.id
                }));

                const uploadResponse = await fetch(`/rag/${encodeURIComponent(indexName)}/files`, {
                    method: 'POST',
                    body: formData
                });

                if (!uploadResponse.ok) {
                    const err = await uploadResponse.json().catch(() => ({}));
                    throw new Error(err.detail || `Erro ao carregar arquivo no RAG: ${file.name}`);
                }
            }
        }
        
        showSuccess(`Agente ${agentData.id} salvo com sucesso! Redirecionando...`);
        
        // Redireciona após 1.5 segundos
        setTimeout(() => {
            window.location.href = '/admin';
        }, 1500);
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message || 'Erro ao criar agente. Tente novamente.');
    }
});

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';
}

function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';
}

function hideMessages() {
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';
}

