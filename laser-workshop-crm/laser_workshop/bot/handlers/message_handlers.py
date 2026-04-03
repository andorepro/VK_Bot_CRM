# -*- coding: utf-8 -*-
"""
Обработчики сообщений VK бота
Клиентские и админские команды
"""

import logging
from laser_workshop.bot.states.conversation_states import state_manager, ConversationState
from laser_workshop.bot.keyboards.main_keyboards import (
    get_client_main_keyboard,
    get_admin_main_keyboard
)

logger = logging.getLogger(__name__)


async def handle_client_message(vk, user_id, text):
    """Обработка сообщений от клиентов"""
    
    if text == '📋 Сделать заказ':
        await send_message(vk, user_id, 'Выберите тип услуги:', get_service_selection_keyboard())
        state_manager.set_state(user_id, ConversationState.ORDER_SERVICE_SELECT)
    
    elif text == '📦 Мои заказы':
        await show_user_orders(vk, user_id)
    
    elif text == '💰 Баланс и кэшбек':
        await show_cashback_balance(vk, user_id)
    
    elif text == '📞 Контакты':
        await send_message(vk, user_id, 
            '📍 Наш адрес: ул. Примерная, 123\n'
            '📱 Телефон: +7 (999) 000-00-00\n'
            '⏰ Режим работы: Пн-Пт 10:00-19:00'
        )
    
    elif text == 'ℹ️ Помощь':
        await send_message(vk, user_id,
            '🤖 Бот для заказа лазерной резки и гравировки.\n\n'
            'Доступные команды:\n'
            '• 📋 Сделать заказ - создать новый заказ\n'
            '• 📦 Мои заказы - просмотреть статусы заказов\n'
            '• 💰 Баланс и кэшбек - проверить счёт\n'
            '• 📞 Контакты - связаться с нами'
        )
    
    else:
        current_state = state_manager.get_state(user_id)
        await handle_stateful_message(vk, user_id, text, current_state)


async def handle_admin_message(vk, user_id, text):
    """Обработка сообщений от администраторов"""
    
    if text == '📊 Статистика':
        await show_statistics(vk, user_id)
    
    elif text == '👥 Клиенты':
        await show_clients_list(vk, user_id)
    
    elif text == '📦 Заказы':
        await show_orders_list(vk, user_id)
    
    elif text == '📦 Склад':
        await show_stock_status(vk, user_id)
    
    elif text == '📢 Рассылка':
        state_manager.set_state(user_id, ConversationState.ADMIN_MESSAGE_BROADCAST)
        await send_message(vk, user_id, 'Введите текст рассылки:')
    
    elif text == '⚙️ Настройки':
        await show_settings(vk, user_id)


async def handle_stateful_message(vk, user_id, text, state):
    """Обработка сообщений в зависимости от состояния"""
    
    if state == ConversationState.ORDER_SERVICE_SELECT:
        # Обработка выбора услуги
        await process_service_selection(vk, user_id, text)
    
    elif state == ConversationState.ADMIN_MESSAGE_BROADCAST:
        # Обработка рассылки
        await process_broadcast(vk, user_id, text)
    
    else:
        await send_message(vk, user_id, 'Неизвестная команда. Используйте меню.')


async def send_message(vk, user_id, text, keyboard=None):
    """Отправка сообщения пользователю"""
    try:
        params = {
            'peer_id': user_id,
            'message': text,
            'random_id': 0
        }
        if keyboard:
            params['keyboard'] = keyboard
        vk.messages.send(**params)
    except Exception as e:
        logger.error(f'Ошибка отправки сообщения: {e}')


# Заглушки для функций (реализация в отдельных модулях)
async def show_user_orders(vk, user_id): pass
async def show_cashback_balance(vk, user_id): pass
async def show_statistics(vk, user_id): pass
async def show_clients_list(vk, user_id): pass
async def show_orders_list(vk, user_id): pass
async def show_stock_status(vk, user_id): pass
async def show_settings(vk, user_id): pass
async def get_service_selection_keyboard(): return None
async def process_service_selection(vk, user_id, text): pass
async def process_broadcast(vk, user_id, text): pass
