(function () {
    function ensureCss() {
        const href = '/static/ui/nav.css';
        const existing = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).some(
            (l) => l.getAttribute('href') === href
        );
        if (existing) return;
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        document.head.appendChild(link);
    }

    function createNav() {
        const mount = document.getElementById('app-nav');
        if (!mount) return;
        if (mount.getAttribute('data-mounted') === 'true') return;

        const pathname = window.location.pathname || '/';
        const isChat = pathname === '/' || pathname.startsWith('/web');
        const isAdmin = pathname.startsWith('/admin');
        const isCreateAgent = pathname.startsWith('/create-agent');

        const nav = document.createElement('nav');
        nav.className = 'app-nav';

        const inner = document.createElement('div');
        inner.className = 'app-nav-inner';

        const brand = document.createElement('a');
        brand.className = 'app-brand';
        brand.href = '/';
        brand.textContent = 'SIA-Piauí';

        const links = document.createElement('div');
        links.className = 'app-links';

        const chat = document.createElement('a');
        chat.className = `app-link${isChat ? ' active' : ''}`;
        chat.href = '/';
        chat.textContent = 'Chat';

        const admin = document.createElement('a');
        admin.className = `app-link${isAdmin ? ' active' : ''}`;
        admin.href = '/admin';
        admin.textContent = 'Admin';

        const createAgent = document.createElement('a');
        createAgent.className = `app-link${isCreateAgent ? ' active' : ''}`;
        createAgent.href = '/create-agent';
        createAgent.textContent = 'Criar agente';

        const logout = document.createElement('button');
        logout.type = 'button';
        logout.className = 'app-link app-link-button';
        logout.textContent = 'Sair';
        logout.addEventListener('click', async () => {
            try {
                await fetch(`${window.location.origin}/api/auth/logout`, {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (e) {
            } finally {
                window.location.href = '/login';
            }
        });

        links.appendChild(chat);
        links.appendChild(admin);
        links.appendChild(createAgent);
        links.appendChild(logout);

        inner.appendChild(brand);
        inner.appendChild(links);
        nav.appendChild(inner);

        mount.appendChild(nav);
        mount.setAttribute('data-mounted', 'true');
    }

    ensureCss();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createNav);
    } else {
        createNav();
    }
})();

