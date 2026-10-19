/* 医疗知识图谱问答 · 前端逻辑 */
(function () {
  'use strict';

  const chat = document.getElementById('chat');
  const form = document.getElementById('ask-form');
  const input = document.getElementById('question');
  const sendBtn = document.getElementById('send');
  const welcome = document.getElementById('welcome');
  const examples = document.getElementById('examples');
  const statusEl = document.getElementById('db-status');

  const statsBtn = document.getElementById('stats-btn');
  const statsModal = document.getElementById('stats-modal');
  const statsBody = document.getElementById('stats-body');
  const statsClose = document.getElementById('stats-close');

  let busy = false;

  /* ---------- 工具 ---------- */
  function scrollToBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function addMessage(role, text, metaHtml) {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg--' + role;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '🧑' : '⚕';

    const bubbleWrap = document.createElement('div');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    bubbleWrap.appendChild(bubble);

    if (metaHtml) {
      const meta = document.createElement('div');
      meta.className = 'meta';
      meta.innerHTML = metaHtml;
      bubbleWrap.appendChild(meta);
    }

    if (role === 'user') {
      wrap.appendChild(bubbleWrap);
      wrap.appendChild(avatar);
    } else {
      wrap.appendChild(avatar);
      wrap.appendChild(bubbleWrap);
    }

    chat.appendChild(wrap);
    scrollToBottom();
    return bubble;
  }

  function addTyping() {
    const wrap = document.createElement('div');
    wrap.className = 'msg msg--bot';
    wrap.dataset.typing = '1';

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '⚕';

    const bubbleWrap = document.createElement('div');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
    bubbleWrap.appendChild(bubble);

    wrap.appendChild(avatar);
    wrap.appendChild(bubbleWrap);
    chat.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function removeTyping() {
    chat.querySelectorAll('[data-typing="1"]').forEach(n => n.remove());
  }

  function hideWelcome() {
    if (welcome && welcome.parentNode) welcome.remove();
  }

  /* ---------- 初始化 ---------- */
  async function loadExamples() {
    try {
      const res = await fetch('/api/examples');
      const data = await res.json();
      (data.examples || []).forEach(q => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'example-btn';
        btn.textContent = q;
        btn.addEventListener('click', () => {
          input.value = q;
          input.focus();
          submit();
        });
        examples.appendChild(btn);
      });
    } catch (_) {
      /* 示例加载失败不影响主流程 */
    }
  }

  async function checkStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.ok) {
        statusEl.className = 'status status--ok';
        statusEl.textContent = '数据库已连接';
        statusEl.title = data.message || '';
      } else {
        statusEl.className = 'status status--err';
        statusEl.textContent = '数据库未连接';
        statusEl.title = data.message || '';
      }
    } catch (_) {
      statusEl.className = 'status status--err';
      statusEl.textContent = '状态未知';
    }
  }

  /* ---------- 提问 ---------- */
  async function submit() {
    const question = input.value.trim();
    if (!question || busy) return;

    hideWelcome();
    addMessage('user', question);
    input.value = '';
    busy = true;
    sendBtn.disabled = true;
    const typing = addTyping();

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      const data = await res.json();
      removeTyping();

      if (!data.ok) {
        addMessage('bot', '出错了：' + (data.error || '未知错误，请确认 Neo4j 已启动'));
      } else {
        let meta = '';
        if (data.intents && data.intents.length) {
          meta = '<code>' + escapeHtml(data.intents.join(' / ')) + '</code>';
          const ents = Object.keys(data.entities || {});
          if (ents.length) meta += '识别实体：' + escapeHtml(ents.join('、'));
        }
        addMessage('bot', data.answer, meta);
      }
    } catch (err) {
      removeTyping();
      addMessage('bot', '请求失败：' + err.message);
    } finally {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  /* ---------- 统计弹窗 ---------- */
  async function openStats() {
    statsModal.hidden = false;
    statsBody.textContent = '加载中…';
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      if (!data.ok) {
        statsBody.textContent = '读取失败：' + (data.error || '未知错误');
        return;
      }
      let html = '<table>';
      (data.labels || []).forEach(item => {
        html += '<tr><td>' + escapeHtml(item.label) + '</td><td>' + escapeHtml(item.count) + '</td></tr>';
      });
      html += '<tr><td><b>关系总数</b></td><td><b>' + escapeHtml(data.relations) + '</b></td></tr>';
      html += '</table>';
      statsBody.innerHTML = html;
    } catch (err) {
      statsBody.textContent = '请求失败：' + err.message;
    }
  }

  statsBtn.addEventListener('click', openStats);
  statsClose.addEventListener('click', () => { statsModal.hidden = true; });
  statsModal.addEventListener('click', e => {
    if (e.target === statsModal) statsModal.hidden = true;
  });

  form.addEventListener('submit', e => {
    e.preventDefault();
    submit();
  });

  /* 启动 */
  loadExamples();
  checkStatus();
})();
