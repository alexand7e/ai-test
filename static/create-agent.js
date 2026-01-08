// Estado dos arquivos
let uploadedFiles = [];

// Elementos do DOM
const form = document.getElementById('agent-form');
const fileUploadArea = document.getElementById('file-upload-area');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const ragEnabled = document.getElementById('rag-enabled');
const ragConfig = document.getElementById('rag-config');
const dataAnalysisEnabled = document.getElementById('data-analysis-enabled');
const dataAnalysisConfig = document.getElementById('data-analysis-config');
const errorMessage = document.getElementById('error-message');
const successMessage = document.getElementById('success-message');

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
            <span class="file-item-name">📄 ${file.name} (${formatFileSize(file.size)})</span>
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
            tools: [],
            webhook_output_url: null
        };
        
        // Adiciona RAG se habilitado
        if (ragEnabled.checked) {
            agentData.rag = {
                type: 'redis',
                index_name: document.getElementById('rag-index-name').value,
                top_k: parseInt(document.getElementById('rag-top-k').value) || 5
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
        
        // Cria agente
        const response = await fetch('/agents/create', {
            method: 'POST',
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
        
        showSuccess(`Agente ${agentData.id} criado com sucesso! Redirecionando...`);
        
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

