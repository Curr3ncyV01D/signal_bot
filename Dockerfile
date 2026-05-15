FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN echo "#!/bin/bash\nalembic upgrade head\npython -m src.main" > /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Запускаем через entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]