const API_BASE_URL = (window.SIAUtils && window.SIAUtils.getApiBaseUrl)
    ? window.SIAUtils.getApiBaseUrl()
    : (window.location && window.location.origin ? window.location.origin : 'http://localhost:8000');

let selectedAgent = null;
let conversationId = null;
let isStreaming = true;
let conversationHistory = []; // Histórico de mensagens da conversa
let conversations = {}; // Todas as conversas salvas

// Elementos DOM
const agentSelect = document.getElementById('agent-select');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const clearButton = document.getElementById('clear-button');
const chatMessages = document.getElementById('chat-messages');
const chatTitle = document.getElementById('chat-title');
const statusSpan = document.getElementById('status');
const streamToggle = document.getElementById('stream-toggle');
const conversationsList = document.getElementById('conversations-list');
const newConversationBtn = document.getElementById('new-conversation-btn');
const logoutBtn = document.getElementById('logout-btn');

// ==================== SANITIZAÇÃO ====================

// Função para sanitizar inputs
function sanitizeInput(value) {
    if (!value) return '';
    if (typeof value !== 'string') return value.toString();
    
    // Remove tags HTML perigosas
    let sanitized = value
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
        .replace(/javascript:/gi, '')
        .replace(/on\w+\s*=/gi, '');
    
    sanitized = sanitized.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, '');
    
    // Limita tamanho
    if (sanitized.length > 10000) {
        sanitized = sanitized.substring(0, 10000);
    }
    
    return sanitized.trim();
}

function sanitizeSseDelta(value) {
    if (value === null || value === undefined) return '';
    if (typeof value !== 'string') value = value.toString();

    let sanitized = value
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
        .replace(/javascript:/gi, '')
        .replace(/on\w+\s*=/gi, '');

    sanitized = sanitized.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g, '');

    if (sanitized.length > 20000) {
        sanitized = sanitized.substring(0, 20000);
    }

    return sanitized;
}

// ==================== LOCALSTORAGE - CONVERSAS ====================

// Carregar conversas do localStorage
function loadConversations() {
    try {
        const saved = localStorage.getItem('conversations');
        if (saved) {
            conversations = JSON.parse(saved);
        }
    } catch (error) {
        console.error('Erro ao carregar conversas:', error);
        conversations = {};
    }
    renderConversationsList();
}

// Salvar conversas no localStorage
function saveConversations() {
    try {
        localStorage.setItem('conversations', JSON.stringify(conversations));
    } catch (error) {
        console.error('Erro ao salvar conversas:', error);
    }
}

// Salvar conversa atual
function saveCurrentConversation() {
    if (!selectedAgent || !conversationId) return;
    
    const key = `${selectedAgent}_${conversationId}`;
    conversations[key] = {
        id: conversationId,
        agent: selectedAgent,
        title: getConversationTitle(),
        history: [...conversationHistory],
        lastMessage: conversationHistory.length > 0 
            ? conversationHistory[conversationHistory.length - 1].content.substring(0, 50)
            : 'Nova conversa',
        timestamp: new Date().toISOString(),
        updatedAt: new Date().toISOString()
    };
    
    saveConversations();
    renderConversationsList();
}

// Carregar conversa
function loadConversation(key) {
    const conv = conversations[key];
    if (!conv) return;
    
    selectedAgent = conv.agent;
    conversationId = conv.id;
    conversationHistory = [...conv.history];
    
    // Atualizar UI
    agentSelect.value = selectedAgent;
    chatTitle.textContent = `Chat: ${selectedAgent}`;
    messageInput.disabled = false;
    sendButton.disabled = false;
    
    // Limpar e renderizar mensagens
    chatMessages.innerHTML = '';
    conv.history.forEach(msg => {
        if (msg.role === 'user') {
            addMessage(msg.content, 'user', false);
        } else if (msg.role === 'assistant') {
            addMessage(msg.content, 'assistant', false);
        }
    });
    
    renderConversationsList();
    scrollToBottom();
}

// Deletar conversa
function deleteConversation(key, event) {
    event.stopPropagation();
    if (confirm('Tem certeza que deseja excluir esta conversa?')) {
        delete conversations[key];
        saveConversations();
        renderConversationsList();
        
        // Se era a conversa atual, limpar
        if (conversationId && `${selectedAgent}_${conversationId}` === key) {
            conversationId = null;
            conversationHistory = [];
            chatMessages.innerHTML = '';
            addSystemMessage('Conversa excluída. Selecione um agente para começar uma nova.');
        }
    }
}

// Obter título da conversa
function getConversationTitle() {
    if (conversationHistory.length === 0) {
        return 'Nova conversa';
    }
    const firstUserMessage = conversationHistory.find(m => m.role === 'user');
    if (firstUserMessage) {
        return sanitizeInput(firstUserMessage.content).substring(0, 40) + '...';
    }
    return 'Conversa';
}

// Renderizar lista de conversas
function renderConversationsList() {
    if (!conversationsList) return;
    
    const currentKey = selectedAgent && conversationId 
        ? `${selectedAgent}_${conversationId}` 
        : null;
    
    // Filtrar conversas do agente atual
    const agentConversations = Object.entries(conversations)
        .filter(([key]) => !selectedAgent || key.startsWith(selectedAgent + '_'))
        .sort(([, a], [, b]) => new Date(b.updatedAt) - new Date(a.updatedAt))
        .slice(0, 20); // Limitar a 20 conversas
    
    if (agentConversations.length === 0) {
        conversationsList.innerHTML = '<p class="no-conversations">Nenhuma conversa salva</p>';
        return;
    }
    
    conversationsList.innerHTML = '';
    agentConversations.forEach(([key, conv]) => {
        const item = document.createElement('div');
        item.className = `conversation-item ${key === currentKey ? 'active' : ''}`;
        item.onclick = () => loadConversation(key);
        
        const header = document.createElement('div');
        header.className = 'conversation-item-header';
        
        const title = document.createElement('div');
        title.className = 'conversation-item-title';
        title.textContent = conv.title || 'Conversa sem título';
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'conversation-item-delete';
        deleteBtn.innerHTML = '×';
        deleteBtn.onclick = (e) => deleteConversation(key, e);
        
        header.appendChild(title);
        header.appendChild(deleteBtn);
        
        const meta = document.createElement('div');
        meta.className = 'conversation-item-meta';
        const date = new Date(conv.updatedAt);
        meta.innerHTML = `
            <span>${date.toLocaleDateString('pt-BR')}</span>
            <span>${conv.history.length} msgs</span>
        `;
        
        item.appendChild(header);
        item.appendChild(meta);
        conversationsList.appendChild(item);
    });
}

// Nova conversa
function newConversation() {
    if (!selectedAgent) {
        alert('Selecione um agente primeiro');
        return;
    }
    
    // Salvar conversa atual se houver mensagens
    if (conversationHistory.length > 0) {
        saveCurrentConversation();
    }
    
    conversationId = `conv_${Date.now()}`;
    conversationHistory = [];
    chatMessages.innerHTML = '';
    addSystemMessage(`Nova conversa iniciada com "${selectedAgent}"`);
    renderConversationsList();
}

// ==================== AUTENTICAÇÃO ====================

// Verificar autenticação
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/verify`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (!response.ok) {
            window.location.href = '/login';
            return false;
        }
        return true;
    } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
        window.location.href = '/login';
        return false;
    }
}

// Logout
async function logout() {
    try {
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
    } catch (error) {
        console.error('Erro ao fazer logout:', error);
    }
    window.location.href = '/login';
}

// ==================== FUNÇÕES EXISTENTES ====================

// Carregar agentes
async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE_URL}/agents`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        agentSelect.innerHTML = '<option value="">Selecione um agente...</option>';
        
        data.agents.forEach(agent => {
            const option = document.createElement('option');
            option.value = agent.id;
            option.textContent = `${agent.id} (${agent.model})`;
            agentSelect.appendChild(option);
        });
        
        updateStatus('Conectado');
    } catch (error) {
        console.error('Erro ao carregar agentes:', error);
        updateStatus('Erro ao conectar');
        agentSelect.innerHTML = '<option value="">Erro ao carregar agentes</option>';
    }
}

// Atualizar status
function updateStatus(status) {
    if (statusSpan) {
        statusSpan.textContent = status;
        statusSpan.style.color = status === 'Conectado' ? '#48bb78' : 
                                status === 'Desconectado' ? '#f56565' : '#ed8936';
    }
}

// Selecionar agente
if (agentSelect) {
    agentSelect.addEventListener('change', (e) => {
        selectedAgent = e.target.value;
        
        if (selectedAgent) {
            chatTitle.textContent = `Chat: ${selectedAgent}`;
            messageInput.disabled = false;
            sendButton.disabled = false;
            
            // Salvar conversa anterior se houver
            if (conversationHistory.length > 0 && conversationId) {
                saveCurrentConversation();
            }
            
            conversationId = `conv_${Date.now()}`;
            conversationHistory = [];
            chatMessages.innerHTML = '';
            addSystemMessage(`Agente "${selectedAgent}" selecionado. Você pode começar a conversar!`);
            renderConversationsList();
        } else {
            chatTitle.textContent = 'Selecione um agente para começar';
            messageInput.disabled = true;
            sendButton.disabled = true;
        }
    });
}

// Toggle streaming
if (streamToggle) {
    streamToggle.addEventListener('change', (e) => {
        isStreaming = e.target.checked;
    });
}

// Renderizar markdown
let markedConfigured = false;

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function isSafeUrl(url) {
    const value = String(url || '').trim();
    if (!value) return false;
    if (value.startsWith('#')) return true;
    if (value.startsWith('/')) return true;
    if (value.startsWith('./') || value.startsWith('../')) return true;
    try {
        const parsed = new URL(value, window.location.origin);
        return ['http:', 'https:', 'mailto:', 'tel:'].includes(parsed.protocol);
    } catch (e) {
        return false;
    }
}

function sanitizeRenderedHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = String(html || '');
    const blocked = new Set(['SCRIPT', 'IFRAME', 'OBJECT', 'EMBED', 'LINK', 'META', 'STYLE']);
    const elements = template.content.querySelectorAll('*');
    elements.forEach((el) => {
        if (blocked.has(el.tagName)) {
            el.remove();
            return;
        }
        Array.from(el.attributes).forEach((attr) => {
            const name = attr.name.toLowerCase();
            if (name.startsWith('on')) {
                el.removeAttribute(attr.name);
                return;
            }
            if (name === 'href' || name === 'src') {
                if (!isSafeUrl(attr.value)) {
                    el.removeAttribute(attr.name);
                }
            }
        });
    });
    return template.innerHTML;
}

function ensureMarkedConfiguredOnce() {
    if (markedConfigured) return;
    if (typeof marked !== 'undefined' && marked && marked.setOptions) {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false
        });
    }
    markedConfigured = true;
}

function renderMarkdown(text) {
    if (!text) return '';
    
    // Verificar se marked está disponível
    if (typeof marked !== 'undefined' && marked) {
        try {
            ensureMarkedConfiguredOnce();
            // Usar marked.parse ou marked dependendo da versão
            const parser = marked.parse || marked;
            const html = parser(escapeHtml(text));
            return sanitizeRenderedHtml(html);
        } catch (e) {
            console.warn('Erro ao usar marked.js, usando fallback:', e);
        }
    }
    
    // Fallback: converter markdown básico manualmente
    let html = escapeHtml(text);
    
    // Processar linha por linha para listas
    const lines = html.split('\n');
    const processedLines = [];
    let inList = false;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const isListItem = /^[\-\*\+]\s+(.+)$/.test(line);
        
        if (isListItem) {
            if (!inList) {
                processedLines.push('<ul>');
                inList = true;
            }
            const content = line.replace(/^[\-\*\+]\s+/, '');
            processedLines.push('<li>' + content + '</li>');
        } else {
            if (inList) {
                processedLines.push('</ul>');
                inList = false;
            }
            processedLines.push(line);
        }
    }
    
    if (inList) {
        processedLines.push('</ul>');
    }
    
    html = processedLines.join('\n');
    
    // Aplicar outras transformações
    html = html
        // Headers (após processar listas)
        .replace(/^### (.*)$/gm, '<h3>$1</h3>')
        .replace(/^## (.*)$/gm, '<h2>$1</h2>')
        .replace(/^# (.*)$/gm, '<h1>$1</h1>')
        // Negrito (não dentro de tags HTML)
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        // Itálico (não dentro de tags HTML)
        .replace(/(?<![*])\*([^*]+)\*(?![*])/g, '<em>$1</em>')
        // Linha horizontal
        .replace(/^---$/gm, '<hr>')
        // Quebras de linha (mas não dentro de tags HTML)
        .replace(/\n/g, '<br>');
    
    return html;
}

function safeFilename(value) {
    if (!value) return 'export';
    return value
        .toString()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9\-_ ]/g, '')
        .trim()
        .replace(/\s+/g, '_')
        .substring(0, 80) || 'export';
}

function buildExportHtml(title, contentHtml) {
    const safeTitle = escapeHtml(title || 'Exportação');
    return `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${safeTitle}</title>
  <style>
    body { font-family: Arial, sans-serif; color: #0f172a; margin: 24px; }
    h1,h2,h3 { margin: 0 0 12px; }
    a { color: #0f52ba; }
    pre { background: #f1f5f9; padding: 12px; border-radius: 8px; overflow-x: auto; }
    code { font-family: 'Courier New', monospace; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; font-weight: 700; }
    hr { border: none; border-top: 1px solid #cbd5e1; margin: 16px 0; }
  </style>
</head>
<body>
  <h2>${safeTitle}</h2>
  <hr>
  ${contentHtml}
</body>
</html>`;
}

function exportBubbleAsWord(bubble, fileBaseName) {
    if (!bubble) return;
    const title = fileBaseName || 'Resposta';
    const html = buildExportHtml(title, bubble.innerHTML || '');
    const blob = new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeFilename(title)}.doc`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportBubbleAsPdf(bubble, fileBaseName) {
    if (!bubble) return;
    const title = fileBaseName || 'Resposta';
    const html = buildExportHtml(title, bubble.innerHTML || '');
    const w = window.open('', '_blank', 'noopener,noreferrer');
    if (!w) {
        addSystemMessage('⚠️ Bloqueador de pop-up impediu a exportação em PDF.');
        return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    w.addEventListener('load', () => {
        w.print();
    });
}

function createMessageActions(bubble, type) {
    if (type !== 'assistant') return null;
    const actions = document.createElement('div');
    actions.className = 'message-actions';

    const now = new Date();
    const agentLabel = (typeof selectedAgent !== 'undefined' && selectedAgent) ? selectedAgent : 'assistente';
    const baseName = `Resposta_${agentLabel}_${now.toLocaleDateString('pt-BR')}_${now.toLocaleTimeString('pt-BR')}`;

    const makeBtn = (kind, title, svgHtml, onClick) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `message-action-btn ${kind}`;
        btn.title = title;
        btn.setAttribute('aria-label', title);
        btn.innerHTML = svgHtml;
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            onClick();
        });
        return btn;
    };

    const pdfSvg = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
  <path d="M7 3h7l3 3v15a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" stroke="currentColor" stroke-width="1.6"/>
  <path d="M14 3v4a1 1 0 0 0 1 1h4" stroke="currentColor" stroke-width="1.6"/>
  <path d="M7.5 16.5h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M7.5 13.5h9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
</svg>`;

    const wordSvg = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
  <path d="M7 3h7l3 3v15a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" stroke="currentColor" stroke-width="1.6"/>
  <path d="M14 3v4a1 1 0 0 0 1 1h4" stroke="currentColor" stroke-width="1.6"/>
  <path d="M8 12.5l1.2 6 1.6-6 1.6 6 1.2-6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

    actions.appendChild(
        makeBtn('pdf', 'Exportar esta resposta em PDF', pdfSvg, () => exportBubbleAsPdf(bubble, baseName))
    );
    actions.appendChild(
        makeBtn('word', 'Exportar esta resposta em Word', wordSvg, () => exportBubbleAsWord(bubble, baseName))
    );

    return actions;
}

// Adicionar mensagem
function addMessage(content, type = 'user', save = true) {
    // Sanitizar conteúdo
    const sanitizedContent = sanitizeInput(content);
    
    // Armazenar no histórico
    if (save) {
        conversationHistory.push({
            role: type === 'user' ? 'user' : 'assistant',
            content: sanitizedContent,
            timestamp: new Date().toISOString()
        });
        
        // Salvar conversa periodicamente
        if (conversationHistory.length % 5 === 0) {
            saveCurrentConversation();
        }
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    // Renderizar markdown apenas para mensagens do assistente
    if (type === 'assistant') {
        bubble.setAttribute('data-text', sanitizedContent);
        bubble.innerHTML = renderMarkdown(sanitizedContent);
    } else {
        bubble.textContent = sanitizedContent;
    }
    
    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    messageDiv.appendChild(bubble);
    const actions = createMessageActions(bubble, type);
    if (actions) {
        messageDiv.appendChild(actions);
    }
    messageDiv.appendChild(time);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
    return bubble;
}

// Adicionar mensagem do sistema
function addSystemMessage(content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = sanitizeInput(content);
    
    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
}

// Indicador de digitação
function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = 'typing-indicator';
    
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    
    messageDiv.appendChild(indicator);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
    return messageDiv;
}

// Remover indicador de digitação
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Scroll para baixo
function scrollToBottom() {
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Enviar mensagem com streaming
async function sendMessageStreaming(message) {
    try {
        // Sanitizar mensagem antes de enviar
        const sanitizedMessage = sanitizeInput(message);
        
        // Preparar histórico de mensagens (sem incluir a mensagem atual que será adicionada depois)
        const history = conversationHistory.map(msg => ({
            role: msg.role,
            content: sanitizeInput(msg.content)
        }));
        
        const response = await fetch(`${API_BASE_URL}/webhooks/${selectedAgent}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                user_id: 'web_user',
                channel: 'web',
                text: sanitizedMessage,
                conversation_id: conversationId,
                stream: true,
                history: history
            })
        });

        if (!response.ok) {
            throw new Error(`Erro: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = null;
        let assistantHistoryIndex = null;
        let buffer = '';

        function ensureAssistantMessage() {
            if (assistantMessage) return;
            removeTypingIndicator();
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.setAttribute('data-text', '');
            bubble.innerHTML = '';
            messageDiv.appendChild(bubble);
            const actions = createMessageActions(bubble, 'assistant');
            if (actions) {
                messageDiv.appendChild(actions);
            }
            chatMessages.appendChild(messageDiv);
            assistantMessage = bubble;

            assistantHistoryIndex = conversationHistory.length;
            conversationHistory.push({
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString()
            });
        }

        function appendAssistantText(delta) {
            const sanitizedDelta = sanitizeSseDelta(delta);
            if (!sanitizedDelta) return;
            ensureAssistantMessage();
            const currentText = (assistantMessage.getAttribute('data-text') || '') + sanitizedDelta;
            assistantMessage.setAttribute('data-text', currentText);
            assistantMessage.innerHTML = renderMarkdown(currentText);
            if (assistantHistoryIndex !== null) {
                conversationHistory[assistantHistoryIndex] = {
                    role: 'assistant',
                    content: sanitizeInput(currentText),
                    timestamp: new Date().toISOString()
                };
            }
            scrollToBottom();
        }

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split(/\r?\n/);
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line) continue;
                if (line.startsWith('data:')) {
                    let data = line.slice(5);
                    if (data.startsWith(' ')) data = data.slice(1);
                    if (data === '[DONE]') continue;
                    let decoded = data;
                    try {
                        if (decoded && (decoded[0] === '"' || decoded[0] === '{' || decoded[0] === '[')) {
                            decoded = JSON.parse(decoded);
                        }
                    } catch (e) {
                        decoded = data;
                    }
                    appendAssistantText(decoded);
                }
            }
        }

        // Adicionar timestamp e atualizar histórico
        if (assistantMessage) {
            buffer += decoder.decode();
            if (buffer) {
                const tailLines = buffer.split(/\r?\n/);
                for (const line of tailLines) {
                    if (!line) continue;
                    if (line.startsWith('data:')) {
                        let data = line.slice(5);
                        if (data.startsWith(' ')) data = data.slice(1);
                        if (data === '[DONE]') continue;
                        let decoded = data;
                        try {
                            if (decoded && (decoded[0] === '"' || decoded[0] === '{' || decoded[0] === '[')) {
                                decoded = JSON.parse(decoded);
                            }
                        } catch (e) {
                            decoded = data;
                        }
                        appendAssistantText(decoded);
                    }
                }
            }
            
            const time = document.createElement('div');
            time.className = 'message-time';
            time.textContent = new Date().toLocaleTimeString('pt-BR', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            assistantMessage.parentElement.appendChild(time);
            
            // Salvar conversa
            saveCurrentConversation();
        }
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        removeTypingIndicator();
        addSystemMessage(`❌ Erro: ${error.message}`);
    }
}

// Enviar mensagem sem streaming
async function sendMessageNormal(message) {
    try {
        const sanitizedMessage = sanitizeInput(message);
        
        const response = await fetch(`${API_BASE_URL}/webhooks/${selectedAgent}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                user_id: 'web_user',
                channel: 'web',
                text: sanitizedMessage,
                conversation_id: conversationId,
                stream: false
            })
        });

        const data = await response.json();
        
        if (response.ok && data.job_id) {
            addSystemMessage('⏳ Processando... (aguarde alguns segundos)');
            
            setTimeout(async () => {
                try {
                    removeTypingIndicator();
                    addSystemMessage('✅ Mensagem enviada e processada pelo worker. Verifique os logs do worker para ver a resposta.');
                    saveCurrentConversation();
                } catch (error) {
                    console.error('Erro ao verificar resposta:', error);
                }
            }, 2000);
        } else {
            throw new Error(data.detail || 'Erro desconhecido');
        }
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        removeTypingIndicator();
        addSystemMessage(`❌ Erro: ${error.message}`);
    }
}

// Enviar mensagem
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || !selectedAgent) return;

    // Sanitizar antes de processar
    const sanitizedMessage = sanitizeInput(message);
    if (!sanitizedMessage) {
        addSystemMessage('⚠️ Mensagem inválida ou muito longa');
        return;
    }

    // Adicionar mensagem do usuário
    addMessage(sanitizedMessage, 'user');
    messageInput.value = '';

    // Adicionar indicador de digitação
    addTypingIndicator();

    // Enviar mensagem
    if (isStreaming) {
        await sendMessageStreaming(sanitizedMessage);
    } else {
        await sendMessageNormal(sanitizedMessage);
    }
}

// Event listeners
if (sendButton) {
    sendButton.addEventListener('click', sendMessage);
}

if (messageInput) {
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

if (clearButton) {
    clearButton.addEventListener('click', () => {
        if (conversationHistory.length > 0) {
            saveCurrentConversation();
        }
        chatMessages.innerHTML = '';
        conversationHistory = [];
        if (selectedAgent) {
            conversationId = `conv_${Date.now()}`;
            addSystemMessage(`Chat limpo. Nova conversa iniciada com "${selectedAgent}"`);
        } else {
            addSystemMessage('👋 Bem-vindo! Selecione um agente acima para começar a conversar.');
        }
        renderConversationsList();
    });
}

if (newConversationBtn) {
    newConversationBtn.addEventListener('click', newConversation);
}

if (logoutBtn) {
    logoutBtn.addEventListener('click', logout);
}

// Inicialização
window.addEventListener('DOMContentLoaded', async () => {
    // Verificar autenticação
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) return;
    
    // Carregar conversas
    loadConversations();
    
    // Carregar agentes
    loadAgents();
    updateStatus('Conectando...');
    
    // Verificar marked.js
    setTimeout(() => {
        if (typeof marked === 'undefined') {
            console.warn('marked.js não carregou, usando fallback de markdown');
        } else {
            console.log('marked.js carregado com sucesso');
        }
    }, 100);
});
