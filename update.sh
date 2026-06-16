#!/bin/bash

# Остановить скрипт при любой ошибке
set -e

# Цвета для вывода (для красоты и наглядности)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 --- Начало обновления Gruzbery Screener ---${NC}"

# 1. Проверка, что мы в нужной папке (где есть docker-compose.yml)
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Ошибка: Файл docker-compose.yml не найден. Запустите скрипт из корня проекта.${NC}"
    exit 1
fi

# 2. Загрузка кода
echo -e "${GREEN}📥 Получение обновлений из GitHub...${NC}"
# Если были локальные мелкие правки, git pull может упасть. 
# Можно добавить git stash перед пулом, если это необходимо.
git pull origin dev

# 3. Сборка образов
echo -e "${GREEN}🏗 Сборка и запуск Docker контейнеров...${NC}"
docker compose up -d --build

# 4. Ожидание готовности контейнера
echo -e "${GREEN}⏳ Ожидание запуска контейнера bot...${NC}"
MAX_RETRIES=15
COUNT=0

while [ "$COUNT" -lt "$MAX_RETRIES" ]; do
    # Пытаемся получить статус контейнера bot (или того, что указан в compose как сервис)
    STATE=$(docker compose ps bot --format "{{.State}}")
    
    if [ "$STATE" == "running" ]; then
        echo -e "${GREEN}✅ Контейнер bot запущен.${NC}"
        break
    fi

    echo -e "${YELLOW}... статус: $STATE, ждем 2 сек... ($((COUNT+1))/$MAX_RETRIES)${NC}"
    sleep 2
    COUNT=$((COUNT + 1))
done

if [ "$COUNT" -eq "$MAX_RETRIES" ]; then
    echo -e "${RED}❌ Ошибка: Контейнер не перешел в статус running за отведенное время.${NC}"
    docker compose logs bot --tail=20
    exit 1
fi

# 5. Миграции базы данных
echo -e "${GREEN}📋 Применение миграций БД (Alembic)...${NC}"
# Выполняем upgrade head внутри контейнера
docker compose exec -T bot alembic upgrade head

# 6. Очистка старых слоев и неиспользуемых образов (чтобы не забивать диск сервера)
echo -e "${GREEN}🧹 Очистка мусора...${NC}"
docker image prune -f

echo -e "${YELLOW}📊 Текущий статус контейнеров:${NC}"
docker compose ps

echo -e "${GREEN}✅ --- Проект успешно обновлен и запущен! ---${NC}"
