/**
 * Dashboard JavaScript
 */

// Загрузка статистики дашборда
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/stats/dashboard');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('total-orders').textContent = data.stats.total_orders;
            document.getElementById('processing-orders').textContent = data.stats.processing_orders;
            document.getElementById('done-orders').textContent = data.stats.done_orders;
            document.getElementById('revenue').textContent = `${data.stats.revenue.toLocaleString()} ₽`;
            
            // Строим графики
            buildRevenueChart();
            buildServicesChart(data.stats.top_services);
        }
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
    }
}

// Загрузка последних заказов
async function loadRecentOrders() {
    try {
        const response = await fetch('/api/orders?limit=10');
        const data = await response.json();
        
        if (data.success) {
            const tbody = document.getElementById('recent-orders-body');
            tbody.innerHTML = '';
            
            data.orders.forEach(order => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>#${order.id}</td>
                    <td>${escapeHtml(order.client_name)}</td>
                    <td>${escapeHtml(order.service_name)}</td>
                    <td><span class="status-${order.status}">${getStatusName(order.status)}</span></td>
                    <td>${order.final_price.toFixed(2)} ₽</td>
                    <td>${formatDate(order.created_at)}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки заказов:', error);
        document.getElementById('recent-orders-body').innerHTML = 
            '<tr><td colspan="6">❌ Ошибка загрузки</td></tr>';
    }
}

// График выручки
let revenueChart = null;
async function buildRevenueChart() {
    try {
        const response = await fetch('/api/stats/revenue');
        const data = await response.json();
        
        if (data.success) {
            const ctx = document.getElementById('revenue-chart').getContext('2d');
            
            if (revenueChart) {
                revenueChart.destroy();
            }
            
            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.data.map(d => d.date),
                    datasets: [{
                        label: 'Выручка (₽)',
                        data: data.data.map(d => d.revenue),
                        borderColor: '#e94560',
                        backgroundColor: 'rgba(233, 69, 96, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#bbb'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#bbb'
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Ошибка построения графика выручки:', error);
    }
}

// График услуг
let servicesChart = null;
function buildServicesChart(topServices) {
    const ctx = document.getElementById('services-chart').getContext('2d');
    
    if (servicesChart) {
        servicesChart.destroy();
    }
    
    servicesChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: topServices.map(s => s.name),
            datasets: [{
                data: topServices.map(s => s.count),
                backgroundColor: [
                    '#e94560',
                    '#4caf50',
                    '#ff9800',
                    '#2196f3',
                    '#9c27b0'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#eee',
                        padding: 15
                    }
                }
            }
        }
    });
}

// Вспомогательные функции
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusName(status) {
    const names = {
        'new': 'Новый',
        'processing': 'В работе',
        'done': 'Готов',
        'delivered': 'Выдан'
    };
    return names[status] || status;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadRecentOrders();
    
    // Автообновление каждые 30 секунд
    setInterval(() => {
        loadDashboardStats();
        loadRecentOrders();
    }, 30000);
});
