class SecurityManager:
    """Глобальный менеджер безопасности для управления кешем блокировок в реальном времени."""
    blocked_users: set[int] = set()

    @classmethod
    def block(cls, user_id: int):
        """Добавляет пользователя в список заблокированных."""
        cls.blocked_users.add(user_id)

    @classmethod
    def unblock(cls, user_id: int):
        """Удаляет пользователя из списка заблокированных."""
        cls.blocked_users.discard(user_id)

    @classmethod
    def is_blocked(cls, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь."""
        return user_id in cls.blocked_users
