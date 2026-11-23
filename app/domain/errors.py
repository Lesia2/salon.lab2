"""Доменні помилки.

Нічого не знають про HTTP: Presentation-шар сам вирішує, у який статус-код
перетворити кожен тип помилки.
"""


class DomainError(Exception):
    """Базова доменна помилка."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvariantViolation(DomainError):
    """Порушено бізнес-правило або дані невалідні."""


class NotFound(DomainError):
    """Сутність не існує (або недоступна поточному користувачу)."""


class Conflict(DomainError):
    """Дія суперечить поточному стану системи."""


class PermissionDenied(DomainError):
    """У користувача немає прав на цю дію."""


class AuthenticationFailed(DomainError):
    """Невірні облікові дані."""


# ---------- Конкретні помилки ----------

class EmailAlreadyRegistered(Conflict):
    def __init__(self):
        super().__init__("Email вже зареєстрований")


class SlotAlreadyTaken(Conflict):
    def __init__(self):
        super().__init__("Цей час у майстра вже зайнятий")


class WorkingDayAlreadyExists(Conflict):
    def __init__(self):
        super().__init__("На цей день графік уже існує")


class SpecialistNotFound(NotFound):
    def __init__(self):
        super().__init__("Майстра не знайдено")


class WorkingDayNotFound(NotFound):
    def __init__(self):
        super().__init__("Запис графіка не знайдено")


class AppointmentNotFound(NotFound):
    def __init__(self):
        super().__init__("Запис не знайдено")
