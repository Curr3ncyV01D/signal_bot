from aiogram.utils.markdown import hbold, hcode

class BIFormatter:
    @staticmethod
    def create_progress_bar(percent: float, length: int = 10) -> str:
        """Генерирует текстовую полоску нагрузки."""
        filled_length = int(length * percent / 100)
        if filled_length >= length:
            bar = '▬' * (length - 1) + '🔘'
        elif filled_length <= 0:
            bar = '🔘' + '▬' * (length - 1)
        else:
            bar = '▬' * filled_length + '🔘' + '▬' * (length - filled_length - 1)
        return f"[{bar}]"

    @classmethod
    def format_finance_text(cls, data: dict) -> str:
        """Форматирует финансовый блок (USDT)."""
        delta_emoji = "📈" if data['delta_24h'] >= 0 else "📉"
        
        return (
            f"💰 {hbold('Финансовая аналитика')}\n\n"
            f"💸 {hbold('Оборот (DEPOSIT):')}\n"
            f"  ├ 24ч: {hbold(data['turnover_24h'])} $ ({delta_emoji} {data['delta_24h']}% по сравнению с предыдущими 24ч)\n"
            f"  ├ 48ч: {hbold(data['turnover_48h'])} $\n"
            f"  ├ 7д: {hbold(data['turnover_7d'])} $\n"
            f"  └ Всего: {hbold(data['turnover_total'])} $\n\n"
            f"💎 {hbold('ARPU:')} {hbold(data['arpu'])} $ / пользователь\n\n"
            f"🎁 {hbold('Выплачено бонусов:')} {hbold(data['rewards_total'])} $\n"
            f"💳 {hbold('Всего денег во всех кошельках:')} {hbold(data['bonus_debt'])} $\n\n"
        )

    @classmethod
    def format_audience_text(cls, data: dict) -> str:
        """Форматирует блок аудитории."""
        top_refs = ""
        if data['top_referrers']:
            for i, ref in enumerate(data['top_referrers'], 1):
                top_refs += f"  {i}. {ref['name']} — {hbold(ref['count'])} чел.\n"
        else:
            top_refs = "  (пока пусто)\n"

        return (
            f"👥 {hbold('Аналитика аудитории')}\n\n"
            f"📊 {hbold('Пользователи:')}\n"
            f"  ├ VIP-активных: {hbold(data['active_vip'])}\n"
            f"  └ Всего: {hbold(data['total_users'])}\n\n"
            f"🎯 {hbold('Конверсия Trial-to-Paid:')} {hbold(data['conversion_rate'])}%\n"
            f"  ├ Использовали пробный период: {data['trial_users_count']}\n"
            f"  └ Купили после: {data['paid_from_trial_count']}\n\n"
            f"🏆 {hbold('ТОП-3 Реферера:')}\n{top_refs}\n"
            f"🌍 {hbold('Языки:')} 100% Русский\n\n"
        )

    @classmethod
    def format_system_text(cls, data: dict) -> str:
        """Форматирует технический блок."""
        cpu_bar = cls.create_progress_bar(data['cpu_usage'])
        ram_bar = cls.create_progress_bar(data['ram_usage'])
        
        conn_status = "✅" if data['active_connections'] >= max(1, data['total_connections'] * 3 / 4) else "⚠️"
        if data['active_connections'] == 0: conn_status = "❌"

        queue_size = data["queue_size"]
        queue_status = "🟢" if queue_size < 50 else "🟡" if queue_size < 200 else "🔴"
        
        return (
            f"⚙️ {hbold('Техническое состояние')}\n\n"
            f"🖥 {hbold('Нагрузка сервера:')}\n"
            f"  ├ CPU: {cpu_bar} {hbold(data['cpu_usage'])}%\n"
            f"  └ RAM: {ram_bar} {hbold(data['ram_usage'])}%\n\n"
            f"🌐 {hbold('Инфраструктура:')}\n"
            f"  ├ Соединения: {conn_status} {hbold(data['active_connections'])}/{hbold(data['total_connections'])}\n"
            f"  ├ Последний сигнал API: {hbold(data['latency'])} назад\n"
            f"  ├ Очередь обработки: {queue_status} {hbold(data['queue_size'])}\n"
            f"  └ Событий в кэше: {hbold(data['total_events'])}\n\n"
            f"💓 {hbold('Время работы:')} {hbold(data['uptime'])}\n"
            f"🕒 Время сервера: {data['server_time']} UTC"
        )
