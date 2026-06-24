#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Определяем текущую ветку
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo -e "${YELLOW}🚀 --- Обновление Gruzbery Screener [Ветка: $CURRENT_BRANCH] ---${NC}"

# Загружаем переменные из .env (чтобы знать PROJECT_NAME)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${RED}❌ Ошибка: Файл .env не найден!${NC}"
    exit 1
fi

echo -e "${GREEN}📥 Тянем код из ветки $CURRENT_BRANCH...${NC}"
git pull origin $CURRENT_BRANCH

echo -e "${GREEN}🏗 Пересборка контейнеров для проекта: $PROJECT_NAME...${NC}"
docker compose up -d --build

# Проверка запуска (сервис в compose называется "bot")
echo -e "${GREEN}⏳ Проверка запуска сервиса bot...${NC}"
sleep 5
STATE=$(docker compose ps bot --format "{{.State}}")

if [ "$STATE" == "running" ]; then
    echo -e "${GREEN}✅ Контейнер bot запущен (Проект: $PROJECT_NAME).${NC}"
    
    echo -e "${GREEN}📋 Применение миграций...${NC}"
    docker compose exec -T bot alembic upgrade head
else
    echo -e "${RED}❌ Ошибка запуска. Проверь логи: docker compose logs bot${NC}"
    exit 1
fi

echo -e "${GREEN}🧹 Удаление старых образов...${NC}"
docker image prune -f

echo -e "${GREEN}✅ Обновление завершено успешно!${NC}"