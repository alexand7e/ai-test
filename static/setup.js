const API_BASE_URL = (window.location && window.location.origin ? window.location.origin : 'http://localhost:8000');
const setupForm = document.getElementById('setup-form');
const errorMessage = document.getElementById('error-message');
const setupButton = document.getElementById('setup-button');

setupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMessage.textContent = '';
    setupButton.disabled = true;
    setupButton.textContent = 'Configurando...';

    const adminName = document.getElementById('admin-name').value;
    const adminEmail = document.getElementById('admin-email').value;
    const adminPassword = document.getElementById('admin-password').value;
    const groupName = document.getElementById('group-name').value;

    try {
        // 1. Run Setup
        const response = await fetch(`${API_BASE_URL}/api/setup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_name: adminName,
                admin_email: adminEmail,
                admin_password: adminPassword,
                group_name: groupName
            })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Falha na configuração');
        }

        // 2. Auto Login
        const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: adminEmail, senha: adminPassword })
        });

        if (loginResponse.ok) {
            window.location.href = '/static/admin.html';
        } else {
            // If auto-login fails, redirect to login page
            alert('Configuração concluída! Por favor, faça login.');
            window.location.href = '/login';
        }

    } catch (error) {
        console.error(error);
        errorMessage.textContent = error.message;
        setupButton.disabled = false;
        setupButton.textContent = 'Configurar e Acessar';
    }
});
