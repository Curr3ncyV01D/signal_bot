import asyncio
import time
import random
import os
from datetime import datetime, timedelta

# Настраиваем импорты, чтобы скрипт видел модули из src
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.rendering.chart_generator import _render_sync

def generate_dummy_ohlc(count=100):
    """Генерирует фейковые данные свечей (Random Walk)"""
    data = []
    current_price = 65000.0
    now = int(time.time() // 60) * 60
    
    for i in range(count):
        start_price = current_price
        # Случайное движение цены
        change = current_price * random.uniform(-0.005, 0.005)
        close_price = start_price + change
        high = max(start_price, close_price) + (abs(change) * 0.2)
        low = min(start_price, close_price) - (abs(change) * 0.2)
        vol = random.uniform(10000, 500000)
        
        data.append({
            "t": now - (count - i) * 60,
            "o": start_price,
            "h": high,
            "l": low,
            "c": close_price,
            "v": vol
        })
        current_price = close_price
        
    return data

async def main():
    print("🚀 Запуск теста отрисовки графика...")
    
    # 1. Генерируем данные (как будто из MarketAggregator)
    symbol = "BTCUSDT"
    alert_title = "QUICK SQUEEZE"
    dummy_data = generate_dummy_ohlc(100)
    
    print(f"📊 Сгенерировано {len(dummy_data)} свечей.")

    # 2. Вызываем функцию отрисовки
    # Мы вызываем синхронную версию напрямую для простоты теста
    try:
        start_time = time.perf_counter()
        
        # Передаем данные прямо в твою функцию рендеринга
        chart_bytes = _render_sync(dummy_data, symbol, alert_title)
        
        end_time = time.perf_counter()
        
        if chart_bytes:
            # 3. Сохраняем результат в файл
            output_path = "test_signal_chart.png"
            with open(output_path, "wb") as f:
                f.write(chart_bytes)
            
            print(f"✅ График успешно сохранен: {os.path.abspath(output_path)}")
            print(f"⏱ Время рендеринга: {end_time - start_time:.4f} сек.")
        else:
            print("❌ Ошибка: Функция вернула пустые байты.")
            
    except Exception as e:
        print(f"💥 Критическая ошибка при тесте: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())