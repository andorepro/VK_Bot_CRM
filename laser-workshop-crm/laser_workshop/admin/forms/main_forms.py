# -*- coding: utf-8 -*-
"""
Формы админ панели Flask
Формы для входа, заказов, клиентов
"""

from wtforms import Form, StringField, PasswordField, SelectField, FloatField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class LoginForm(Form):
    """Форма входа"""
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6, max=100)])
    submit = SubmitField('Войти')


class OrderForm(Form):
    """Форма заказа"""
    service_type = SelectField('Тип услуги', choices=[
        ('cutting', 'Резка'),
        ('engraving', 'Гравировка'),
        ('marking', 'Маркировка')
    ], validators=[DataRequired()])
    
    material_type = SelectField('Материал', choices=[
        ('acrylic', 'Акрил'),
        ('wood', 'Дерево'),
        ('plastic', 'Пластик'),
        ('fabric', 'Ткань'),
        ('leather', 'Кожа')
    ], validators=[DataRequired()])
    
    thickness = FloatField('Толщина (мм)', validators=[DataRequired(), NumberRange(min=0.1, max=100)])
    area = FloatField('Площадь (см²)', validators=[DataRequired(), NumberRange(min=0.1)])
    quantity = IntegerField('Количество', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    price = FloatField('Цена (руб)', validators=[DataRequired(), NumberRange(min=0)])
    discount = FloatField('Скидка (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    comment = TextAreaField('Комментарий', validators=[Optional(), Length(max=500)])
    status = SelectField('Статус', choices=[
        ('new', 'Новый'),
        ('in_progress', 'В работе'),
        ('awaiting_payment', 'Ожидает оплаты'),
        ('ready', 'Готов к выдаче'),
        ('completed', 'Завершён'),
        ('cancelled', 'Отменён')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Сохранить')


class ClientForm(Form):
    """Форма клиента"""
    name = StringField('Имя', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Телефон', validators=[Optional(), Length(min=10, max=20)])
    email = StringField('Email', validators=[Optional(), Length(max=100)])
    vk_id = IntegerField('VK ID', validators=[Optional()])
    cashback = FloatField('Кэшбек (баллы)', validators=[Optional(), NumberRange(min=0)], default=0)
    comment = TextAreaField('Комментарий', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Сохранить')


class ServiceForm(Form):
    """Форма услуги"""
    name = StringField('Название', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Описание', validators=[Optional(), Length(max=500)])
    base_price = FloatField('Базовая цена', validators=[DataRequired(), NumberRange(min=0)])
    unit = StringField('Единица измерения', validators=[Optional(), Length(max=20)], default='см²')
    
    submit = SubmitField('Сохранить')


class StockForm(Form):
    """Форма складских остатков"""
    material_id = IntegerField('ID материала', validators=[DataRequired()])
    quantity = IntegerField('Количество', validators=[DataRequired(), NumberRange(min=0)])
    min_quantity = IntegerField('Мин. количество', validators=[DataRequired(), NumberRange(min=0)], default=10)
    
    submit = SubmitField('Сохранить')


class BroadcastForm(Form):
    """Форма рассылки"""
    subject = StringField('Тема', validators=[Optional(), Length(max=200)])
    message = TextAreaField('Сообщение', validators=[DataRequired(), Length(min=1, max=4096)])
    
    submit = SubmitField('Отправить')
