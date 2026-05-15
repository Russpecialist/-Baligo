-- =====================================================
-- Миграция: добавление категорий партнёров для Бали
-- Применять: psql -U restobot_user -d restobot_db -f migration_categories.sql
-- =====================================================

-- 1. Добавляем колонку category в таблицу restaurant
ALTER TABLE public.restaurant
    ADD COLUMN IF NOT EXISTS category character varying(60);

-- 2. Существующим записям (рестораны) ставим категорию по умолчанию
UPDATE public.restaurant
    SET category = 'Рестораны/Кафе/Бары'
    WHERE category IS NULL;

-- 3. Добавляем районы Бали (если регионов ещё нет — вставляем пустые строки-маркеры;
--    реальных партнёров вы добавите через бот или напрямую в БД)
-- Просто убеждаемся что регионы используют правильные названия.
-- Если вы хотите полностью очистить тестовые данные — раскомментируйте строки ниже:

-- DELETE FROM public.promotions;
-- DELETE FROM public.events;
-- DELETE FROM public.promotion_event_approvals;
-- DELETE FROM public.restaurant_approvals;
-- DELETE FROM public.user_restaurants;
-- DELETE FROM public.restaurant;

-- 4. Создаём индекс для быстрой фильтрации по категории
CREATE INDEX IF NOT EXISTS idx_restaurant_category ON public.restaurant (category);
CREATE INDEX IF NOT EXISTS idx_restaurant_region_category ON public.restaurant (region_nm, category);

-- =====================================================
-- Список допустимых категорий (для справки):
--   'Рестораны/Кафе/Бары'
--   'Отели'
--   'СПА/Бани'
--   'GYM'
--   'Салоны красоты'
--   'Магазины'
--   'Аренда вилл и сервисы'
--
-- Районы Бали:
--   'Canggu'
--   'Ubud'
--   'Seminyak'
--   'Uluwatu'
-- =====================================================
