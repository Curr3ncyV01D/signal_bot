FROM python:3.13-slim

WORKDIR /app

# Устанавливаем системные зависимости:
# 1. libpq-dev — для PostgreSQL
# 2. fontconfig — для управления шрифтами
# 3. fonts-dejavu-core — стандартный качественный шрифт (Sans, Serif, Mono)
# 4. libfreetype6 — библиотека для рендеринга шрифтов (нужна для matplotlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    fontconfig \
    fonts-dejavu-core \
    libfreetype6 \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

COPY . .

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]