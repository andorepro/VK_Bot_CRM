/* Laser Workshop CRM - Main Application JavaScript */

// Global state
let priceList = [];
let currentPromoDiscount = 0;
let currentClientVkId = null;
let currentMonth = new Date().getMonth() + 1;
let currentYear = new Date().getFullYear();
let currentUserRole = 'admin';
let servicesChart = null;
let segmentsChart = null;
let inventoryChart = null;
let deferredPrompt = null;

// VK Long Poll State
let vkLongPollServer = null;
let vkLongPollKey = null;
let vkLongPollTs = null;
let vkPollConnected = false;

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
  // Check if user is logged in
  checkAuth();

  // Register Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('✅ SW registered:', reg.scope))
      .catch(err => console.log('❌ SW error:', err));
  }

  // Offline Detection
  window.addEventListener('online', () => {
    document.getElementById('offline-indicator')?.classList.remove('active');
    showToast('📡 Подключение восстановлено');
    refreshAllData();
  });
  window.addEventListener('offline', () => {
    document.getElementById('offline-indicator')?.classList.add('active');
    showToast('📡 Офлайн режим');
  });

  // PWA Install Prompt
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const installBtn = document.getElementById('install-pwa');
    if (installBtn) installBtn.style.display = 'block';
  });

  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  // Auto-refresh chat
  setInterval(() => {
    if (currentClientVkId) loadChatMessages(currentClientVkId);
  }, 3000);

  // Initialize VK Long Poll
  initVKLongPoll();
});

// ==================== AUTHENTICATION ====================
async function checkAuth() {
  try {
    const res = await fetch('/api/auth/check');
    const data = await res.json();
    
    if (!data.authenticated) {
      showLoginPage();
      return;
    }
    
    currentUserRole = data.role || 'admin';
    document.getElementById('username-display').textContent = data.username || 'user';
    document.getElementById('role-display').textContent = data.role || 'user';
    document.getElementById('role-display').className = `role-badge role-${data.role || 'admin'}`;
    
    // Load initial data
    loadPriceList();
    loadOrders();
    loadClients();
    loadSummary();
    loadInventory();
    loadAIPredictions();
    loadLowStock();
    loadChatClients();

    // Admin-only tabs
    if (currentUserRole === 'admin') {
      document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
      loadUsers();
      loadAuditLog();
    }
  } catch(e) {
    console.error('Auth check error:', e);
    showLoginPage();
  }
}

function showLoginPage() {
  // Hide main app, show login
  document.querySelector('header')?.style.setProperty('display', 'none', 'important');
  document.querySelector('.container')?.style.setProperty('display', 'none', 'important');
  
  const loginHTML = `
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <h1>🔬 Лазерная Мастерская</h1>
          <p>CRM Система - Вход</p>
        </div>
        <div id="login-error" class="login-error hidden"></div>
        <form class="login-form" onsubmit="handleLogin(event)">
          <div class="form-group">
            <label>Имя пользователя</label>
            <input type="text" id="login-username" required placeholder="Введите имя">
          </div>
          <div class="form-group">
            <label>Пароль</label>
            <input type="password" id="login-password" required placeholder="Введите пароль">
          </div>
          <button type="submit" class="btn-login">Войти</button>
        </form>
        <div class="login-footer">
          © 2024 Лазерная Мастерская CRM
        </div>
      </div>
    </div>
  `;
  
  document.body.innerHTML = loginHTML + document.body.innerHTML;
}

async function handleLogin(event) {
  event.preventDefault();
  
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errorDiv = document.getElementById('login-error');
  
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username, password})
    });
    
    const data = await res.json();
    
    if (data.success) {
      location.reload();
    } else {
      errorDiv.textContent = data.error || 'Ошибка входа';
      errorDiv.classList.remove('hidden');
    }
  } catch(e) {
    console.error('Login error:', e);
    errorDiv.textContent = 'Ошибка подключения к серверу';
    errorDiv.classList.remove('hidden');
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', {method: 'POST'});
  } catch(e) {
    console.error('Logout error:', e);
  }
  location.href = '/';
}

// ==================== VK LONG POLL API ====================
async function initVKLongPoll() {
  try {
    // Get Long Poll server details from backend
    const res = await fetch('/api/vk/longpoll/init');
    const data = await res.json();
    
    if (data.success) {
      vkLongPollServer = data.server;
      vkLongPollKey = data.key;
      vkLongPollTs = data.ts;
      
      updateVKPollStatus(true);
      startLongPolling();
    } else {
      updateVKPollStatus(false);
    }
  } catch(e) {
    console.error('VK Long Poll init error:', e);
    updateVKPollStatus(false);
  }
}

function updateVKPollStatus(connected) {
  vkPollConnected = connected;
  
  // Update UI status indicator
  let statusEl = document.getElementById('vk-poll-status');
  if (!statusEl) {
    // Create status indicator if not exists
    const userInfo = document.querySelector('.user-info');
    if (userInfo) {
      statusEl = document.createElement('span');
      statusEl.id = 'vk-poll-status';
      statusEl.className = `vk-poll-status ${connected ? 'connected' : 'disconnected'}`;
      statusEl.innerHTML = `<span class="status-dot"></span><span>VK: ${connected ? 'Подключено' : 'Отключено'}</span>`;
      userInfo.appendChild(statusEl);
      return;
    }
  }
  
  statusEl.className = `vk-poll-status ${connected ? 'connected' : 'disconnected'}`;
  statusEl.innerHTML = `<span class="status-dot"></span><span>VK: ${connected ? 'Подключено' : 'Отключено'}</span>`;
}

async function startLongPolling() {
  while (vkPollConnected) {
    try {
      const url = `${vkLongPollServer}?act=a_check&key=${vkLongPollKey}&ts=${vkLongPollTs}&wait=25&version=3`;
      const res = await fetch(url);
      const data = await res.json();
      
      if (data.failed) {
        // Reinitialize if failed
        await initVKLongPoll();
        break;
      }
      
      vkLongPollTs = data.ts;
      
      // Process updates
      if (data.updates) {
        for (const update of data.updates) {
          await processVKUpdate(update);
        }
      }
    } catch(e) {
      console.error('Long Poll error:', e);
      await sleep(5000);
    }
  }
}

async function processVKUpdate(update) {
  const [type, ...params] = update;
  
  // Type 4 = new message
  if (type === 4) {
    const [messageId, flags, userId, text] = params;
    
    // Only process incoming messages (flag 2 not set)
    if (!(flags & 2)) {
      // New incoming message from VK
      await handleIncomingVKMessage(userId, text);
    }
  }
  
  // Type 5 = message flags updated (read, etc.)
  if (type === 5) {
    const [messageId, flags, userId] = params;
    // Handle message read status if needed
  }
}

async function handleIncomingVKMessage(vkId, text) {
  console.log('New VK message:', vkId, text);
  
  // Save message to database via API
  try {
    await fetch('/api/chat/receive', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({vk_id: vkId, message: text})
    });
    
    // Refresh chat if this client is selected
    if (currentClientVkId == vkId) {
      loadChatMessages(vkId);
    }
    
    // Show notification
    showToast(`💬 Новое сообщение от VK ${vkId}`);
  } catch(e) {
    console.error('Handle VK message error:', e);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ==================== TAB SWITCHING ====================
function switchTab(tabId) {
  document.querySelectorAll('.content-section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));

  document.getElementById(tabId).classList.add('active');
  document.querySelector(`.tab[data-tab="${tabId}"]`)?.classList.add('active');

  // Load data on tab switch
  if (tabId === 'calendar') loadCalendar();
  if (tabId === 'analytics') loadDetailedAnalytics();
  if (tabId === 'inventory') loadInventory();
  if (tabId === 'users' && currentUserRole === 'admin') loadUsers();
  if (tabId === 'audit' && currentUserRole === 'admin') loadAuditLog();
}

// ==================== PRICE LIST & CALCULATOR ====================
async function loadPriceList() {
  try {
    const res = await fetch('/api/price_list');
    priceList = await res.json();
    const select = document.getElementById('calc-service');
    select.innerHTML = '<option value="">Выберите услугу...</option>';
    priceList.forEach((item, i) => {
      select.innerHTML += `<option value="${i}" data-type="${item.calc_type}" data-price="${item.price}">${item.name} — ${item.price}₽</option>`;
    });
  } catch(e) { console.error('Load price list error:', e); }
}

function updateCalculatorFields() {
  const select = document.getElementById('calc-service');
  const option = select.options[select.selectedIndex];
  if (!option.value) return;

  const calcType = option.getAttribute('data-type');
  const fieldsDiv = document.getElementById('calc-fields');

  const configs = {
    'fixed': [{name:'quantity', label:'Количество (шт)', type:'number', min:1}],
    'area_cm2': [
      {name:'length', label:'Длина (см)', type:'number', step:'0.1'},
      {name:'width', label:'Ширина (см)', type:'number', step:'0.1'}
    ],
    'meter_thickness': [
      {name:'meters', label:'Метры реза', type:'number', step:'0.1'},
      {name:'thickness', label:'Толщина (мм)', type:'number', min:1, max:20}
    ],
    'per_minute': [{name:'minutes', label:'Минуты', type:'number', min:1}],
    'per_char': [{name:'chars', label:'Символы', type:'number', min:1}],
    'vector_length': [{name:'length', label:'Метры вектора', type:'number', step:'0.1'}],
    'setup_batch': [
      {name:'setup_price', label:'Настройка (₽)', type:'number'},
      {name:'quantity', label:'Тираж (шт)', type:'number', min:1}
    ],
    'photo_raster': [
      {name:'length', label:'Длина (см)', type:'number', step:'0.1'},
      {name:'width', label:'Ширина (см)', type:'number', step:'0.1'},
      {name:'dpi_multiplier', label:'DPI множитель', type:'number', step:'0.1', value:'1'}
    ],
    'cylindrical': [
      {name:'diameter', label:'Диаметр (мм)', type:'number'},
      {name:'length', label:'Длина (мм)', type:'number'}
    ],
    'volume_3d': [
      {name:'length', label:'Длина (см)', type:'number', step:'0.1'},
      {name:'width', label:'Ширина (см)', type:'number', step:'0.1'},
      {name:'depth', label:'Глубина (мм)', type:'number'}
    ],
    'material_and_cut': [
      {name:'length', label:'Длина (см)', type:'number', step:'0.1'},
      {name:'width', label:'Ширина (см)', type:'number', step:'0.1'},
      {name:'cut_meters', label:'Метры реза', type:'number', step:'0.1'}
    ]
  };

  const config = configs[calcType] || [];
  fieldsDiv.innerHTML = config.map(f => `
    <div class="form-group">
      <label>${f.label}</label>
      <input type="${f.type}" id="calc-${f.name}"
             step="${f.step||1}" min="${f.min||0}" max="${f.max||''}" value="${f.value||''}"
             oninput="calculatePrice()">
    </div>
  `).join('');

  calculatePrice();
}

async function validatePromo() {
  const code = document.getElementById('calc-promo').value.trim().toUpperCase();
  if (!code) { currentPromoDiscount = 0; calculatePrice(); return; }

  try {
    const res = await fetch('/api/promo/validate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code})
    });
    const data = await res.json();
    if (data.valid) {
      currentPromoDiscount = data.discount / 100;
      showToast(`✅ Промокод: скидка ${data.discount}%`);
    } else {
      currentPromoDiscount = 0;
      showToast('❌ Промокод недействителен');
    }
    calculatePrice();
  } catch(e) { console.error('Promo validate error:', e); }
}

function calculatePrice() {
  const select = document.getElementById('calc-service');
  const option = select.options[select.selectedIndex];
  if (!option.value) return;

  const calcType = option.getAttribute('data-type');
  const basePrice = parseFloat(option.getAttribute('data-price'));
  const params = {};

  document.querySelectorAll('#calc-fields input').forEach(input => {
    const name = input.id.replace('calc-', '');
    params[name] = parseFloat(input.value) || 0;
  });

  let price = 0;
  switch(calcType) {
    case 'fixed': price = basePrice * (params.quantity || 1); break;
    case 'area_cm2': price = (params.length/10) * (params.width/10) * basePrice; break;
    case 'meter_thickness': price = params.meters * (basePrice * (params.thickness/3)); break;
    case 'per_minute': price = params.minutes * basePrice; break;
    case 'per_char': price = params.chars * basePrice; break;
    case 'vector_length': price = params.length * basePrice; break;
    case 'setup_batch':
      price = (params.setup_price || basePrice) + (basePrice * (params.quantity || 1)); break;
    case 'photo_raster':
      price = (params.length/10) * (params.width/10) * basePrice * (params.dpi_multiplier || 1); break;
    case 'cylindrical':
      price = (params.diameter * 3.14 * params.length / 100) * basePrice; break;
    case 'volume_3d':
      price = (params.length/10) * (params.width/10) * params.depth * basePrice; break;
    case 'material_and_cut':
      price = ((params.length/10) * (params.width/10) * basePrice) + (params.cut_meters * basePrice); break;
  }

  // Discounts
  const qty = params.quantity || 1;
  let discount = 0;
  if (qty >= 100) discount = 0.20;
  else if (qty >= 50) discount = 0.15;
  else if (qty >= 20) discount = 0.10;
  else if (qty >= 10) discount = 0.05;

  if (currentPromoDiscount > discount) discount = currentPromoDiscount;

  let finalPrice = price * (1 - discount);

  // Cashback
  let cashbackUsed = 0;
  if (document.getElementById('calc-cashback').value === '1') {
    const maxCB = finalPrice * 0.30;
    cashbackUsed = Math.min(1000, maxCB); // Demo balance
    finalPrice -= cashbackUsed;
  }

  document.getElementById('calc-total').textContent = finalPrice.toFixed(2) + '₽';
  document.getElementById('calc-discount').textContent = discount > 0 ? `Скидка ${Math.round(discount*100)}%` : '';
  document.getElementById('calc-cashback-display').textContent =
    cashbackUsed > 0 ? `Кэшбек: -${cashbackUsed.toFixed(2)}₽` : '';
}

async function createOrderFromCalc() {
  const select = document.getElementById('calc-service');
  const option = select.options[select.selectedIndex];
  if (!option.value) { showToast('⚠️ Выберите услугу'); return; }

  const params = {};
  document.querySelectorAll('#calc-fields input').forEach(input => {
    params[input.id.replace('calc-', '')] = input.value;
  });

  const total = parseFloat(document.getElementById('calc-total').textContent);

  try {
    await fetch('/api/order/create', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        service_id: option.value,
        service_name: option.text.split(' — ')[0],
        parameters: params,
        total_price: total,
        discount: currentPromoDiscount * 100,
        promo_code: document.getElementById('calc-promo').value.trim() || null,
        cashback_applied: document.getElementById('calc-cashback').value === '1' ? 100 : 0,
        planned_date: document.getElementById('calc-planned-date').value,
        status: 'NEW'
      })
    });
    showToast('✅ Заказ создан');
    loadOrders();
    loadCalendar();
    loadSummary();
  } catch(e) {
    console.error('Create order error:', e);
    showToast('❌ Ошибка создания заказа');
  }
}

// ==================== ORDERS ====================
async function loadOrders() {
  try {
    const status = document.getElementById('order-status-filter').value;
    const search = document.getElementById('order-search').value.toLowerCase();
    const res = await fetch(`/api/orders${status !== 'all' ? '?status='+status : ''}`);
    let orders = await res.json();

    if (search) {
      orders = orders.filter(o =>
        (o.client_name?.toLowerCase().includes(search)) ||
        (o.service_name?.toLowerCase().includes(search)) ||
        (o.id.toString().includes(search))
      );
    }

    const tbody = document.getElementById('orders-body');
    tbody.innerHTML = orders.map(o => `
      <tr>
        <td>#${o.id}</td>
        <td>${o.client_name || '—'}</td>
        <td>${o.service_name}</td>
        <td>${o.total_price}₽</td>
        <td>${o.discount > 0 ? o.discount+'%' : '—'}</td>
        <td style="color:var(--cashback-color)">${o.cashback_applied > 0 ? o.cashback_applied.toFixed(2)+'₽' : '—'}</td>
        <td><span class="status-badge status-${o.status.toLowerCase()}">${o.status}</span></td>
        <td>
          ${o.status !== 'DONE' ? `<button class="btn btn-warning" style="padding:4px 8px;font-size:11px;" onclick="updateStatus(${o.id},'PROCESSING')">⚙️</button>` : ''}
          ${o.status !== 'DONE' ? `<button class="btn btn-success" style="padding:4px 8px;font-size:11px;" onclick="updateStatus(${o.id},'DONE')">✅</button>` : ''}
        </td>
      </tr>
    `).join('');

    document.getElementById('active-orders').textContent =
      orders.filter(o => ['NEW','PROCESSING'].includes(o.status)).length;
    document.getElementById('completed-orders').textContent =
      orders.filter(o => o.status === 'DONE').length;
  } catch(e) { console.error('Load orders error:', e); }
}

async function updateStatus(orderId, status) {
  try {
    await fetch('/api/order/status', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({order_id: orderId, status})
    });
    showToast(`✅ Статус: ${status}`);
    loadOrders();
    loadSummary();
  } catch(e) {
    console.error('Update status error:', e);
    showToast('❌ Ошибка обновления');
  }
}

// ==================== CLIENTS ====================
async function loadClients() {
  try {
    const segment = document.getElementById('client-segment-filter').value;
    const res = await fetch(`/api/clients${segment !== 'all' ? '?segment='+segment : ''}`);
    const clients = await res.json();

    document.getElementById('clients-body').innerHTML = clients.map(c => `
      <tr>
        <td>${c.id}</td>
        <td>${c.name}</td>
        <td>${c.vk_id || '—'}</td>
        <td><span class="segment-badge segment-${c.customer_segment}">${c.customer_segment}</span></td>
        <td>${c.total_orders}</td>
        <td>${c.total_spent}₽</td>
        <td style="color:var(--cashback-color)">${(c.cashback_balance||0).toFixed(2)}₽</td>
        <td>${(c.avg_check||0).toFixed(2)}₽</td>
      </tr>
    `).join('');
  } catch(e) { console.error('Load clients error:', e); }
}

// ==================== CHAT ====================
async function loadChatClients() {
  try {
    const res = await fetch('/api/clients');
    const clients = (await res.json()).filter(c => c.vk_id);

    document.getElementById('chat-clients').innerHTML = clients.map(c => `
      <div class="chat-client" onclick="selectClient(${c.vk_id}, '${c.name}')">
        <div class="name">${c.name}</div>
        <div class="vk-id">VK: ${c.vk_id}</div>
      </div>
    `).join('') || '<div style="padding:16px;text-align:center;opacity:0.7">Нет клиентов с VK</div>';
  } catch(e) { console.error('Load chat clients error:', e); }
}

function selectClient(vkId, name) {
  currentClientVkId = vkId;
  document.querySelectorAll('.chat-client').forEach(el => el.classList.remove('active'));
  event.currentTarget.classList.add('active');
  loadChatMessages(vkId);
}

async function loadChatMessages(vkId) {
  try {
    const res = await fetch(`/api/chat/history?vk_id=${vkId}`);
    const messages = await res.json();

    document.getElementById('chat-messages').innerHTML = messages.reverse().map(m => `
      <div class="message ${m.is_admin ? 'message-admin' : 'message-client'}">
        ${m.message_text}
        <span class="time">${new Date(m.timestamp).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'})}</span>
      </div>
    `).join('');

    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
  } catch(e) { console.error('Load chat error:', e); }
}

async function sendMessage() {
  const input = document.getElementById('chat-message-input');
  const message = input.value.trim();
  if (!message || !currentClientVkId) return;

  try {
    await fetch('/api/chat/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({vk_id: currentClientVkId, message})
    });
    input.value = '';
    loadChatMessages(currentClientVkId);
  } catch(e) {
    console.error('Send message error:', e);
    showToast('❌ Не удалось отправить');
  }
}

// ==================== CALENDAR ====================
async function loadCalendar() {
  try {
    const res = await fetch(`/api/calendar?month=${currentMonth}&year=${currentYear}`);
    const data = await res.json();

    const months = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
    document.getElementById('calendar-month').textContent = `${months[currentMonth-1]} ${currentYear}`;

    const days = new Date(currentYear, currentMonth, 0).getDate();
    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';
    const today = new Date().toISOString().split('T')[0];

    for (let d = 1; d <= days; d++) {
      const dateStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const orders = data[dateStr] || [];
      const isToday = dateStr === today;

      const day = document.createElement('div');
      day.className = `calendar-day${isToday ? ' today' : ''}`;
      day.innerHTML = `
        <div class="calendar-day-header">${d}</div>
        ${orders.slice(0,3).map(o => `
          <div class="calendar-order" title="${o.client_name}: ${o.service_name}">
            ${o.client_name} — ${o.total_price}₽
          </div>
        `).join('')}
        ${orders.length > 3 ? `<div style="font-size:10px;opacity:0.7">+${orders.length-3} ещё</div>` : ''}
      `;
      grid.appendChild(day);
    }
  } catch(e) { console.error('Load calendar error:', e); }
}

function changeMonth(delta) {
  currentMonth += delta;
  if (currentMonth > 12) { currentMonth = 1; currentYear++; }
  else if (currentMonth < 1) { currentMonth = 12; currentYear--; }
  loadCalendar();
}

// ==================== ANALYTICS ====================
async function loadSummary() {
  try {
    const res = await fetch('/api/analytics/summary');
    const data = await res.json();

    document.getElementById('total-revenue').textContent = data.total_revenue.toFixed(2) + '₽';
    document.getElementById('total-orders-count').textContent = `${data.total_orders} заказов`;
    document.getElementById('avg-check').textContent = data.avg_check.toFixed(2) + '₽';
    document.getElementById('total-cashback').textContent = data.total_cashback_outstanding.toFixed(2) + '₽';

    document.getElementById('top-clients').innerHTML = data.top_clients.map((c,i) => `
      <div style="padding:8px 0;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between">
        <span>${i+1}. ${c.name}</span>
        <span style="color:var(--success-color);font-weight:600">${c.total_spent}₽</span>
      </div>
    `).join('') || '<div style="opacity:0.7">Нет данных</div>';
  } catch(e) { console.error('Load summary error:', e); }
}

async function loadDetailedAnalytics() {
  try {
    // Services chart
    const svcRes = await fetch('/api/analytics/services');
    const svcData = await svcRes.json();
    const svcCtx = document.getElementById('servicesChart');
    if (servicesChart) servicesChart.destroy();
    servicesChart = new Chart(svcCtx, {
      type: 'doughnut',
      data: {
        labels: svcData.map(d => d.service_name),
        datasets: [{
          data: svcData.map(d => d.revenue),
          backgroundColor: ['#4fc3f7','#4caf50','#ff9800','#f44336','#9c27b0','#00bcd4']
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#eaeaea', font: {size:10} } } }
      }
    });

    // Segments chart
    const segRes = await fetch('/api/analytics/segments');
    const segData = await segRes.json();
    const segCtx = document.getElementById('segmentsChart');
    if (segmentsChart) segmentsChart.destroy();
    segmentsChart = new Chart(segCtx, {
      type: 'pie',
      data: {
        labels: segData.map(d => d.customer_segment),
        datasets: [{
          data: segData.map(d => d.count),
          backgroundColor: ['#ffd700','#4caf50','#2196f3','#9e9e9e']
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#eaeaea', font: {size:10} } } }
      }
    });

    // Inventory chart
    const invRes = await fetch('/api/inventory');
    const invData = await invRes.json();
    const invCtx = document.getElementById('inventoryChart');
    if (inventoryChart) inventoryChart.destroy();
    inventoryChart = new Chart(invCtx, {
      type: 'bar',
      data: {
        labels: invData.slice(0,10).map(d => d.item_name),
        datasets: [{
          label: 'Остаток',
          data: invData.slice(0,10).map(d => d.quantity),
          backgroundColor: invData.slice(0,10).map(d =>
            d.quantity <= d.min_quantity ? '#f44336' : '#4caf50'
          )
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { color: '#eaeaea' }, grid: { color: '#2a2a4a' } },
          x: { ticks: { color: '#eaeaea', font: {size:9} }, grid: { color: '#2a2a4a' } }
        }
      }
    });
  } catch(e) { console.error('Load analytics error:', e); }
}

// ==================== AI PREDICTIONS ====================
async function loadAIPredictions() {
  try {
    const res = await fetch('/api/analytics/forecast');
    const data = await res.json();

    if (data && data.forecast && data.forecast.length > 0) {
      // Отображаем прогноз выручки
      document.getElementById('ai-prediction-value').textContent =
        data.monthly_prediction.toFixed(2) + '₽';
      
      const trendDesc = data.trend_description || '➡️ Стабильно';
      document.getElementById('ai-prediction-trend').innerHTML =
        `Тренд: ${trendDesc}`;
      
      document.getElementById('ai-confidence').textContent =
        `Уверенность: ${data.confidence}%`;
      
      // Обновляем расширенную информацию о прогнозе
      updateForecastDetails(data);
      
    } else {
      document.getElementById('ai-prediction-value').textContent = 'Недостаточно данных';
      document.getElementById('ai-prediction-trend').textContent = '';
      document.getElementById('ai-confidence').textContent = '';
    }
  } catch(e) { 
    console.error('Load AI forecast error:', e);
    document.getElementById('ai-prediction-value').textContent = 'Ошибка загрузки';
  }
}

// Обновление деталей прогноза
function updateForecastDetails(data) {
  const detailsContainer = document.getElementById('forecast-details');
  if (!detailsContainer) return;
  
  const metrics = data.metrics || {};
  const historical = data.historical_data || {};
  
  detailsContainer.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:15px;">
      <div class="stat-card" style="background:linear-gradient(135deg,#1e3a5f,#0d2137);padding:12px;border-radius:10px;">
        <div style="font-size:11px;color:#aaa;margin-bottom:5px;">Прогноз на неделю</div>
        <div style="font-size:18px;font-weight:bold;color:#4fc3f7">${(data.weekly_prediction||0).toFixed(0)}₽</div>
      </div>
      <div class="stat-card" style="background:linear-gradient(135deg,#1e3a5f,#0d2137);padding:12px;border-radius:10px;">
        <div style="font-size:11px;color:#aaa;margin-bottom:5px;">Средний чек</div>
        <div style="font-size:18px;font-weight:bold;color:#4caf50">${(historical.avg_daily_revenue||0).toFixed(0)}₽</div>
      </div>
      <div class="stat-card" style="background:linear-gradient(135deg,#1e3a5f,#0d2137);padding:12px;border-radius:10px;">
        <div style="font-size:11px;color:#aaa;margin-bottom:5px;">R² точность</div>
        <div style="font-size:18px;font-weight:bold;color:#ff9800">${(metrics.r_squared||0)*100.toFixed(0)}%</div>
      </div>
      <div class="stat-card" style="background:linear-gradient(135deg,#1e3a5f,#0d2137);padding:12px;border-radius:10px;">
        <div style="font-size:11px;color:#aaa;margin-bottom:5px;">Дней анализа</div>
        <div style="font-size:18px;font-weight:bold;color:#9c27b0">${historical.days_analyzed||0}</div>
      </div>
    </div>
    
    <div style="margin-top:20px;">
      <h4 style="color:#eaeaea;margin-bottom:10px;font-size:14px;">📊 График прогноза на 30 дней</h4>
      <canvas id="forecastChart" height="100"></canvas>
    </div>
  `;
  
  // Рисуем график прогноза
  renderForecastChart(data.forecast);
}

let forecastChartInstance = null;

function renderForecastChart(forecastData) {
  const ctx = document.getElementById('forecastChart');
  if (!ctx) return;
  
  if (forecastChartInstance) {
    forecastChartInstance.destroy();
  }
  
  const labels = forecastData.slice(0, 14).map(d => {
    const date = new Date(d.date);
    return `${date.getDate()}.${date.getMonth()+1}`;
  });
  
  const values = forecastData.slice(0, 14).map(d => d.predicted_revenue);
  
  forecastChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Прогноз выручки (₽)',
        data: values,
        borderColor: '#4fc3f7',
        backgroundColor: 'rgba(79, 195, 247, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: '#eaeaea', font: { size: 11 } }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(30, 30, 50, 0.95)',
          titleColor: '#4fc3f7',
          bodyColor: '#eaeaea',
          borderColor: '#4fc3f7',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              return context.parsed.y.toFixed(2) + ' ₽';
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: false,
          grid: { color: '#2a2a4a' },
          ticks: { 
            color: '#aaa',
            callback: function(value) {
              return value.toLocaleString('ru-RU') + '₽';
            }
          }
        },
        x: {
          grid: { color: '#2a2a4a' },
          ticks: { color: '#aaa' }
        }
      }
    }
  });
}

// ==================== INVENTORY ====================
async function loadInventory() {
  try {
    const filter = document.getElementById('inventory-filter')?.value || 'all';
    const res = await fetch('/api/inventory');
    let items = await res.json();

    if (filter === 'low') items = items.filter(i => i.quantity <= i.min_quantity);
    else if (filter !== 'all') items = items.filter(i => i.item_type === filter);

    document.getElementById('inventory-body').innerHTML = items.map(item => {
      const stockClass = item.quantity <= item.min_quantity/2 ? 'stock-critical' :
                       item.quantity <= item.min_quantity ? 'stock-low' : 'stock-ok';
      return `
        <tr>
          <td><span class="stock-indicator ${stockClass}"></span></td>
          <td>${item.item_name}</td>
          <td>${item.item_type}</td>
          <td>${item.quantity} ${item.unit}</td>
          <td>${item.min_quantity}</td>
          <td>${item.price_per_unit}₽</td>
          <td>${item.supplier}</td>
          <td><button class="btn btn-outline" style="padding:4px 8px;font-size:11px;" onclick="editInventory(${item.id})">✏️</button></td>
        </tr>
      `;
    }).join('') || '<tr><td colspan="8" style="text-align:center;padding:20px;opacity:0.7">Нет товаров</td></tr>';
  } catch(e) { console.error('Load inventory error:', e); }
}

async function refreshInventory() {
  await loadInventory();
  showToast('📦 Склад обновлён');
}

function openInventoryModal() {
  document.getElementById('inventory-modal').classList.add('active');
}
function closeInventoryModal() {
  document.getElementById('inventory-modal').classList.remove('active');
}

async function editInventory(id) {
  try {
    const res = await fetch('/api/inventory');
    const items = await res.json();
    const item = items.find(i => i.id === id);
    if (item) {
      document.getElementById('inv-item-id').value = item.id;
      document.getElementById('inv-quantity').value = item.quantity;
      document.getElementById('inv-min-quantity').value = item.min_quantity;
      document.getElementById('inv-price').value = item.price_per_unit;
      document.getElementById('inv-supplier').value = item.supplier;
      openInventoryModal();
    }
  } catch(e) { console.error('Edit inventory error:', e); }
}

async function saveInventory() {
  try {
    await fetch('/api/inventory/update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        id: document.getElementById('inv-item-id').value,
        quantity: parseFloat(document.getElementById('inv-quantity').value),
        min_quantity: parseFloat(document.getElementById('inv-min-quantity').value),
        price_per_unit: parseFloat(document.getElementById('inv-price').value),
        supplier: document.getElementById('inv-supplier').value,
        notes: document.getElementById('inv-notes').value
      })
    });
    showToast('✅ Склад обновлён');
    closeInventoryModal();
    loadInventory();
    loadLowStock();
  } catch(e) {
    console.error('Save inventory error:', e);
    showToast('❌ Ошибка сохранения');
  }
}

async function loadLowStock() {
  try {
    const res = await fetch('/api/inventory/low-stock');
    const items = await res.json();
    const alert = document.getElementById('low-stock-alert');
    if (items.length > 0) {
      alert.classList.remove('hidden');
      document.getElementById('low-stock-items').innerHTML =
        items.map(i => `<strong>${i.item_name}</strong>: ${i.quantity}/${i.min_quantity} ${i.unit}`).join(', ');
    } else {
      alert.classList.add('hidden');
    }
  } catch(e) { console.error('Load low stock error:', e); }
}

// ==================== CASHBACK ====================
function showCashbackModal() {
  document.getElementById('cashback-modal').classList.add('active');
  document.getElementById('total-cashback-display').textContent =
    document.getElementById('total-cashback').textContent;
}
function closeCashbackModal() {
  document.getElementById('cashback-modal').classList.remove('active');
  document.getElementById('client-cashback-info').innerHTML = '';
}

async function checkClientCashback() {
  const vkId = document.getElementById('cashback-vk-id').value;
  if (!vkId) return;

  try {
    const clientsRes = await fetch('/api/clients');
    const clients = await clientsRes.json();
    const client = clients.find(c => c.vk_id == vkId);

    if (client) {
      const histRes = await fetch(`/api/cashback/history/${client.id}`);
      const history = await histRes.json();

      document.getElementById('client-cashback-info').innerHTML = `
        <div class="cashback-card">
          <div>Баланс кэшбека</div>
          <div class="cashback-amount">${(client.cashback_balance||0).toFixed(2)}₽</div>
          <div style="font-size:12px">Заработано: ${(client.cashback_earned||0).toFixed(2)}₽</div>
        </div>
        <div style="margin-top:12px">
          <strong>История операций:</strong>
          ${history.map(h => `
            <div style="padding:8px 0;border-bottom:1px solid var(--border-color);font-size:12px">
              ${h.operation_type==='earned'?'💰 Начислено':'💸 Списано'}:
              <strong>${h.amount.toFixed(2)}₽</strong>
              <span style="opacity:0.7">${new Date(h.created_at).toLocaleDateString('ru-RU')}</span>
            </div>
          `).join('') || '<div style="opacity:0.7;padding:8px">Нет операций</div>'}
        </div>
      `;
    } else {
      document.getElementById('client-cashback-info').innerHTML =
        '<div style="color:var(--danger-color);padding:12px;text-align:center">Клиент не найден</div>';
    }
  } catch(e) {
    console.error('Check cashback error:', e);
    showToast('❌ Ошибка проверки');
  }
}

// ==================== PROMO CODES ====================
function openPromoModal() {
  document.getElementById('promo-modal').classList.add('active');
  loadPromoList();
}
function closePromoModal() {
  document.getElementById('promo-modal').classList.remove('active');
}

async function loadPromoList() {
  try {
    const res = await fetch('/api/promo/list');
    const promos = await res.json();
    document.getElementById('promo-list').innerHTML = promos.map(p => `
      <div class="promo-card">
        <div class="promo-code">${p.code}</div>
        <div>Скидка: <strong>${p.discount_percent}%</strong></div>
        <div class="promo-stats">
          <span>Использовано: ${p.current_uses}/${p.max_uses}</span>
          <span>${p.is_active ? '✅ Активен' : '❌ Неактивен'}</span>
        </div>
        ${p.valid_until ? `<div style="font-size:11px;margin-top:6px;opacity:0.8">До: ${p.valid_until}</div>` : ''}
      </div>
    `).join('');
  } catch(e) { console.error('Load promos error:', e); }
}

async function createPromo() {
  const code = document.getElementById('promo-code').value.trim().toUpperCase();
  const discount = parseFloat(document.getElementById('promo-discount').value);
  const maxUses = parseInt(document.getElementById('promo-max-uses').value) || 100;
  const validUntil = document.getElementById('promo-valid-until').value || null;

  if (!code || !discount) { showToast('⚠️ Заполните код и скидку'); return; }

  try {
    await fetch('/api/promo/create', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code, discount, max_uses: maxUses, valid_until: validUntil})
    });
    showToast('✅ Промокод создан');
    document.getElementById('promo-code').value = '';
    document.getElementById('promo-discount').value = '';
    loadPromoList();
  } catch(e) {
    console.error('Create promo error:', e);
    showToast('❌ Ошибка создания');
  }
}

// ==================== INTEGRATIONS ====================
function openIntegrationsModal() {
  document.getElementById('integrations-modal').classList.add('active');
  loadIntegrations();
}
function closeIntegrationsModal() {
  document.getElementById('integrations-modal').classList.remove('active');
}

async function loadIntegrations() {
  try {
    const res = await fetch('/api/integrations');
    const integrations = await res.json();

    document.getElementById('integrations-list').innerHTML = integrations.map(int => `
      <div class="integration-card">
        <div class="info">
          <div class="name">${int.service_name}</div>
          <div class="desc">${int.config ? JSON.parse(int.config).desc || 'Интеграция' : 'Настройте интеграцию'}</div>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span class="integration-status ${int.is_active ? 'integration-active' : 'integration-inactive'}">
            ${int.is_active ? '✅ Активно' : '❌ Неактивно'}
          </span>
          <button class="btn btn-outline" style="padding:6px 12px;font-size:12px;" onclick="configureIntegration('${int.service_name}')">⚙️</button>
        </div>
      </div>
    `).join('');
  } catch(e) { console.error('Load integrations error:', e); }
}

function configureIntegration(service) {
  showToast(`🔌 Настройка ${service} — требуется API-ключ`);
}

// ==================== USERS & AUDIT (Admin) ====================
async function loadUsers() {
  if (currentUserRole !== 'admin') return;
  try {
    const res = await fetch('/api/users');
    const users = await res.json();
    document.getElementById('users-body').innerHTML = users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td>${u.username}</td>
        <td><span class="role-badge role-${u.role}">${u.role}</span></td>
        <td>${new Date(u.created_at).toLocaleDateString('ru-RU')}</td>
      </tr>
    `).join('');
  } catch(e) { console.error('Load users error:', e); }
}

function openUserModal() {
  document.getElementById('user-modal').classList.add('active');
}
function closeUserModal() {
  document.getElementById('user-modal').classList.remove('active');
}

async function createUser() {
  const username = document.getElementById('user-username').value.trim();
  const password = document.getElementById('user-password').value;
  const role = document.getElementById('user-role').value;

  if (!username || !password) { showToast('⚠️ Заполните все поля'); return; }

  try {
    await fetch('/api/user/create', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username, password, role})
    });
    showToast('✅ Пользователь создан');
    closeUserModal();
    loadUsers();
  } catch(e) {
    console.error('Create user error:', e);
    showToast('❌ Ошибка создания');
  }
}

async function loadAuditLog() {
  if (currentUserRole !== 'admin') return;
  try {
    const res = await fetch('/api/audit-log?limit=50');
    const logs = await res.json();
    document.getElementById('audit-log').innerHTML = logs.map(log => `
      <div class="audit-log-entry">
        <span class="action">${log.action}</span>
        ${log.entity_type ? `→ ${log.entity_type} #${log.entity_id}` : ''}
        <span class="timestamp">${new Date(log.created_at).toLocaleString('ru-RU')} ${log.ip_address ? `• IP: ${log.ip_address}` : ''}</span>
      </div>
    `).join('') || '<div style="opacity:0.7;text-align:center;padding:20px">Нет записей</div>';
  } catch(e) { console.error('Load audit error:', e); }
}

// ==================== UTILITIES ====================
async function exportCSV() {
  window.open('/api/export/csv', '_blank');
  showToast('📥 Экспорт начат');
}

async function downloadBackup() {
  window.open('/api/backup/download', '_blank');
  showToast('💾 Бэкап скачивается');
}

function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

async function refreshAllData() {
  await Promise.all([
    loadOrders(),
    loadClients(),
    loadSummary(),
    loadInventory(),
    loadAIPredictions()
  ]);
  showToast('🔄 Данные обновлены');
}

// ==================== PWA INSTALL ====================
async function installPWA() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') showToast('✅ Приложение установлено');
    deferredPrompt = null;
    document.getElementById('install-pwa').style.display = 'none';
  }
}
