# -*- coding: utf-8 -*-
"""
Состояния диалогов для VK бота
Машина состояний для обработки многошаговых сценариев
"""

from enum import Enum


class ConversationState(Enum):
    """Состояния диалога"""
    
    # Начальное состояние
    IDLE = 'idle'
    
    # Создание заказа
    ORDER_SERVICE_SELECT = 'order_service_select'
    ORDER_MATERIAL_SELECT = 'order_material_select'
    ORDER_THICKNESS_INPUT = 'order_thickness_input'
    ORDER_SIZE_INPUT = 'order_size_input'
    ORDER_QUANTITY_INPUT = 'order_quantity_input'
    ORDER_COMMENT_INPUT = 'order_comment_input'
    ORDER_CONFIRM = 'order_confirm'
    
    # Регистрация клиента
    REGISTRATION_NAME = 'registration_name'
    REGISTRATION_PHONE = 'registration_phone'
    
    # Админ операции
    ADMIN_ORDER_STATUS_CHANGE = 'admin_order_status_change'
    ADMIN_CLIENT_SEARCH = 'admin_client_search'
    ADMIN_MESSAGE_BROADCAST = 'admin_message_broadcast'


class StateManager:
    """Менеджер состояний пользователей"""
    
    def __init__(self):
        self._states = {}
    
    def get_state(self, user_id):
        """Получение состояния пользователя"""
        return self._states.get(user_id, ConversationState.IDLE)
    
    def set_state(self, user_id, state):
        """Установка состояния пользователя"""
        self._states[user_id] = state
    
    def reset_state(self, user_id):
        """Сброс состояния пользователя"""
        if user_id in self._states:
            del self._states[user_id]
    
    def clear_all(self):
        """Очистка всех состояний"""
        self._states.clear()


# Глобальный экземпляр
state_manager = StateManager()
