import asyncio
import csv
import logging
import os
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import (
    EquipmentType,
    ProjectType,
    StageTemplate,
    User,
)
from app.db.session import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")

EQUIPMENT_MAP = {
    "BULLDOZER": "bulldozer",
    "DUMP_TRUCK": "dump_truck",
    "EXCAVATOR": "excavator",
    "ROAD_ROLLER": "road_roller",
    "CONCRETE_MIXER": "concrete_mixer",
    "MOBILE_CRANE": "mobile_crane",
    "FLATBED_TRUCK": "truck",
    "TOWER_CRANE": "tower_crane",
    "LOADER_CRANE": "loader_crane",
    "CONCRETE_PUMP": "concrete_pump",
    "SKID_STEER_LOADER": "skid_steer_loader",
    "BACKHOE_LOADER": "backhoe_loader",
    "FRONT_LOADER": "front_loader",
}

PROJECT_TYPE_MAPPING = {
    "RESIDENTIAL": [
        ("residential_building", "Жилой дом", "Многоквартирные жилые здания"),
    ],
    "ADMINISTRATIVE": [
        ("administrative", "Административное здание", "Офисные и муниципальные здания"),
    ],
    "BUSINESS": [
        ("business", "Технопарк и бизнес-центр", "Многофункциональные деловые комплексы"),
        ("parking", "Многоуровневый паркинг", "Гаражи и стояночные комплексы"),
    ],
    "EDUCATION": [
        ("school", "Школа", "Общеобразовательные учреждения"),
    ],
    "KINDERGARTEN": [
        ("kindergarten", "Детский сад", "Дошкольные образовательные учреждения"),
    ],
    "HEALTHCARE": [
        ("hospital", "Больница", "Лечебно-профилактические комплексы"),
        ("polyclinic", "Поликлиника", "Амбулаторные медицинские центры"),
    ],
    "SPORTS_FACILITY": [
        ("sports_complex", "Спортивный комплекс", "Физкультурно-оздоровительные сооружения и бассейны"),
    ],
    "CULTURE": [
        ("culture", "Объект культуры", "Дома культуры, театры и концертные залы"),
    ],
    "ROAD_CONSTRUCTION": [
        ("road", "Автомобильная дорога", "Дорожно-транспортная инфраструктура"),
        ("bridge", "Мостовое сооружение", "Мосты, путепроводы и эстакады"),
    ],
}


def parse_required_equipment(raw_text: str) -> list[dict]:
    """Парсинг строки вида 'BULLDOZER: 1, DUMP_TRUCK: 2'"""
    if not raw_text or not raw_text.strip():
        return []
    result = []
    items = raw_text.split(",")
    for item in items:
        item = item.strip()
        if ":" in item:
            eq_type, count_str = item.split(":", 1)
            eq_type = eq_type.strip().upper()
            try:
                count = int(count_str.strip())
            except ValueError:
                count = 1
            code = EQUIPMENT_MAP.get(eq_type, eq_type.lower())
            result.append({"equipment_type_code": code, "default_count": count})
    return result


def parse_allowed_equipment(raw_text: str) -> list[str]:
    """Парсинг строки вида 'EXCAVATOR, DUMP_TRUCK'"""
    if not raw_text or not raw_text.strip():
        return []
    result = []
    for item in raw_text.split(","):
        item = item.strip().upper()
        if item:
            code = EQUIPMENT_MAP.get(item, item.lower())
            result.append(code)
    return result


async def seed() -> None:
    logger.info("Запуск сидирования базы данных...")
    async with AsyncSessionLocal() as session:
        users_data = [
            ("admin@build.ru", "admin12345", "Сергей", "Собянин", ["admin"]),
            ("engineer@build.ru", "engineer123", "Иван", "Инженеров", ["engineer"]),
            ("foreman@build.ru", "foreman123", "Петр", "Прорабов", ["foreman"]),
        ]
        for email, pwd, first_name, last_name, roles in users_data:
            existing = await session.scalar(select(User).where(User.email == email))
            if not existing:
                user = User(
                    email=email,
                    password_hash=hash_password(pwd),
                    first_name=first_name,
                    last_name=last_name,
                    roles=roles,
                )
                session.add(user)
                logger.info("Создан пользователь: %s (%s)", email, roles)

        equipment_data = [
            ("excavator", "Экскаватор", ["excavator", "digger"]),
            ("dump_truck", "Самосвал", ["dump_truck", "truck"]),
            ("bulldozer", "Бульдозер", ["bulldozer", "dozer"]),
            ("road_roller", "Дорожный каток", ["road_roller", "roller"]),
            ("front_loader", "Фронтальный погрузчик", ["front_loader"]),
            ("concrete_mixer", "Автобетоносмеситель", ["concrete_mixer", "mixer"]),
            ("truck", "Грузовик / длинномер", ["truck", "flatbed_truck"]),
            ("mobile_crane", "Автокран", ["mobile_crane"]),
            ("tower_crane", "Башенный кран", ["tower_crane", "crane"]),
            ("loader_crane", "Кран-манипулятор", ["loader_crane"]),
            ("concrete_pump", "Бетононасос", ["concrete_pump"]),
            ("skid_steer_loader", "Мини-погрузчик", ["skid_steer_loader"]),
            ("backhoe_loader", "Экскаватор-погрузчик", ["backhoe_loader"]),
        ]
        for code, name, ml_classes in equipment_data:
            existing = await session.scalar(select(EquipmentType).where(EquipmentType.code == code))
            if not existing:
                session.add(EquipmentType(code=code, name=name, ml_class_names=ml_classes))
                logger.info("Добавлена техника: %s [%s]", name, code)

        for csv_code, type_variants in PROJECT_TYPE_MAPPING.items():
            for code, name, desc in type_variants:
                existing = await session.scalar(select(ProjectType).where(ProjectType.code == code))
                if not existing:
                    session.add(ProjectType(code=code, name=name, description=desc))
                    logger.info("Добавлен тип объекта: %s (%s)", name, code)

        await session.flush()

        csv_path = "стройка.csv"
        if not os.path.exists(csv_path):
            csv_path = "stages.csv"

        if not os.path.exists(csv_path):
            logger.error("Файл стройка.csv не найден в корне проекта!")
            return

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info("Прочитано %d строк из %s", len(rows), csv_path)

        stages_by_type = {}
        for row in rows:
            csv_type = row.get("Тип объекта (project_type_code)", "").strip()
            if not csv_type:
                continue
            stages_by_type.setdefault(csv_type, []).append(row)

        for csv_type, stage_rows in stages_by_type.items():
            db_type_variants = PROJECT_TYPE_MAPPING.get(csv_type, [(csv_type.lower(), csv_type, "")])

            for db_code, _, _ in db_type_variants:
                ptype = await session.scalar(select(ProjectType).where(ProjectType.code == db_code))
                if not ptype:
                    continue
                
                existing_templates = (await session.scalars(
                    select(StageTemplate).where(StageTemplate.type_id == ptype.id)
                )).all()
                for old in existing_templates:
                    await session.delete(old)

                for idx, row in enumerate(stage_rows, start=1):
                    major = row.get("Крупный этап", "").strip()
                    sub = row.get("Подэтап СМР", "").strip()
                    duration = int(row.get("Длительность (дней)", "7").strip() or 7)
                    is_crit = row.get("Критический путь", "").strip().upper() == "TRUE"
                    req_eq = parse_required_equipment(row.get("Обязательная техника", ""))
                    allowed_eq = parse_allowed_equipment(row.get("Допустимая техника", ""))
                    risks = row.get("Контролируемые аномалии и риски (Алерты)", "").strip() or None

                    tmpl = StageTemplate(
                        type_id=ptype.id,
                        stage_name=major,
                        substage_name=sub,
                        sequence_order=idx,
                        default_duration_days=duration,
                        is_critical_path=is_crit,
                        allowed_equipment=allowed_eq,
                        alerts_and_risks=risks,
                        default_equipment=req_eq,
                    )
                    session.add(tmpl)

                logger.info("Загружено %d этапов для типа ОКС: %s", len(stage_rows), db_code)

        await session.commit()
    logger.info("База успешно наполнена всеми 9 типами строек")


if __name__ == "__main__":
    asyncio.run(seed())