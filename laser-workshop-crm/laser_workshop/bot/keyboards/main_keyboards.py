# -*- coding: utf-8 -*-
"""
Клавиатуры для VK бота
Генерация inline и button клавиатур
"""

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_client_main_keyboard():
    """Основное меню клиента"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('📦 Мои заказы', color=VkKeyboardColor.BLUE)
    keyboard.add_button('💰 Баланс и кэшбек', color=VkKeyboardColor.GREEN)
    
    keyboard.add_line()
    keyboard.add_button('📋 Сделать заказ', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('📞 Контакты', color=VkKeyboardColor.SECONDARY)
    
    keyboard.add_line()
    keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    
    return keyboard.get_keyboard()


def get_admin_main_keyboard():
    """Основное меню администратора"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('📊 Статистика', color=VkKeyboardColor.BLUE)
    keyboard.add_button('👥 Клиенты', color=VkKeyboardColor.GREEN)
    
    keyboard.add_line()
    keyboard.add_button('📦 Заказы', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('📦 Склад', color=VkKeyboardColor.RED)
    
    keyboard.add_line()
    keyboard.add_button('📢 Рассылка', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('⚙️ Настройки', color=VkKeyboardColor.SECONDARY)
    
    return keyboard.get_keyboard()


def get_order_status_keyboard(order_id):
    """Клавиатура для управления статусом заказа"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('✅ В работе', color=VkKeyboardColor.BLUE)
    keyboard.add_button('⏳ Ожидает оплаты', color=VkKeyboardColor.YELLOW)
    
    keyboard.add_line()
    keyboard.add_button('🚀 Готов к выдаче', color=VkKeyboardColor.GREEN)
    keyboard.add_button('❌ Отменён', color=VkKeyboardColor.RED)
    
    keyboard.add_line()
    keyboard.add_button(f'📝 Заказ #{order_id}', color=VkKeyboardColor.SECONDARY)
    
    return keyboard.get_keyboard()


def get_yes_no_keyboard():
    """Клавиатура Да/Нет"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('✅ Да', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('❌ Нет', color=VkKeyboardColor.NEGATIVE)
    
    return keyboard.get_keyboard()


def get_back_keyboard():
    """Клавиатура с кнопкой Назад"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('↩️ Назад', color=VkKeyboardColor.SECONDARY)
    
    return keyboard.get_keyboard()
