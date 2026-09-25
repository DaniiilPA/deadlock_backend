
class DomainException(Exception):
    def __init__(self, message: str = "Ошибка бизнес-логики"):
        self.message = message
        super().__init__(self.message)

class EntityNotFoundException(DomainException):
    pass

class ProjectNotFoundException(EntityNotFoundException):
    def __init__(self, project_id):
        super().__init__(f"Проект {project_id} не найден")

class ScheduleNotFoundException(EntityNotFoundException):
    def __init__(self, schedule_id):
        super().__init__(f"Этап графика {schedule_id} не найден")

class InvalidProjectStatusException(DomainException):
    pass

class TemplatesNotFoundException(DomainException):
    pass