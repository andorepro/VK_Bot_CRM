/**
 * Переключатель темы (тёмная/светлая)
 */

// Применение темы
function applyTheme(theme) {
    if (theme === 'light') {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
    }
    localStorage.setItem('theme', theme);
}

// Загрузка сохранённой темы
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme);
    
    // Устанавливаем значение в селекторе
    const themeSelect = document.getElementById('theme-switcher');
    if (themeSelect) {
        themeSelect.value = savedTheme;
        
        // Обработчик изменения темы
        themeSelect.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });
    }
});
