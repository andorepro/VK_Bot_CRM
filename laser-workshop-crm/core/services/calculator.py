"""
Калькуляторы стоимости для 11 типов расчётов
"""
import math

class Calculator:
    """Базовый класс калькулятора"""
    
    @staticmethod
    def calculate(calc_type, params):
        """
        Расчёт стоимости на основе типа калькуляции и параметров
        
        :param calc_type: тип расчёта (fixed, area_cm2, etc.)
        :param params: словарь с параметрами
        :return: float - стоимость
        """
        calculators = {
            'fixed': Calculator.fixed,
            'area_cm2': Calculator.area_cm2,
            'meter_thickness': Calculator.meter_thickness,
            'per_minute': Calculator.per_minute,
            'per_char': Calculator.per_char,
            'vector_length': Calculator.vector_length,
            'setup_batch': Calculator.setup_batch,
            'photo_raster': Calculator.photo_raster,
            'cylindrical': Calculator.cylindrical,
            'volume_3d': Calculator.volume_3d,
            'material_and_cut': Calculator.material_and_cut
        }
        
        if calc_type not in calculators:
            raise ValueError(f"Неизвестный тип расчёта: {calc_type}")
        
        return calculators[calc_type](params)
    
    @staticmethod
    def fixed(params):
        """
        2.1 Штучный товар (Фляжки, жетоны)
        Фиксированная цена за единицу
        """
        quantity = params.get('quantity', 1)
        base_price = params.get('base_price', 0)
        return base_price * quantity
    
    @staticmethod
    def area_cm2(params):
        """
        2.2 Шильды/Дерево
        (Длина/10 * Ширина/10) * Цена за см²
        Параметры: length_mm, width_mm, price_per_cm2, quantity
        """
        length_mm = params.get('length_mm', 0)
        width_mm = params.get('width_mm', 0)
        price_per_cm2 = params.get('price_per_cm2', 0)
        quantity = params.get('quantity', 1)
        
        area_cm2 = (length_mm / 10) * (width_mm / 10)
        return area_cm2 * price_per_cm2 * quantity
    
    @staticmethod
    def meter_thickness(params):
        """
        2.3 Резка фанеры Ortur
        Метры реза * (Цена * (Толщина_мм / 3.0))
        Параметры: cut_length_m, thickness_mm, base_price
        """
        cut_length_m = params.get('cut_length_m', 0)
        thickness_mm = params.get('thickness_mm', 3)
        base_price = params.get('base_price', 0)
        
        multiplier = thickness_mm / 3.0
        return cut_length_m * (base_price * multiplier)
    
    @staticmethod
    def per_minute(params):
        """
        2.4 Долгая гравировка JPT
        Минуты работы * Цена за минуту
        Параметры: minutes, price_per_minute
        """
        minutes = params.get('minutes', 0)
        price_per_minute = params.get('price_per_minute', 0)
        return minutes * price_per_minute
    
    @staticmethod
    def per_char(params):
        """
        2.5 Кольца/Ручки
        Кол-во символов * Цена за символ
        Параметры: char_count, price_per_char, quantity
        """
        char_count = params.get('char_count', 0)
        price_per_char = params.get('price_per_char', 0)
        quantity = params.get('quantity', 1)
        return char_count * price_per_char * quantity
    
    @staticmethod
    def vector_length(params):
        """
        2.6 Пром. резка
        Длина вектора в метрах * Цена
        Параметры: vector_length_m, price_per_meter
        """
        vector_length_m = params.get('vector_length_m', 0)
        price_per_meter = params.get('price_per_meter', 0)
        return vector_length_m * price_per_meter
    
    @staticmethod
    def setup_batch(params):
        """
        2.7 B2B тираж
        Настройка станка + (Цена шт * Тираж)
        Параметры: setup_cost, price_per_unit, quantity
        """
        setup_cost = params.get('setup_cost', 0)
        price_per_unit = params.get('price_per_unit', 0)
        quantity = params.get('quantity', 0)
        return setup_cost + (price_per_unit * quantity)
    
    @staticmethod
    def photo_raster(params):
        """
        2.8 Фото на дереве/металле
        Площадь * Цена * Коэфф DPI
        Параметры: length_mm, width_mm, base_price, dpi_coefficient
        """
        length_mm = params.get('length_mm', 0)
        width_mm = params.get('width_mm', 0)
        base_price = params.get('base_price', 0)
        dpi_coefficient = params.get('dpi_coefficient', 1.0)
        
        area_cm2 = (length_mm / 10) * (width_mm / 10)
        return area_cm2 * base_price * dpi_coefficient
    
    @staticmethod
    def cylindrical(params):
        """
        2.9 Термосы/Кружки (Ось)
        (Диаметр * 3.14 * Длина/100) * Цена
        Параметры: diameter_mm, length_mm, price_per_cm2
        """
        diameter_mm = params.get('diameter_mm', 0)
        length_mm = params.get('length_mm', 0)
        price_per_cm2 = params.get('price_per_cm2', 0)
        
        # Площадь поверхности цилиндра (боковая)
        circumference_cm = (diameter_mm * math.pi) / 10
        length_cm = length_mm / 10
        area_cm2 = circumference_cm * length_cm
        
        return area_cm2 * price_per_cm2
    
    @staticmethod
    def volume_3d(params):
        """
        2.10 3D-Клише (MOPA)
        Площадь * Глубина(мм) * Цена
        Параметры: length_mm, width_mm, depth_mm, price_per_mm3
        """
        length_mm = params.get('length_mm', 0)
        width_mm = params.get('width_mm', 0)
        depth_mm = params.get('depth_mm', 0)
        price_per_mm3 = params.get('price_per_mm3', 0)
        
        area_cm2 = (length_mm / 10) * (width_mm / 10)
        return area_cm2 * depth_mm * price_per_mm3
    
    @staticmethod
    def material_and_cut(params):
        """
        2.11 Материал + Рез
        Площадь фанеры * Цена + Рез * Цена
        Параметры: material_area_cm2, material_price, cut_length_m, cut_price
        """
        material_area_cm2 = params.get('material_area_cm2', 0)
        material_price = params.get('material_price', 0)
        cut_length_m = params.get('cut_length_m', 0)
        cut_price = params.get('cut_price', 0)
        
        material_cost = material_area_cm2 * material_price
        cut_cost = cut_length_m * cut_price
        
        return material_cost + cut_cost
    
    @staticmethod
    def apply_bulk_discount(base_price, quantity):
        """
        Применение оптовых скидок
        10 шт -5%, 20 шт -10%, 50 шт -15%, 100 шт -20%
        """
        discounts = {
            100: 0.20,
            50: 0.15,
            20: 0.10,
            10: 0.05
        }
        
        discount = 0
        for threshold, disc in sorted(discounts.items()):
            if quantity >= threshold:
                discount = disc
                break
        
        return base_price * (1 - discount)
    
    @staticmethod
    def apply_promo_code(price, promo_data):
        """
        Применение промокода
        """
        if not promo_data:
            return price
        
        discount_percent = promo_data.get('discount_percent', 0)
        return price * (1 - discount_percent / 100)
