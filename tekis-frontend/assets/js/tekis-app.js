(function () {
  const API_BASE = '/api/v1';
  const TOKEN_KEY = 'tekis_token';
  const USER_KEY = 'tekis_user';

  function getStoredToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  function saveStoredSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function saveChatHistory(role, content) {
    var history;
    try {
      history = JSON.parse(localStorage.getItem('tekis_chat_history') || '[]');
    } catch (error) {
      history = [];
    }
    history.push({ role: role, content: String(content), at: new Date().toISOString() });
    localStorage.setItem('tekis_chat_history', JSON.stringify(history.slice(-50)));
  }

  function getChatHistory() {
    try {
      return JSON.parse(localStorage.getItem('tekis_chat_history') || '[]');
    } catch (error) {
      return [];
    }
  }

  function clearStoredSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function getStoredUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch (error) {
      return null;
    }
  }

  function requestJson(path, options) {
    const token = getStoredToken();
    const headers = Object.assign({ 'Content-Type': 'application/json' }, (options && options.headers) || {});
    if (token) {
      headers.Authorization = 'Bearer ' + token;
    }

    return fetch(API_BASE + path, Object.assign({
      headers: headers,
    }, options || {})).then(async function (response) {
      const data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        throw new Error(data.error || data.message || 'Erreur de requête');
      }
      return data;
    });
  }

  function requestMultipart(path, formData) {
    var headers = {};
    var token = getStoredToken();
    if (token) headers.Authorization = 'Bearer ' + token;
    return fetch(API_BASE + path, { method: 'POST', headers: headers, body: formData }).then(async function (response) {
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(data.error || data.message || 'Erreur d upload');
      return data;
    });
  }

  function setStatusMessage(message, isError) {
    const status = document.getElementById('loginStatus');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('text-red-500', !!isError);
    status.classList.toggle('text-green-500', !isError);
  }

  function mountLoginPage() {
    const form = document.getElementById('loginForm');
    if (!form) return;

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const submitButton = form.querySelector('button[type="submit"]');

      if (!email || !password) {
        setStatusMessage('Veuillez renseigner votre email et votre mot de passe.', true);
        return;
      }

      if (submitButton) submitButton.disabled = true;
      setStatusMessage('Connexion en cours...', false);

      requestJson('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email, password: password }),
      })
        .then(function (payload) {
          const user = payload.data && payload.data.user ? payload.data.user : { email: email };
          const token = payload.data && payload.data.access_token ? payload.data.access_token : '';
          saveStoredSession(token, user);
          window.location.href = 'chat.html';
        })
        .catch(function (error) {
          var message = error.message === 'Failed to fetch'
            ? 'API inaccessible. Vérifiez que les services TEKIS sont démarrés.'
            : (error.message || 'Connexion impossible.');
          setStatusMessage(message, true);
        })
        .finally(function () {
          if (submitButton) submitButton.disabled = false;
        });
    });
  }

  function addMessage(role, content, meta) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    const wrap = document.createElement('div');
    wrap.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';

    const bubble = document.createElement('div');
    bubble.className = role === 'user' ? 'tk-bubble-user' : 'tk-bubble-ai';

    const inner = document.createElement('div');
    inner.innerHTML = content;

    bubble.appendChild(inner);
    if (meta) {
      const footer = document.createElement('div');
      footer.className = 'mt-3 text-xs text-text-subtle';
      footer.textContent = meta;
      bubble.appendChild(footer);
    }

    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;

    if (role === 'user' || role === 'assistant') {
      saveChatHistory(role, content.replace(/<[^>]*>/g, ''));
    }
  }

  function formatSources(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
      return '<div class="text-sm text-text-subtle">Aucune source détectée pour cette réponse.</div>';
    }

    const chips = sources.map(function (source) {
      const docVersion = source.document_version_id != null ? ' • v' + source.document_version_id : '';
      const distance = source.distance != null ? ' • score ' + Number(source.distance).toFixed(3) : '';
      return '<span class="tk-source-chip"><span class="material-symbols-outlined text-[16px]">description</span>chunk #' + (source.chunk_id || 'n/a') + docVersion + distance + '</span>';
    }).join('');

    return '<div class="border-t border-border pt-4"><h4 class="tk-label-caps text-text-subtle mb-3">SOURCES UTILISÉES</h4><div class="flex flex-wrap gap-2">' + chips + '</div></div>';
  }

  function renderAnswerParagraphs(value) {
    var text = String(value || '').replace(/\*{3,}/g, '').trim();
    return text.split(/\n\s*\n/).filter(Boolean).map(function (block) {
      var html = escapeHtml(block.trim())
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\s*[-*]\s+/gm, '');
      return '<p class="tk-body-lg mb-4">' + html.replace(/\n/g, '<br>') + '</p>';
    }).join('');
  }

  function renderAssistantReply(payload) {
    const data = (payload && payload.data) || {};
    const answer = data.answer || 'Aucune réponse disponible.';
    const reason = data.reason ? '<p class="tk-body-md text-text-muted mb-4">' + escapeHtml(data.reason) + '</p>' : '';
    const confidence = data.confidence != null ? '<div class="mt-3 text-xs text-text-subtle">Confiance: ' + Number(data.confidence).toFixed(3) + '</div>' : '';
    const sources = formatSources(data.sources || []);

    addMessage('assistant', '<div class="flex items-center gap-2 mb-2"><span class="material-symbols-outlined text-primary filled">smart_toy</span><span class="tk-label-caps font-bold">ASSISTANT TEKIS</span></div>' + renderAnswerParagraphs(answer) + reason + confidence + sources, 'Réponse générée par le backend TEKIS');
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function mountChatPage() {
    const form = document.getElementById('chatForm');
    const messageField = document.getElementById('chatInput');
    const attachmentButton = document.querySelector('[data-context-upload]');
    if (!form) return;

    if (!getStoredToken()) {
      window.location.href = 'login.html';
      return;
    }

    const user = getStoredUser();
    const userLabel = document.querySelector('[data-user-label]');
    const userEmail = document.querySelector('[data-user-email]');
    if (userLabel && user && user.name) {
      userLabel.textContent = user.name;
    }
    if (userEmail && user && user.email) {
      userEmail.textContent = user.email;
    }

    if (attachmentButton) {
      var fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = '.pdf,.docx,.xlsx,.txt';
      fileInput.hidden = true;
      document.body.appendChild(fileInput);
      attachmentButton.addEventListener('click', function () { fileInput.click(); });
      fileInput.addEventListener('change', function () {
        var file = fileInput.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        formData.append('title', file.name.replace(/\.[^.]+$/, ''));
        formData.append('classification', 'chat-context');
        attachmentButton.disabled = true;
        requestMultipart('/ingestion', formData).then(function (payload) {
          addMessage('assistant', '<p class="tk-body-md">Le fichier <strong>' + escapeHtml(file.name) + '</strong> a été ajouté comme contexte. Il sera utilisé après son indexation.</p>', 'Contexte ajouté');
          return requestJson('/embeddings/reindex', { method: 'POST', body: '{}' });
        }).catch(function (error) {
          addMessage('assistant', '<p class="tk-body-md">Impossible d ajouter ce fichier : ' + escapeHtml(error.message) + '</p>', 'Upload échoué');
        }).finally(function () { attachmentButton.disabled = false; fileInput.value = ''; });
      });
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      const query = (messageField ? messageField.value : '').trim();
      if (!query) return;

      addMessage('user', '<p class="tk-body-lg text-text">' + escapeHtml(query) + '</p>', 'Question envoyée');
      if (messageField) messageField.value = '';

      const submitButton = form.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;

      requestJson('/chat', {
        method: 'POST',
        body: JSON.stringify({ query: query, top_k: 5 }),
      })
        .then(function (payload) {
          renderAssistantReply(payload);
        })
        .catch(function (error) {
          addMessage('assistant', '<p class="tk-body-md text-text-muted">Erreur: ' + escapeHtml(error.message) + '</p>', 'Backend non disponible');
        })
        .finally(function () {
          if (submitButton) submitButton.disabled = false;
          if (messageField) messageField.focus();
        });
    });
  }

  function mountProtectedShell() {
    if (!getStoredToken()) {
      window.location.href = 'login.html';
      return false;
    }

    var user = getStoredUser() || {};
    document.querySelectorAll('[data-user-label]').forEach(function (element) {
      element.textContent = user.name || user.email || 'Utilisateur';
    });
    document.querySelectorAll('[data-user-email]').forEach(function (element) {
      element.textContent = user.email || '';
    });
    document.querySelectorAll('[data-user-role]').forEach(function (element) {
      element.textContent = user.role || 'Utilisateur';
    });
    return true;
  }

  function mountHistoryPage() {
    var container = document.getElementById('historyList');
    var emptyState = document.getElementById('historyEmpty');
    if (!container) return;

    var history = getChatHistory();
    if (!history.length) {
      if (emptyState) emptyState.hidden = false;
      return;
    }
    if (emptyState) emptyState.hidden = true;
    container.innerHTML = history.slice().reverse().map(function (item) {
      var date = new Date(item.at).toLocaleString('fr-FR');
      return '<article class="tk-card p-5"><div class="flex items-center justify-between gap-4 mb-2"><span class="tk-label-caps">' +
        (item.role === 'user' ? 'QUESTION' : 'RÉPONSE TEKIS') +
        '</span><time class="text-xs text-text-subtle">' + escapeHtml(date) +
        '</time></div><p class="tk-body-md">' + escapeHtml(item.content) + '</p></article>';
    }).join('');
  }

  function mountDocumentationPage() {
    var status = document.getElementById('apiStatus');
    if (!status) return;
    requestJson('/health', { headers: {} })
      .then(function (payload) {
        status.textContent = payload.data && payload.data.status === 'ok' ? 'API opérationnelle' : 'API disponible';
        status.className = 'text-green-600';
      })
      .catch(function () {
        status.textContent = 'API indisponible';
        status.className = 'text-red-500';
      });

    var user = getStoredUser() || {};
    var panel = document.getElementById('adminUploadPanel');
    var form = document.getElementById('documentationUploadForm');
    if (panel && user.role === 'admin') panel.hidden = false;
    if (!form || user.role !== 'admin') return;
    var departmentSelect = document.getElementById('departmentSelect');
    requestJson('/admin/departments').then(function (payload) {
      departmentSelect.innerHTML = '<option value="">Choisir un département</option>' + (payload.data.departments || []).map(function (department) {
        return '<option value="' + department.id + '">' + escapeHtml(department.name) + '</option>';
      }).join('');
    });
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var status = document.getElementById('documentationStatus');
      var formData = new FormData(form);
      formData.append('source', 'enterprise');
      if (!formData.get('department_id')) { status.textContent = 'Choisissez un département.'; return; }
      status.textContent = 'Upload et ingestion en cours...';
      requestMultipart('/ingestion', formData).then(function (payload) {
        status.textContent = 'Document ingéré : ' + payload.data.num_chunks + ' chunk(s). Indexation en cours...';
        return requestJson('/embeddings/reindex', { method: 'POST', body: '{}' });
      }).then(function (payload) {
        status.textContent += ' ' + (payload.data ? payload.data.num_chunks_indexed : 0) + ' embedding(s) créé(s).';
        form.reset();
      }).catch(function (error) { status.textContent = error.message || 'Upload impossible.'; });
    });
  }

  function mountSettingsPage() {
    var form = document.getElementById('settingsForm');
    if (!form) return;
    var theme = localStorage.getItem('tekis_theme') || 'system';
    var themeField = form.querySelector('[name="theme"]');
    if (themeField) themeField.value = theme;
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (themeField) localStorage.setItem('tekis_theme', themeField.value);
      var status = document.getElementById('settingsStatus');
      if (status) status.textContent = 'Préférences enregistrées localement.';
    });
  }

  function mountAdministrationPage() {
    var button = document.querySelector('[data-reindex]');
    var roleButton = document.querySelector('[data-role-create]');
    var roleBody = document.getElementById('rolesTableBody');
    if (roleBody) {
      requestJson('/admin/roles').then(function (payload) {
        roleBody.innerHTML = (payload.data.roles || []).map(function (role) {
          return '<tr><td class="font-semibold">' + escapeHtml(role.name) + '</td><td><span class="tk-tag">ID ' + role.id + '</span></td><td>' +
            escapeHtml(role.description || '') + '</td><td class="text-right"><button class="tk-icon-btn" data-role-edit="' + role.id + '" title="Modifier"><span class="material-symbols-outlined text-sm">edit</span></button> <button class="tk-icon-btn" data-role-delete="' + role.id + '" title="Supprimer"><span class="material-symbols-outlined text-sm">delete</span></button></td></tr>';
        }).join('');
        roleBody.querySelectorAll('[data-role-edit]').forEach(function (editButton) {
          editButton.addEventListener('click', function () {
            var description = window.prompt('Nouvelle description du rôle :');
            if (description === null) return;
            requestJson('/admin/roles/' + editButton.dataset.roleEdit, { method: 'PATCH', body: JSON.stringify({ description: description }) }).then(function () { window.location.reload(); });
          });
        });
        roleBody.querySelectorAll('[data-role-delete]').forEach(function (deleteButton) {
          deleteButton.addEventListener('click', function () {
            if (!window.confirm('Supprimer ce rôle ?')) return;
            requestJson('/admin/roles/' + deleteButton.dataset.roleDelete, { method: 'DELETE' }).then(function () { window.location.reload(); });
          });
        });
      }).catch(function (error) {
        if (document.getElementById('adminStatus')) document.getElementById('adminStatus').textContent = error.message;
      });
    }
    if (roleButton) roleButton.addEventListener('click', function () {
      var name = window.prompt('Nom du nouveau rôle :');
      if (!name) return;
      var description = window.prompt('Description du rôle :') || '';
      requestJson('/admin/roles', { method: 'POST', body: JSON.stringify({ name: name, description: description }) }).then(function () { window.location.reload(); });
    });
    var adminFilter = document.querySelector('[data-admin-filter]');
    if (adminFilter && roleBody) adminFilter.addEventListener('click', function () {
      var term = window.prompt('Rechercher un rôle :');
      if (term === null) return;
      roleBody.querySelectorAll('tr').forEach(function (row) { row.hidden = term && row.textContent.toLowerCase().indexOf(term.toLowerCase()) === -1; });
    });
    var adminNext = document.querySelector('[data-admin-next]');
    if (adminNext) adminNext.addEventListener('click', function () {
      var status = document.getElementById('adminStatus');
      if (status) status.textContent = 'Tous les rôles disponibles sont affichés.';
      adminNext.disabled = true;
    });
    if (!button) return;
    button.addEventListener('click', function () {
      var status = document.getElementById('adminStatus');
      button.disabled = true;
      if (status) status.textContent = 'Réindexation en cours...';
      requestJson('/embeddings/reindex', { method: 'POST', body: '{}' })
        .then(function (payload) {
          var count = payload.data ? payload.data.num_chunks_indexed : 0;
          if (status) status.textContent = count + ' chunk(s) réindexé(s).';
        })
        .catch(function (error) {
          if (status) status.textContent = error.message || 'Réindexation impossible.';
        })
        .finally(function () { button.disabled = false; });
    });
  }

  function mountAclPage() {
    var body = document.getElementById('aclTableBody');
    if (!body) return;
    requestJson('/admin/roles').then(function (payload) {
      var roleCount = document.getElementById('aclRoleCount');
      if (roleCount) roleCount.textContent = (payload.data.roles || []).length;
    });
    function loadAcls() { return requestJson('/admin/permissions').then(function (payload) {
      var resources = payload.data.permissions || [];
      var resourceCount = document.getElementById('aclResourceCount');
      if (resourceCount) resourceCount.textContent = resources.length;
      body.innerHTML = (payload.data.permissions || []).map(function (permission) {
        return '<tr><td class="font-semibold">ACL #' + permission.id + '</td><td><span class="tk-tag">' + (permission.document_id || ('version ' + permission.document_version_id)) + '</span></td><td>' + escapeHtml((permission.allowed_roles || []).join(', ') || 'Aucun rôle') + '</td><td>' + (permission.allowed_users || []).length + '</td><td class="text-right"><button class="tk-icon-btn" data-acl-edit="' + permission.id + '" title="Modifier"><span class="material-symbols-outlined text-sm">edit</span></button> <button class="tk-icon-btn" data-acl-delete="' + permission.id + '" title="Supprimer"><span class="material-symbols-outlined text-sm">delete</span></button></td></tr>';
      }).join('');
      body.querySelectorAll('[data-acl-delete]').forEach(function (deleteButton) {
        deleteButton.addEventListener('click', function () {
          if (!window.confirm('Supprimer cette ACL ?')) return;
          requestJson('/admin/permissions/' + deleteButton.dataset.aclDelete, { method: 'DELETE' }).then(function () { window.location.reload(); });
        });
      });
      body.querySelectorAll('[data-acl-edit]').forEach(function (editButton) {
        editButton.addEventListener('click', function () {
          var roles = window.prompt('Rôles autorisés, séparés par des virgules :');
          if (roles === null) return;
          requestJson('/admin/permissions/' + editButton.dataset.aclEdit, { method: 'PATCH', body: JSON.stringify({ allowed_roles: roles.split(',').map(function (role) { return role.trim(); }).filter(Boolean) }) }).then(loadAcls);
        });
      });
    }); }
    loadAcls();
    var createButton = document.querySelector('[data-acl-create]');
    if (createButton) createButton.addEventListener('click', function () {
      var documentId = window.prompt('ID du document à protéger :');
      if (!documentId) return;
      var roles = window.prompt('Rôles autorisés, séparés par des virgules :') || '';
      requestJson('/admin/permissions', { method: 'POST', body: JSON.stringify({ document_id: Number(documentId), allowed_roles: roles.split(',').map(function (role) { return role.trim(); }).filter(Boolean) }) }).then(loadAcls);
    });
    var filterButton = document.querySelector('[data-acl-filter]');
    if (filterButton) filterButton.addEventListener('click', function () {
      var term = window.prompt('Texte à rechercher dans les ACL :');
      if (term === null) return;
      body.querySelectorAll('tr').forEach(function (row) { row.hidden = term && row.textContent.toLowerCase().indexOf(term.toLowerCase()) === -1; });
    });
  }

  function mountCommonActions() {
    document.querySelectorAll('button').forEach(function (button) {
      var icon = button.querySelector('.material-symbols-outlined');
      var iconName = icon ? icon.textContent.trim() : '';
      if (iconName === 'notifications') {
        button.addEventListener('click', function () { window.alert('Aucune nouvelle notification.'); });
      }
      if (iconName === 'account_circle') {
        button.addEventListener('click', function () { window.location.href = 'parametres.html'; });
      }
      if (button.textContent.indexOf('Connexion SSO') !== -1) {
        button.addEventListener('click', function () { setStatusMessage('La connexion SSO n’est pas configurée sur cet environnement.', true); });
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const page = document.body.getAttribute('data-page');
    if (page === 'login') mountLoginPage();
    if (page !== 'login' && page !== 'landing' && !mountProtectedShell()) return;
    if (page === 'chat') mountChatPage();
    if (page === 'history') mountHistoryPage();
    if (page === 'documentation') mountDocumentationPage();
    if (page === 'settings') mountSettingsPage();
    if (page === 'administration') mountAdministrationPage();
    if (page === 'acl') mountAclPage();
    mountCommonActions();

    const logoutButton = document.querySelector('[data-logout]');
    if (logoutButton) {
      logoutButton.addEventListener('click', function () {
        clearStoredSession();
        window.location.href = 'login.html';
      });
    }
  });
})();
