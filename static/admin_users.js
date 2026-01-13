
// --- GERENCIAMENTO DE USUÁRIOS E GRUPOS ---

const usersSection = document.getElementById('users-section');
const usersTableBody = document.querySelector('#users-table tbody');
const userModal = document.getElementById('user-modal');
const createUserForm = document.getElementById('create-user-form');
const userGroupSelect = document.getElementById('user-group');
const groupsModal = document.getElementById('groups-modal');
const groupsList = document.getElementById('groups-list');

// Close modals
const closeUserModal = document.getElementById('user-modal-close');
const closeGroupsModal = document.getElementById('groups-modal-close');

closeUserModal.addEventListener('click', () => userModal.style.display = 'none');
closeGroupsModal.addEventListener('click', () => groupsModal.style.display = 'none');
window.addEventListener('click', (e) => {
    if (e.target === userModal) userModal.style.display = 'none';
    if (e.target === groupsModal) groupsModal.style.display = 'none';
});

// Create User
createUserForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('user-email').value;
    const senha = document.getElementById('user-password').value;
    const nivel = document.getElementById('user-level').value;
    const grupoId = document.getElementById('user-group').value;

    try {
        const response = await fetch(`${API_BASE_URL}/api/users/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, senha, nivel, grupoId })
        });

        if (response.ok) {
            alert('Usuário criado com sucesso!');
            userModal.style.display = 'none';
            createUserForm.reset();
            loadUsers();
        } else {
            const err = await response.json();
            alert(`Erro: ${err.detail || 'Falha ao criar usuário'}`);
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao conectar com o servidor');
    }
});

// Create Group
document.getElementById('create-group-btn').addEventListener('click', async () => {
    const nome = document.getElementById('new-group-name').value;
    if (!nome) return alert('Digite o nome do grupo');

    try {
        const response = await fetch(`${API_BASE_URL}/api/groups/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome, descricao: `Grupo ${nome}` })
        });
        if (response.ok) {
            document.getElementById('new-group-name').value = '';
            loadGroupsList(); // Refresh list inside modal
            // Also refresh dropdown in user creation
            loadGroupsDropdown();
        } else {
            alert('Erro ao criar grupo');
        }
    } catch (e) {
        console.error(e);
    }
});

async function checkUserPermissions() {
    try {
        // Verify current user info
        const response = await fetch(`${API_BASE_URL}/api/auth/me`);
        if (response.ok) {
            const user = await response.json();
            if (user.nivel === 'ADMIN_GERAL') {
                usersSection.style.display = 'block';
                loadUsers();
            }
        }
    } catch (e) {
        console.error('Erro ao verificar permissões', e);
    }
}

async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/users/`);
        if (!response.ok) return;
        const users = await response.json();

        usersTableBody.innerHTML = '';
        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${escapeHtml(u.email)}</td>
                <td>${u.nivel}</td>
                <td>${u.grupo ? escapeHtml(u.grupo.nome) : '-'}</td>
                <td>
                    <button class="btn btn-danger btn-small" onclick="deleteUser('${u.id}')">Excluir</button>
                </td>
            `;
            usersTableBody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
    }
}

async function loadGroupsDropdown() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/groups/`);
        const groups = await response.json();
        userGroupSelect.innerHTML = '<option value="">Selecione...</option>';
        groups.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.nome;
            userGroupSelect.appendChild(opt);
        });
    } catch (e) { console.error(e); }
}

async function loadGroupsList() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/groups/`);
        const groups = await response.json();
        groupsList.innerHTML = '';
        groups.forEach(g => {
            const li = document.createElement('li');
            li.textContent = g.nome;
            groupsList.appendChild(li);
        });
    } catch (e) { console.error(e); }
}

async function deleteUser(id) {
    if (!confirm('Excluir usuário?')) return;
    await fetch(`${API_BASE_URL}/api/users/${id}`, { method: 'DELETE' });
    loadUsers();
}

window.showCreateUserModal = () => {
    loadGroupsDropdown();
    userModal.style.display = 'block';
};

window.showGroupsModal = () => {
    loadGroupsList();
    groupsModal.style.display = 'block';
};
window.deleteUser = deleteUser;

// Add initialization
document.addEventListener('DOMContentLoaded', () => {
    checkUserPermissions();
});
