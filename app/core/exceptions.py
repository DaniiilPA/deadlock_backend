from app.core.security import AppException


class DomainException(AppException):
    def __init__(self, message: str = "Ошибка бизнес-логики", code: str = "DOMAIN_ERROR", status_code: int = 400):
        super().__init__(message=message)
        self.code = code
        self.status_code = status_code
        self.details = None


class EntityNotFoundException(DomainException):
    def __init__(self, message: str = "Объект не найден", code: str = "NOT_FOUND"):
        super().__init__(message=message, code=code, status_code=404)


class ProjectNotFoundException(EntityNotFoundException):
    def __init__(self, project_id):
        super().__init__(message=f"Проект {project_id} не найден", code="PROJECT_NOT_FOUND")


class ScheduleNotFoundException(EntityNotFoundException):
    def __init__(self, schedule_id):
        super().__init__(message=f"Этап графика {schedule_id} не найден", code="SCHEDULE_NOT_FOUND")


class InvalidProjectStatusException(DomainException):
    def __init__(self, message: str):
        super().__init__(message=message, code="INVALID_PROJECT_STATUS")


class TemplatesNotFoundException(DomainException):
    def __init__(self, message: str):
        super().__init__(message=message, code="TEMPLATES_NOT_FOUND")