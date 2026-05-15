-- =====================================================
-- Тестовые данные: партнёры по районам Бали
-- Применять: 
-- Get-Content "путь\test_partners.sql" | docker exec -i restobot_db psql -U restobot_db -d restobot_db
-- =====================================================

-- Очищаем старые тестовые данные (если нужно)
-- DELETE FROM restaurant WHERE region_nm IN ('Canggu', 'Ubud', 'Seminyak', 'Uluwatu');

-- =====================================================
-- CANGGU
-- =====================================================

INSERT INTO restaurant (restaurant_id, restaurant_name, address_nm, reservation, delivery, region_nm, category, banquet_flg, menu, promo)
VALUES
-- Рестораны/Кафе/Бары
(100, 'Canggu Kitchen', 'Jl. Batu Bolong No.69, Canggu', '+62 812-3456-7890', 'Gojek, Grab', 'Canggu', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(101, 'The Shady Shack', 'Jl. Tanah Barak No.57, Canggu', '+62 812-1111-2222', 'Gojek', 'Canggu', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),
(102, 'Betelnut Café', 'Jl. Pantai Batu Bolong, Canggu', '+62 813-2222-3333', '-', 'Canggu', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),

-- Отели
(103, 'Desa Potato Head', 'Jl. Petitenget No.51B, Canggu', '+62 361-473-7979', '-', 'Canggu', 'Отели', 'Да', 0, NULL),
(104, 'The Layar Canggu', 'Jl. Umalas II No.7, Canggu', '+62 361-847-5816', '-', 'Canggu', 'Отели', 'Да', 0, NULL),

-- СПА/Бани
(105, 'Sundari Day Spa', 'Jl. Raya Canggu No.10, Canggu', '+62 361-844-6806', '-', 'Canggu', 'СПА/Бани', 'Нет', 0, NULL),
(106, 'Serenity Spa Canggu', 'Jl. Batu Mejan No.8, Canggu', '+62 812-3333-4444', '-', 'Canggu', 'СПА/Бани', 'Нет', 0, NULL),

-- GYM
(107, 'Canggu Fitness Club', 'Jl. Raya Canggu No.88, Canggu', '+62 812-4444-5555', '-', 'Canggu', 'GYM', 'Нет', 0, NULL),
(108, 'CrossFit Canggu', 'Jl. Batu Bolong No.30, Canggu', '+62 813-5555-6666', '-', 'Canggu', 'GYM', 'Нет', 0, NULL),

-- Салоны красоты
(109, 'Canggu Beauty Lounge', 'Jl. Raya Canggu No.15, Canggu', '+62 812-6666-7777', '-', 'Canggu', 'Салоны красоты', 'Нет', 0, NULL),

-- Магазины
(110, 'Canggu Market', 'Jl. Pantai Batu Bolong No.5, Canggu', '+62 812-7777-8888', '-', 'Canggu', 'Магазины', 'Нет', 0, NULL),

-- Аренда вилл и сервисы
(111, 'Canggu Villa Rentals', 'Jl. Batu Mejan No.20, Canggu', '+62 812-8888-9999', '-', 'Canggu', 'Аренда вилл и сервисы', 'Нет', 0, NULL),

-- =====================================================
-- UBUD
-- =====================================================

-- Рестораны/Кафе/Бары
(200, 'Locavore', 'Jl. Dewi Sita No.17, Ubud', '+62 361-977-733', '-', 'Ubud', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(201, 'Penestanan Kitchen', 'Jl. Penestanan, Ubud', '+62 812-1234-5678', 'Gojek', 'Ubud', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),
(202, 'Bali Buda', 'Jl. Jembawan No.1, Ubud', '+62 361-976-324', '-', 'Ubud', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),

-- Отели
(203, 'Komaneka at Bisma', 'Jl. Bisma, Ubud', '+62 361-971-933', '-', 'Ubud', 'Отели', 'Да', 0, NULL),
(204, 'Alaya Resort Ubud', 'Jl. Hanoman No.89, Ubud', '+62 361-972-200', '-', 'Ubud', 'Отели', 'Да', 0, NULL),

-- СПА/Бани
(205, 'COMO Shambhala', 'Banjar Begawan, Ubud', '+62 361-978-888', '-', 'Ubud', 'СПА/Бани', 'Нет', 0, NULL),
(206, 'Karsa Spa', 'Jl. Raya Sanggingan, Ubud', '+62 361-977-578', '-', 'Ubud', 'СПА/Бани', 'Нет', 0, NULL),

-- GYM
(207, 'Ubud Fitness Center', 'Jl. Monkey Forest No.11, Ubud', '+62 812-9999-0000', '-', 'Ubud', 'GYM', 'Нет', 0, NULL),

-- Салоны красоты
(208, 'Ubud Beauty Studio', 'Jl. Dewi Sita No.5, Ubud', '+62 812-0000-1111', '-', 'Ubud', 'Салоны красоты', 'Нет', 0, NULL),

-- Аренда вилл и сервисы
(209, 'Ubud Villa Collection', 'Jl. Raya Ubud No.35, Ubud', '+62 361-975-000', '-', 'Ubud', 'Аренда вилл и сервисы', 'Да', 0, NULL),

-- =====================================================
-- SEMINYAK
-- =====================================================

-- Рестораны/Кафе/Бары
(300, 'Sarong Restaurant', 'Jl. Petitenget No.19X, Seminyak', '+62 361-473-7809', '-', 'Seminyak', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(301, 'La Lucciola', 'Jl. Kayu Aya, Seminyak', '+62 361-730-838', '-', 'Seminyak', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(302, 'Motel Mexicola', 'Jl. Kayu Jati No.9X, Seminyak', '+62 361-736-688', '-', 'Seminyak', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),

-- Отели
(303, 'W Bali Seminyak', 'Jl. Petitenget, Seminyak', '+62 361-473-8106', '-', 'Seminyak', 'Отели', 'Да', 0, NULL),
(304, 'The Layar Seminyak', 'Jl. Drupadi No.XX, Seminyak', '+62 361-738-840', '-', 'Seminyak', 'Отели', 'Да', 0, NULL),

-- СПА/Бани
(305, 'Prana Spa', 'Jl. Kunti No.118X, Seminyak', '+62 361-730-840', '-', 'Seminyak', 'СПА/Бани', 'Нет', 0, NULL),
(306, 'Bodyworks Seminyak', 'Jl. Kayu Aya No.2, Seminyak', '+62 361-733-317', '-', 'Seminyak', 'СПА/Бани', 'Нет', 0, NULL),

-- GYM
(307, 'Seminyak Fitness', 'Jl. Raya Seminyak No.17, Seminyak', '+62 812-1122-3344', '-', 'Seminyak', 'GYM', 'Нет', 0, NULL),

-- Салоны красоты
(308, 'Seminyak Hair & Beauty', 'Jl. Laksmana No.33, Seminyak', '+62 812-2233-4455', '-', 'Seminyak', 'Салоны красоты', 'Нет', 0, NULL),

-- Магазины
(309, 'Seminyak Square', 'Jl. Raya Seminyak No.17, Seminyak', '+62 361-730-552', '-', 'Seminyak', 'Магазины', 'Нет', 0, NULL),
(310, 'Biasa Artisan', 'Jl. Raya Seminyak No.36, Seminyak', '+62 361-730-308', '-', 'Seminyak', 'Магазины', 'Нет', 0, NULL),

-- Аренда вилл и сервисы
(311, 'Seminyak Villas', 'Jl. Petitenget No.100, Seminyak', '+62 361-730-000', '-', 'Seminyak', 'Аренда вилл и сервисы', 'Да', 0, NULL),

-- =====================================================
-- ULUWATU
-- =====================================================

-- Рестораны/Кафе/Бары
(400, 'Single Fin', 'Jl. Mamo, Uluwatu', '+62 361-769-941', '-', 'Uluwatu', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(401, 'Ulu Cliff House', 'Jl. Labuansait, Uluwatu', '+62 812-3344-5566', '-', 'Uluwatu', 'Рестораны/Кафе/Бары', 'Да', 0, NULL),
(402, 'Sundays Beach Club', 'Jl. Pantai Selatan Gau, Uluwatu', '+62 361-848-2111', '-', 'Uluwatu', 'Рестораны/Кафе/Бары', 'Нет', 0, NULL),

-- Отели
(403, 'Alila Villas Uluwatu', 'Jl. Belimbing Sari, Uluwatu', '+62 361-848-2166', '-', 'Uluwatu', 'Отели', 'Да', 0, NULL),
(404, 'Anantara Uluwatu', 'Jl. Pemutih, Uluwatu', '+62 361-895-7555', '-', 'Uluwatu', 'Отели', 'Да', 0, NULL),

-- СПА/Бани
(405, 'Karma Spa Uluwatu', 'Jl. Yoga Perkanthi, Uluwatu', '+62 361-848-2200', '-', 'Uluwatu', 'СПА/Бани', 'Нет', 0, NULL),
(406, 'The Istana Spa', 'Jl. Labuansait No.5, Uluwatu', '+62 812-4455-6677', '-', 'Uluwatu', 'СПА/Бани', 'Нет', 0, NULL),

-- GYM
(407, 'Uluwatu Fitness', 'Jl. Raya Uluwatu No.10, Uluwatu', '+62 812-5566-7788', '-', 'Uluwatu', 'GYM', 'Нет', 0, NULL),

-- Салоны красоты
(408, 'Uluwatu Beauty Bar', 'Jl. Labuansait No.12, Uluwatu', '+62 812-6677-8899', '-', 'Uluwatu', 'Салоны красоты', 'Нет', 0, NULL),

-- Аренда вилл и сервисы
(409, 'Uluwatu Cliff Villas', 'Jl. Pantai Selatan, Uluwatu', '+62 361-848-0000', '-', 'Uluwatu', 'Аренда вилл и сервисы', 'Да', 0, NULL),
(410, 'Bali South Rentals', 'Jl. Mamo No.5, Uluwatu', '+62 812-7788-9900', '-', 'Uluwatu', 'Аренда вилл и сервисы', 'Нет', 0, NULL);

-- =====================================================
-- Проверка: сколько партнёров по районам и категориям
-- =====================================================
SELECT region_nm, category, COUNT(*) as count
FROM restaurant
WHERE region_nm IN ('Canggu', 'Ubud', 'Seminyak', 'Uluwatu')
GROUP BY region_nm, category
ORDER BY region_nm, category;