(function () {
  const API_BASE = 'http://127.0.0.1:5000/api/v1';
  const TOKEN_KEY = 'tekis_token';
  const USER_KEY = 'tekis_user';

  function getStoredToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  function saveStoredSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  const ACTIVE_CONVERSATION_KEY = 'tekis_active_conversation_id';

  function getActiveConversationId() {
    var value = sessionStorage.getItem(ACTIVE_CONVERSATION_KEY);
    return value ? Number(value) : null;
  }

  function setActiveConversationId(id) {
    if (id == null) sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    else sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, String(id));
  }

  function saveChatHistory() {
    // Compatibilité avec d'anciennes versions du frontend : l'historique est
    // désormais géré exclusivement par PostgreSQL.
  }

  function getChatHistory() {
    return [];
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
            ? 'API inaccessible. Démarrez le backend sur http://127.0.0.1:5000.'
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

  function groupSourcesByDocument(sources) {
    var grouped = {};
    (Array.isArray(sources) ? sources : []).forEach(function (source) {
      var key = String(source.document_version_id || source.document_id || source.original_filename || source.chunk_id || 'source');
      if (!grouped[key]) {
        grouped[key] = {
          document_id: source.document_id,
          document_version_id: source.document_version_id,
          document_title: source.document_title,
          original_filename: source.original_filename,
          file_type: source.file_type,
          department_name: source.department_name,
          pages: [],
        };
      }
      if (source.page != null && grouped[key].pages.indexOf(source.page) === -1) {
        grouped[key].pages.push(source.page);
      }
    });
    return Object.keys(grouped).map(function (key) { return grouped[key]; });
  }

  function openDocumentPreview(source) {
    var modal = document.getElementById('documentPreviewModal');
    var body = document.getElementById('documentPreviewBody');
    var title = document.getElementById('documentPreviewTitle');
    var meta = document.getElementById('documentPreviewMeta');
    if (!modal || !body || !title || !meta) return;

    var filename = source.original_filename || source.document_title || 'Document TEKIS';
    title.textContent = filename;
    meta.textContent = [
      source.document_title && source.document_title !== filename ? source.document_title : '',
      source.department_name || '',
      source.pages && source.pages.length ? 'Page' + (source.pages.length > 1 ? 's ' : ' ') + source.pages.join(', ') : '',
    ].filter(Boolean).join(' • ');
    body.innerHTML = '<div class="flex items-center gap-3 text-text-subtle py-8 justify-center"><span class="material-symbols-outlined animate-spin">progress_activity</span><span>Chargement du document…</span></div>';
    modal.hidden = false;
    document.body.classList.add('overflow-hidden');

    requestJson('/documents/versions/' + encodeURIComponent(source.document_version_id) + '/preview')
      .then(function (payload) {
        var data = (payload && payload.data) || {};
        var pages = Array.isArray(data.pages) ? data.pages : [];
        if (!pages.length) {
          body.innerHTML = '<div class="tk-document-empty">Aucun contenu textuel disponible pour cet aperçu.</div>';
          return;
        }
        body.innerHTML = pages.map(function (page) {
          var content = escapeHtml(page.content || '').replace(/\n/g, '<br>');
          return '<section class="tk-preview-page"><div class="tk-preview-page-label">PAGE ' + page.page + '</div><div class="tk-preview-content">' + content + '</div></section>';
        }).join('');
        if (data.truncated) {
          body.insertAdjacentHTML('beforeend', '<div class="tk-preview-notice">Aperçu tronqué pour conserver une consultation fluide. Le document source est intact.</div>');
        }
      })
      .catch(function (error) {
        body.innerHTML = '<div class="text-red-400 py-8">Impossible d afficher le document : ' + escapeHtml(error.message) + '</div>';
      });
  }

  function closeDocumentPreview() {
    var modal = document.getElementById('documentPreviewModal');
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('overflow-hidden');
  }

  function formatSources(sources) {
    if (!Array.isArray(sources) || sources.length === 0) {
      return '<div class="text-sm text-text-subtle">Aucune source détectée pour cette réponse.</div>';
    }

    var grouped = groupSourcesByDocument(sources);
    var cards = grouped.map(function (source, index) {
      var filename = source.original_filename || source.document_title || 'Document sans nom';
      var meta = [
        source.document_title && source.document_title !== filename ? source.document_title : '',
        source.department_name || '',
        source.pages && source.pages.length ? 'page' + (source.pages.length > 1 ? 's ' : ' ') + source.pages.join(', ') : '',
      ].filter(Boolean).join(' • ');

      return '<button type="button" class="tk-source-card" data-source-index="' + index + '" aria-label="Afficher ' + escapeHtml(filename) + '">' +
        '<span class="tk-source-icon material-symbols-outlined">description</span>' +
        '<span class="min-w-0 flex-1 text-left">' +
          '<span class="tk-source-name">' + escapeHtml(filename) + '</span>' +
          (meta ? '<span class="tk-source-meta">' + escapeHtml(meta) + '</span>' : '') +
        '</span>' +
        '<span class="tk-source-action">Afficher le document</span>' +
        '<span class="material-symbols-outlined tk-source-chevron">chevron_right</span>' +
      '</button>';
    }).join('');

    return '<div class="border-t border-border pt-4 mt-4"><div class="flex items-center justify-between gap-4 mb-3"><h4 class="tk-label-caps text-text-subtle">SOURCES UTILISÉES</h4><span class="tk-source-hint">Cliquer pour consulter</span></div><div class="tk-source-list" data-source-list>' + cards + '</div></div>';
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
    const confidence = data.confidence != null ? '<div class="tk-confidence">Confiance ' + Math.round(Number(data.confidence) * 100) + '%</div>' : '';
    const sources = formatSources(data.sources || []);

    addMessage('assistant', '<div class="flex items-center gap-2 mb-2"><span class="material-symbols-outlined text-primary filled">smart_toy</span><span class="tk-label-caps font-bold">ASSISTANT TEKIS</span></div>' + renderAnswerParagraphs(answer) + reason + confidence + sources, 'Réponse générée par le backend TEKIS');

    var container = document.getElementById('chatMessages');
    var lastAssistant = container ? container.lastElementChild : null;
    var list = lastAssistant ? lastAssistant.querySelector('[data-source-list]') : null;
    if (list) {
      var grouped = groupSourcesByDocument(data.sources || []);
      list.querySelectorAll('[data-source-index]').forEach(function (button) {
        button.addEventListener('click', function () {
          var index = Number(button.getAttribute('data-source-index'));
          if (grouped[index] && grouped[index].document_version_id != null) {
            openDocumentPreview(grouped[index]);
          }
        });
      });
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function createStreamingAssistantMessage() {
    const container = document.getElementById('chatMessages');
    if (!container) return null;
    const wrap = document.createElement('div');
    wrap.className = 'flex justify-start';
    const bubble = document.createElement('div');
    bubble.className = 'tk-bubble-ai';
    const inner = document.createElement('div');
    inner.innerHTML = '<div class="flex items-center gap-2 mb-2"><span class="material-symbols-outlined text-primary filled">smart_toy</span><span class="tk-label-caps font-bold">ASSISTANT TEKIS</span></div><div data-stream-answer class="tk-body-lg whitespace-pre-wrap"></div><div data-stream-extra></div>';
    bubble.appendChild(inner);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    return { wrap: wrap, answer: inner.querySelector('[data-stream-answer]'), extra: inner.querySelector('[data-stream-extra]') };
  }

  function renderStreamingSources(streamView, sources, confidence, reason) {
    if (!streamView || !streamView.extra) return;
    var reasonHtml = reason ? '<p class="tk-body-md text-text-muted mb-4">' + escapeHtml(reason) + '</p>' : '';
    var confidenceHtml = confidence != null ? '<div class="tk-confidence">Confiance ' + Math.round(Number(confidence) * 100) + '%</div>' : '';
    streamView.extra.innerHTML = reasonHtml + confidenceHtml + formatSources(sources || []);
    var grouped = groupSourcesByDocument(sources || []);
    streamView.extra.querySelectorAll('[data-source-index]').forEach(function (button) {
      button.addEventListener('click', function () {
        var index = Number(button.getAttribute('data-source-index'));
        if (grouped[index] && grouped[index].document_version_id != null) openDocumentPreview(grouped[index]);
      });
    });
  }

  function formatConversationDate(value) {
    if (!value) return '';
    try {
      return new Date(value).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: 'short',
      });
    } catch (error) {
      return '';
    }
  }

  function renderConversationNav(conversations) {
    var container = document.getElementById('conversationNav');
    if (!container) return;
    var activeId = getActiveConversationId();
    var items = (Array.isArray(conversations) ? conversations : []).slice(0, 20);
    container.innerHTML = items.map(function (conversation) {
      var active = Number(conversation.id) === Number(activeId);
      return '<a href="chat.html?conversation_id=' + encodeURIComponent(conversation.id) +
        '" class="tk-conversation-nav-item' + (active ? ' active' : '') + '">' +
        '<span class="material-symbols-outlined">chat_bubble</span>' +
        '<span class="truncate">' + escapeHtml(conversation.title || 'Nouvelle discussion') + '</span>' +
        '</a>';
    }).join('');
  }

  async function loadConversations() {
    var payload = await requestJson('/conversations');
    var conversations = payload.data && Array.isArray(payload.data.conversations)
      ? payload.data.conversations : [];
    renderConversationNav(conversations);
    return conversations;
  }

  function clearChatMessages() {
    var container = document.getElementById('chatMessages');
    if (!container) return;
    container.innerHTML = '<div class="text-center"><span class="tk-label-caps text-text-subtle">DISCUSSION</span></div>';
  }

  function renderStoredMessage(message) {
    var content = escapeHtml(message.content || '').replace(/\n/g, '<br>');
    if (message.role === 'user') {
      addMessage('user', '<p class="tk-body-lg text-text">' + content + '</p>', '');
      return;
    }
    addMessage('assistant',
      '<div class="flex items-center gap-2 mb-2"><span class="material-symbols-outlined text-primary filled">smart_toy</span><span class="tk-label-caps font-bold">ASSISTANT TEKIS</span></div>' +
      renderAnswerParagraphs(message.content || ''),
      '');
  }

  async function loadConversation(conversationId) {
    var payload = await requestJson('/conversations/' + encodeURIComponent(conversationId));
    var conversation = payload.data || {};
    setActiveConversationId(conversation.id);
    clearChatMessages();
    (conversation.messages || []).forEach(renderStoredMessage);
    var title = document.querySelector('[data-current-conversation-title]');
    if (title) title.textContent = conversation.title || 'Discussion';
    await loadConversations();
    return conversation;
  }

  async function streamChat(query, view) {
    const token = getStoredToken();
    const response = await fetch(API_BASE + '/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
      },
      body: JSON.stringify({ query: query, top_k: 5, conversation_id: getActiveConversationId() }),
    });

    if (!response.ok) {
      const data = await response.json().catch(function () { return {}; });
      throw new Error(data.error || data.message || 'Erreur de requête');
    }
    if (!response.body) throw new Error('Le navigateur ne supporte pas le streaming HTTP.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let answer = '';
    let metadata = {};

    function handleEvent(raw) {
      var eventName = 'message';
      var dataText = '';
      raw.split('\n').forEach(function (line) {
        if (line.indexOf('event:') === 0) eventName = line.slice(6).trim();
        if (line.indexOf('data:') === 0) dataText += line.slice(5).trim();
      });
      if (!dataText) return;
      var data;
      try { data = JSON.parse(dataText); } catch (error) { return; }
      if (eventName === 'conversation') {
        if (data.conversation_id != null) {
          setActiveConversationId(data.conversation_id);
          loadConversations().catch(function () {});
        }
      } else if (eventName === 'metadata') {
        metadata = data || {};
        if (metadata.conversation_id != null) {
          setActiveConversationId(metadata.conversation_id);
          loadConversations().catch(function () {});
        }
        renderStreamingSources(view, metadata.sources || [], metadata.confidence, metadata.reason);
      } else if (eventName === 'token') {
        answer += String(data.text || '');
        view.answer.textContent = answer;
        const container = document.getElementById('chatMessages');
        if (container) container.scrollTop = container.scrollHeight;
      } else if (eventName === 'done') {
        if (data.answer != null) answer = String(data.answer);
        view.answer.innerHTML = renderAnswerParagraphs(answer);
        renderStreamingSources(view, metadata.sources || [], metadata.confidence, metadata.reason);
      } else if (eventName === 'error') {
        throw new Error(data.error || 'Erreur pendant la génération');
      }
    }

    while (true) {
      const result = await reader.read();
      buffer += decoder.decode(result.value || new Uint8Array(), { stream: !result.done });
      var parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      parts.forEach(handleEvent);
      if (result.done) break;
    }
    if (buffer.trim()) handleEvent(buffer);
  }

  function mountChatPage() {
    const form = document.getElementById('chatForm');
    const messageField = document.getElementById('chatInput');
    const attachmentButton = document.querySelector('[data-context-upload]');
    if (!form) return;

    var previewModal = document.getElementById('documentPreviewModal');
    var previewClose = document.querySelector('[data-close-document-preview]');
    if (previewClose) previewClose.addEventListener('click', closeDocumentPreview);
    if (previewModal) {
      previewModal.addEventListener('click', function (event) {
        if (event.target === previewModal) closeDocumentPreview();
      });
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeDocumentPreview();
    });

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

    var params = new URLSearchParams(window.location.search);
    var requestedConversationId = params.get('conversation_id');
    var conversationLoad = requestedConversationId
      ? loadConversation(requestedConversationId)
      : (function () {
          setActiveConversationId(null);
          clearChatMessages();
          return loadConversations();
        })();
    conversationLoad.catch(function (error) {
      console.error('[TEKIS] Impossible de charger les conversations:', error);
    });

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

      var streamView = createStreamingAssistantMessage();
      streamChat(query, streamView)
        .catch(function (error) {
          if (streamView && streamView.answer) {
            streamView.answer.innerHTML = '<p class="tk-body-md text-text-muted">Erreur: ' + escapeHtml(error.message) + '</p>';
          } else {
            addMessage('assistant', '<p class="tk-body-md text-text-muted">Erreur: ' + escapeHtml(error.message) + '</p>', 'Backend non disponible');
          }
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

  async function mountHistoryPage() {
    var container = document.getElementById('historyList');
    var emptyState = document.getElementById('historyEmpty');
    if (!container) return;

    try {
      var conversations = await loadConversations();
      if (!conversations.length) {
        if (emptyState) emptyState.hidden = false;
        return;
      }
      if (emptyState) emptyState.hidden = true;
      container.innerHTML = conversations.map(function (conversation) {
        var date = formatConversationDate(conversation.updated_at || conversation.created_at);
        return '<a href="chat.html?conversation_id=' + encodeURIComponent(conversation.id) +
          '" class="tk-card p-5 block hover:shadow-md transition-shadow">' +
          '<div class="flex items-center justify-between gap-4 mb-2">' +
          '<span class="tk-label-caps">DISCUSSION</span>' +
          '<time class="text-xs text-text-subtle">' + escapeHtml(date) + '</time>' +
          '</div>' +
          '<h2 class="font-semibold text-lg text-text mb-1">' + escapeHtml(conversation.title || 'Nouvelle discussion') + '</h2>' +
          '<p class="tk-body-md text-text-subtle">Ouvrir cette conversation et reprendre l’échange</p>' +
          '</a>';
      }).join('');
    } catch (error) {
      if (emptyState) emptyState.hidden = false;
      if (container) container.innerHTML = '<div class="text-red-400">Impossible de charger l’historique : ' + escapeHtml(error.message) + '</div>';
    }
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
