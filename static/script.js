const API_BASE_URL = 'http://localhost:8000';

let selectedAgent = null;
let conversationId = null;
let isStreaming = true;
let conversationHistory = []; // Histórico de mensagens da conversa

// Elementos DOM
const agentSelect = document.getElementById('agent-select');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const clearButton = document.getElementById('clear-button');
const chatMessages = document.getElementById('chat-messages');
const chatTitle = document.getElementById('chat-title');
const statusSpan = document.getElementById('status');
const streamToggle = document.getElementById('stream-toggle');

// Carregar agentes
async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE_URL}/agents`);
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
    statusSpan.textContent = status;
    statusSpan.style.color = status === 'Conectado' ? '#48bb78' : 
                            status === 'Desconectado' ? '#f56565' : '#ed8936';
}

// Selecionar agente
agentSelect.addEventListener('change', (e) => {
    selectedAgent = e.target.value;
    
    if (selectedAgent) {
        chatTitle.textContent = `Chat: ${selectedAgent}`;
        messageInput.disabled = false;
        sendButton.disabled = false;
        conversationId = `conv_${Date.now()}`;
        conversationHistory = []; // Limpar histórico ao trocar de agente
        addSystemMessage(`Agente "${selectedAgent}" selecionado. Você pode começar a conversar!`);
    } else {
        chatTitle.textContent = 'Selecione um agente para começar';
        messageInput.disabled = true;
        sendButton.disabled = true;
    }
});

// Toggle streaming
streamToggle.addEventListener('change', (e) => {
    isStreaming = e.target.checked;
});

// Adicionar mensagem
function addMessage(content, type = 'user') {
    // Armazenar no histórico
    conversationHistory.push({
        role: type === 'user' ? 'user' : 'assistant',
        content: content,
        timestamp: new Date().toISOString()
    });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = content;
    
    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    messageDiv.appendChild(bubble);
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
    bubble.textContent = content;
    
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
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Enviar mensagem com streaming
async function sendMessageStreaming(message) {
    try {
        // Preparar histórico de mensagens (sem incluir a mensagem atual que será adicionada depois)
        const history = conversationHistory.map(msg => ({
            role: msg.role,
            content: msg.content
        }));
        
        const response = await fetch(`${API_BASE_URL}/webhooks/${selectedAgent}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: 'web_user',
                channel: 'web',
                text: message,
                conversation_id: conversationId,
                stream: true,
                history: history  // Enviar histórico completo
            })
        });

        if (!response.ok) {
            throw new Error(`Erro: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data.trim()) {
                        if (!assistantMessage) {
                            removeTypingIndicator();
                            const messageDiv = document.createElement('div');
                            messageDiv.className = 'message assistant';
                            const bubble = document.createElement('div');
                            bubble.className = 'message-bubble';
                            bubble.textContent = data;
                            messageDiv.appendChild(bubble);
                            chatMessages.appendChild(messageDiv);
                            assistantMessage = bubble;
                        } else {
                            assistantMessage.textContent += data;
                        }
                        scrollToBottom();
                    }
                }
            }
        }

        // Adicionar timestamp e atualizar histórico
        if (assistantMessage) {
            const fullResponse = assistantMessage.textContent;
            // Atualizar o histórico com a resposta completa
            conversationHistory[conversationHistory.length - 1] = {
                role: 'assistant',
                content: fullResponse,
                timestamp: new Date().toISOString()
            };
            
            const time = document.createElement('div');
            time.className = 'message-time';
            time.textContent = new Date().toLocaleTimeString('pt-BR', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
            assistantMessage.parentElement.appendChild(time);
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
        const response = await fetch(`${API_BASE_URL}/webhooks/${selectedAgent}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: 'web_user',
                channel: 'web',
                text: message,
                conversation_id: conversationId,
                stream: false
            })
        });

        const data = await response.json();
        
        if (response.ok && data.job_id) {
            // Aguardar processamento do worker
            addSystemMessage('⏳ Processando... (aguarde alguns segundos)');
            
            // Polling simples - em produção, usar WebSocket ou Server-Sent Events
            setTimeout(async () => {
                try {
                    // Verificar se há resposta via pub/sub ou webhook
                    // Por enquanto, apenas avisamos que foi enfileirado
                    removeTypingIndicator();
                    addSystemMessage('✅ Mensagem enviada e processada pelo worker. Verifique os logs do worker para ver a resposta.');
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

    // Adicionar mensagem do usuário
    addMessage(message, 'user');
    messageInput.value = '';

    // Adicionar indicador de digitação
    addTypingIndicator();

    // Enviar mensagem
    if (isStreaming) {
        await sendMessageStreaming(message);
    } else {
        await sendMessageNormal(message);
    }
}

// Event listeners
sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

clearButton.addEventListener('click', () => {
    chatMessages.innerHTML = '';
    conversationHistory = []; // Limpar histórico também
    if (selectedAgent) {
        conversationId = `conv_${Date.now()}`; // Nova conversa
        addSystemMessage(`Chat limpo. Nova conversa iniciada com "${selectedAgent}"`);
    } else {
        addSystemMessage('👋 Bem-vindo! Selecione um agente acima para começar a conversar.');
    }
});

// Inicializar
loadAgents();
updateStatus('Conectando...');

