# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем системные зависимости для pdf2image (poppler-utils)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем необходимые директории
RUN mkdir -p /app/logs /app/rest_menu /app/cache

# Указываем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Команда для запуска
CMD ["python", "main.py"]