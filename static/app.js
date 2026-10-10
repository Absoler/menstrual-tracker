const API = '/api';

const OPTIONS = {
  flow: [
    ['none', '无'], ['spotting', '点滴'], ['light', '少量'],
    ['medium', '中量'], ['heavy', '大量'],
  ],
  colors: [
    ['bright_red', '鲜红'], ['dark_red', '暗红'], ['pink', '粉色'],
    ['brown', '棕褐'], ['black', '黑色'], ['orange', '橙色'], ['grey', '灰色'],
  ],
  clots: [
    ['none', '无'], ['small', '小血块'], ['large', '大血块（≥2.5cm）'],
  ],
  pain: [
    ['none', '无'], ['mild', '轻度'], ['moderate', '中度'], ['severe', '重度'],
  ],
  symptoms: [
    ['bloating', '腹胀'], ['headache', '头痛'], ['breast_tenderness', '乳房胀痛'],
    ['nausea', '恶心'], ['fatigue', '疲劳'], ['diarrhea', '腹泻'],
    ['constipation', '便秘'], ['appetite_change', '食欲变化'],
    ['acne', '痤疮'], ['insomnia', '失眠'],
  ],
  mood: [
    ['calm', '平静'], ['happy', '开心'], ['anxious', '焦虑'],
    ['irritable', '易怒'], ['sad', '低落'], ['tired', '疲惫'],
  ],
};

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

const state = {
  token: localStorage.getItem('token'),
  username: localStorage.getItem('username') || '',
  authMode: 'login',
  month: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  records: new Map(),
  predictions: null,
  notifications: [],
  editingDate: null,
};

function dateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function monthKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function show(id) {
  document.getElementById(id).classList.remove('hidden');
}

function hide(id) {
  document.getElementById(id).classList.add('hidden');
}

function fmtErrorDetail(detail) {
  if (!detail) return "请求失败";
  if (Array.isArray(detail)) {
    return detail.map((e) => {
      const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '';
      return field ? `${field}: ${e.msg}` : e.msg;
    })
    .join('; ');
  }
  return detail;
}

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(fmtErrorDetail(data.detail));
  return data;
}

/* ---------- 登录 / 注册 ---------- */

function setAuthError(msg) {
  document.getElementById('auth-error').textContent = msg || '';
}

function toggleAuthMode() {
  state.authMode = state.authMode === 'login' ? 'register' : 'login';
  document.getElementById('auth-title').textContent =
    state.authMode === 'login' ? '登录' : '注册';
  document.getElementById('auth-submit').textContent =
    state.authMode === 'login' ? '登录' : '注册';
  document.getElementById('auth-toggle').textContent =
    state.authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录';
  setAuthError('');
}

async function submitAuth(e) {
  e.preventDefault();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  setAuthError('');
  try {
    const path = state.authMode === 'login' ? '/auth/login' : '/auth/register';
    const data = await api(path, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    state.token = data.token;
    state.username = data.username;
    localStorage.setItem('token', state.token);
    localStorage.setItem('username', state.username);
    showApp();
  } catch (err) {
    setAuthError(err.message);
  }
}

function logout() {
  state.token = null;
  state.username = '';
  localStorage.removeItem('token');
  localStorage.removeItem('username');
  hide('app-view');
  show('auth-view');
}

/* ---------- 日历 ---------- */

async function loadMonth() {
  const data = await api(`/records?month=${monthKey(state.month)}`);
  state.records = new Map(data.records.map((r) => [r.date, r]));
  renderCalendar();
  await refreshPredictions();
}

function renderCalendar() {
  const grid = document.getElementById('calendar-grid');
  grid.innerHTML = '';
  WEEKDAYS.forEach((w) => {
    const head = document.createElement('div');
    head.className = 'cal-head';
    head.textContent = w;
    grid.appendChild(head);
  });

  const year = state.month.getFullYear();
  const month = state.month.getMonth();
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // 周一为第一列
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevDays = new Date(year, month, 0).getDate();
  const todayKey = dateKey(new Date());

  const addCell = (d, cls) => {
    const cell = document.createElement('div');
    cell.className = `cal-cell ${cls}`;
    const key = dateKey(d);
    const isFuture = key > todayKey;
    const rec = state.records.get(key);
    if (rec && rec.flow !== 'none') {
      cell.classList.add('has-flow', `flow-${rec.flow}`);
      cell.title = `经量：${labelOf('flow', rec.flow)}`;
    }
    const num = document.createElement('div');
    num.className = 'cal-num';
    num.textContent = d.getDate();
    cell.appendChild(num);
    if (key === todayKey) cell.classList.add('today');
    if (cls !== 'other-month') {
      cell.dataset.date = key;
      if (isFuture) {
        cell.classList.add('future');
      } else {
        cell.addEventListener('click', () => openDetail(key));
      }
    }
    grid.appendChild(cell);
  };

  for (let i = offset - 1; i >= 0; i--) {
    addCell(new Date(year, month - 1, prevDays - i), 'other-month');
  }
  for (let day = 1; day <= daysInMonth; day++) {
    addCell(new Date(year, month, day), '');
  }
  const used = offset + daysInMonth;
  const trailing = used % 7 === 0 ? 0 : 7 - (used % 7);
  for (let day = 1; day <= trailing; day++) {
    addCell(new Date(year, month + 1, day), 'other-month');
  }

  document.getElementById('month-label').textContent = `${year}年${month + 1}月`;
}

function labelOf(field, value) {
  const item = OPTIONS[field].find(([v]) => v === value);
  return item ? item[1] : value;
}

/* ---------- 编辑弹窗 ---------- */

function fieldGroup(name, label, options, type, value) {
  const wrap = document.createElement('div');
  wrap.className = 'field';
  const title = document.createElement('div');
  title.className = 'field-label';
  title.textContent = label;
  wrap.appendChild(title);

  if (type === 'select') {
    const select = document.createElement('select');
    select.name = name;
    options.forEach(([v, text]) => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = text;
      if (v === value) opt.selected = true;
      select.appendChild(opt);
    });
    wrap.appendChild(select);
  } else {
    const box = document.createElement('div');
    box.className = 'chips';
    options.forEach(([v, text]) => {
      const labelEl = document.createElement('label');
      labelEl.className = 'chip';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.name = name;
      input.value = v;
      if ((value || []).includes(v)) input.checked = true;
      labelEl.appendChild(input);
      labelEl.appendChild(document.createTextNode(text));
      box.appendChild(labelEl);
    });
    wrap.appendChild(box);
  }
  return wrap;
}

function textField(name, label, value, textarea) {
  const wrap = document.createElement('div');
  wrap.className = 'field';
  const title = document.createElement('div');
  title.className = 'field-label';
  title.textContent = label;
  const input = document.createElement(textarea ? 'textarea' : 'input');
  input.name = name;
  input.value = value || '';
  if (!textarea) input.type = 'text';
  wrap.appendChild(title);
  wrap.appendChild(input);
  return wrap;
}

const DETAIL_FIELDS = [
  { key: 'flow', label: '经量', type: 'select' },
  { key: 'colors', label: '颜色', type: 'multi' },
  { key: 'clots', label: '血块', type: 'select' },
  { key: 'pain', label: '疼痛', type: 'select' },
  { key: 'symptoms', label: '症状', type: 'multi' },
  { key: 'mood', label: '情绪', type: 'multi' },
  { key: 'medication', label: '用药', type: 'text' },
  { key: 'notes', label: '备注', type: 'text' },
];

function openDetail(date) {
  state.editingDate = date;
  const rec = state.records.get(date) || {};
  document.getElementById('editor-title').textContent = date;

  const content = document.getElementById('detail-content');
  content.innerHTML = '';

  const hasAny = DETAIL_FIELDS.some((f) => {
    const v = rec[f.key];
    if (Array.isArray(v)) return v.length > 0;
    if (f.key === 'flow' || f.key === 'clots' || f.key === 'pain') return v && v !== 'none';
    return v && String(v).trim() !== '';
  });

  if (!hasAny) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = '这一天还没有记录。';
    content.appendChild(empty);
  } else {
    const list = document.createElement('div');
    list.className = 'detail-list';
    DETAIL_FIELDS.forEach((f) => {
      const v = rec[f.key];
      let text = '';
      if (f.type === 'select') {
        if (!v || v === 'none') return;
        text = labelOf(f.key, v);
      } else if (f.type === 'multi') {
        if (!Array.isArray(v) || v.length === 0) return;
        text = v.map((x) => labelOf(f.key, x)).join('、');
      } else {
        if (!v || String(v).trim() === '') return;
        text = v;
      }
      const row = document.createElement('div');
      row.className = 'detail-row';
      const name = document.createElement('span');
      name.className = 'detail-label';
      name.textContent = f.label;
      const val = document.createElement('span');
      val.className = 'detail-value';
      val.textContent = text;
      row.append(name, val);
      list.appendChild(row);
    });
    content.appendChild(list);
  }

  show('detail-view');
  hide('editor-form');
  show('editor-modal');
}

function openEditor(date) {
  state.editingDate = date;
  const rec = state.records.get(date) || {};
  document.getElementById('editor-title').textContent = `编辑 ${date}`;
  hide('detail-view');
  show('editor-form');
  const form = document.getElementById('editor-form');
  form.innerHTML = '';
  form.appendChild(fieldGroup('flow', '经量', OPTIONS.flow, 'select', rec.flow || 'none'));
  form.appendChild(fieldGroup('colors', '颜色（可多选）', OPTIONS.colors, 'checkbox', rec.colors));
  form.appendChild(fieldGroup('clots', '血块', OPTIONS.clots, 'select', rec.clots || 'none'));
  form.appendChild(fieldGroup('pain', '疼痛', OPTIONS.pain, 'select', rec.pain || 'none'));
  form.appendChild(fieldGroup('symptoms', '症状（可多选）', OPTIONS.symptoms, 'checkbox', rec.symptoms));
  form.appendChild(fieldGroup('mood', '情绪（可多选）', OPTIONS.mood, 'checkbox', rec.mood));
  form.appendChild(textField('medication', '用药', rec.medication));
  form.appendChild(textField('notes', '备注', rec.notes, true));

  const actions = document.createElement('div');
  actions.className = 'actions';
  const save = document.createElement('button');
  save.type = 'submit';
  save.textContent = '保存';
  const del = document.createElement('button');
  del.type = 'button';
  del.className = 'ghost danger';
  del.textContent = '删除当天记录';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'ghost';
  cancel.textContent = '取消';
  actions.append(save, del, cancel);
  form.appendChild(actions);

  form.onsubmit = saveRecord;
  del.onclick = deleteRecord;
  cancel.onclick = () => hide('editor-modal');
  show('editor-modal');
}

function collectForm(form) {
  const data = new FormData(form);
  return {
    flow: data.get('flow'),
    colors: data.getAll('colors'),
    clots: data.get('clots'),
    pain: data.get('pain'),
    symptoms: data.getAll('symptoms'),
    mood: data.getAll('mood'),
    medication: data.get('medication') || '',
    notes: data.get('notes') || '',
  };
}

async function saveRecord(e) {
  e.preventDefault();
  const body = collectForm(e.target);
  await api(`/records/${state.editingDate}`, { method: 'PUT', body: JSON.stringify(body) });
  state.records.set(state.editingDate, { date: state.editingDate, ...body });
  renderCalendar();
  await refreshPredictions();
  openDetail(state.editingDate);
}

async function deleteRecord() {
  await api(`/records/${state.editingDate}`, { method: 'DELETE' });
  state.records.delete(state.editingDate);
  hide('editor-modal');
  renderCalendar();
  await refreshPredictions();
}

/* ---------- 预测与通知 ---------- */

async function refreshPredictions() {
  state.predictions = await api('/predictions');
  renderSummary();
  const data = await api('/notifications');
  state.notifications = data.notifications;
  renderNotifications();
}

function renderSummary() {
  const el = document.getElementById('summary-content');
  el.innerHTML = '';
  const p = state.predictions;
  if (!p || p.status !== 'ok') {
    const msg = document.createElement('p');
    msg.textContent = (p && p.message) || '记录 2 次经期后可开始预测';
    el.appendChild(msg);
    return;
  }
  const lines = [
    ['下次月经', `${p.next_period}（±${p.range_days} 天）`],
    ['排卵日', `${p.ovulation}（前后 1 天为受孕窗口）`],
  ];
  lines.forEach(([k, v]) => {
    const row = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = `${k}：`;
    row.append(strong, document.createTextNode(v));
    el.appendChild(row);
  });
  const hint = document.createElement('p');
  hint.className = 'hint';
  hint.textContent = `基于 ${p.samples} 次经期记录，平均周期 ${p.cycle_median} 天。预测仅供参考。`;
  el.appendChild(hint);
}

function renderNotifications() {
  const bar = document.getElementById('notification-bar');
  bar.innerHTML = '';
  state.notifications.forEach((n) => {
    const item = document.createElement('div');
    item.className = `notice notice-${n.type}`;
    const title = document.createElement('span');
    title.className = 'notice-title';
    title.textContent = n.title;
    const msg = document.createElement('span');
    msg.textContent = n.message;
    const close = document.createElement('button');
    close.className = 'notice-close ghost';
    close.textContent = '×';
    close.addEventListener('click', () => item.remove());
    item.append(title, msg, close);
    bar.appendChild(item);
  });
}

/* ---------- 视图切换与初始化 ---------- */

function showApp() {
  hide('auth-view');
  show('app-view');
  document.getElementById('username-label').textContent = state.username;
  loadMonth().catch((err) => alert(err.message));
}

function bindEvents() {
  document.getElementById('auth-form').addEventListener('submit', submitAuth);
  document.getElementById('auth-toggle').addEventListener('click', (e) => {
    e.preventDefault();
    toggleAuthMode();
  });
  document.getElementById('logout-btn').addEventListener('click', logout);
  document.getElementById('detail-edit').addEventListener('click', () => openEditor(state.editingDate));
  document.getElementById('detail-close').addEventListener('click', () => hide('editor-modal'));
  document.getElementById('prev-month').addEventListener('click', () => {
    state.month = new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1);
    loadMonth().catch((err) => alert(err.message));
  });
  document.getElementById('next-month').addEventListener('click', () => {
    state.month = new Date(state.month.getFullYear(), state.month.getMonth() + 1, 1);
    loadMonth().catch((err) => alert(err.message));
  });
  document.getElementById('today-btn').addEventListener('click', () => {
    state.month = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    loadMonth().catch((err) => alert(err.message));
  });
}

async function init() {
  bindEvents();
  if (state.token) {
    try {
      const me = await api('/auth/me');
      state.username = me.username;
      localStorage.setItem('username', state.username);
      showApp();
    } catch {
      logout();
    }
  } else {
    show('auth-view');
  }
}

init();
