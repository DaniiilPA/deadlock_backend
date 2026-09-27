import asyncio
import json
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
}

PROJECT_TYPE_MAP = {
    "RESIDENTIAL": ("residential_building", "Жилой дом", "Многоквартирные жилые здания"),
    "ADMINISTRATIVE": ("administrative", "Административное здание", "Офисные и муниципальные здания"),
    "BUSINESS": ("business", "Технопарк и бизнес-центр", "Многофункциональные деловые комплексы"),
    "EDUCATION": ("school", "Общеобразовательная школа", "Учебные корпуса и спортивные ядра"),
    "KINDERGARTEN": ("kindergarten", "Детский сад", "Дошкольные образовательные учреждения"),
}


async def seed() -> None:
    logger.info("Запуск сидирования базы данных...")
    async with AsyncSessionLocal() as session:
        #Базовые пользователи
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

        #Все 13 классов техники от ML
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

        # Типы проектов
        all_types = [
            ("school", "Школа", "Общеобразовательные учреждения"),
            ("kindergarten", "Детский сад", "Дошкольные образовательные учреждения"),
            ("residential_building", "Жилой дом", "Многоквартирные жилые здания"),
            ("administrative", "Административное здание", "Офисные и муниципальные здания"),
            ("business", "Технопарк и бизнес-центр", "Многофункциональные деловые комплексы"),
            ("hospital", "Больница", "Лечебно-профилактические комплексы"),
            ("polyclinic", "Поликлиника", "Амбулаторные медицинские центры"),
            ("sports_complex", "Спортивный комплекс", "Физкультурно-оздоровительные сооружения"),
            ("road", "Автомобильная дорога", "Дорожно-транспортная инфраструктура"),
            ("bridge", "Мостовое сооружение", "Мосты, эстакады и путепроводы"),
            ("parking", "Многоуровневый паркинг", "Гаражи и стояночные комплексы"),
        ]
        for code, name, desc in all_types:
            existing = await session.scalar(select(ProjectType).where(ProjectType.code == code))
            if not existing:
                session.add(ProjectType(code=code, name=name, description=desc))
                logger.info("Добавлен тип проекта: %s (%s)", name, code)

        await session.flush()

        #Загрузка шаблонов из data.json
        data_file = "data.json"
        if not os.path.exists(data_file):
            logger.warning("Файл %s не найден! Шаблоны не загружены.", data_file)
        else:
            with open(data_file, "r", encoding="utf-8") as f:
                stages_data = json.load(f)

            project_type_cache = {}
            seq_counters = {}

            for item in stages_data:
                p_code = item["project_type_code"]
                db_code = PROJECT_TYPE_MAP.get(p_code, (p_code.lower(),))[0]

                if db_code not in project_type_cache:
                    ptype = await session.scalar(select(ProjectType).where(ProjectType.code == db_code))
                    project_type_cache[db_code] = ptype

                ptype = project_type_cache.get(db_code)
                if not ptype:
                    continue

                seq_counters[db_code] = seq_counters.get(db_code, 0) + 1
                seq = seq_counters[db_code]

                req_eq = []
                for eq in item.get("required_equipment", []):
                    code = EQUIPMENT_MAP.get(eq["type"], eq["type"].lower())
                    req_eq.append({"equipment_type_code": code, "default_count": eq["count"]})

                allowed_eq = [
                    EQUIPMENT_MAP.get(eq_type, eq_type.lower())
                    for eq_type in item.get("allowed_equipment", [])
                ]

                existing_tmpl = await session.scalar(
                    select(StageTemplate).where(
                        StageTemplate.type_id == ptype.id,
                        StageTemplate.sequence_order == seq,
                    )
                )

                if not existing_tmpl:
                    tmpl = StageTemplate(
                        type_id=ptype.id,
                        stage_name=item["major_stage"],
                        substage_name=item["sub_stage"],
                        sequence_order=seq,
                        default_duration_days=item["duration_days"],
                        is_critical_path=item.get("is_critical_path", False),
                        allowed_equipment=allowed_eq,
                        alerts_and_risks=item.get("alerts_and_risks"),
                        default_equipment=req_eq,
                    )
                    session.add(tmpl)
                else:
                    existing_tmpl.stage_name = item["major_stage"]
                    existing_tmpl.substage_name = item["sub_stage"]
                    existing_tmpl.default_duration_days = item["duration_days"]
                    existing_tmpl.is_critical_path = item.get("is_critical_path", False)
                    existing_tmpl.allowed_equipment = allowed_eq
                    existing_tmpl.alerts_and_risks = item.get("alerts_and_risks")
                    existing_tmpl.default_equipment = req_eq

            logger.info("Успешно загружено %d этапов из %s", len(stages_data), data_file)

        await session.commit()
    logger.info("Сидирование базы данных успешно завершено!")


if __name__ == "__main__":
    asyncio.run(seed())