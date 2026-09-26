import asyncio
import logging
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


async def seed() -> None:
    logger.info("Starting database seeding")
    async with AsyncSessionLocal() as session:
        users_data = [
            ("admin@build.ru", "admin12345", "Сергей", "Собянин", ["admin"]),
            ("engineer@build.ru", "engineer123", "Иван", "Инженеров", ["engineer"]),
            ("foreman@build.ru", "foreman123", "Петр", "Прорабов", ["foreman"]),
        ]

        for email, pwd, first_name, last_name, roles in users_data:
            existing_user = await session.scalar(
                select(User).where(User.email == email)
            )
            if not existing_user:
                user = User(
                    email=email,
                    password_hash=hash_password(pwd),
                    first_name=first_name,
                    last_name=last_name,
                    roles=roles,
                )
                session.add(user)
                logger.info("User created: %s, roles: %s", email, roles)

        equipment_data = [
            ("excavator", "Гусеничный экскаватор", ["excavator", "digger"]),
            ("crane", "Башенный кран", ["crane", "tower_crane"]),
            ("dump_truck", "Самосвал", ["truck", "dump_truck"]),
            ("concrete_mixer", "Автобетоносмеситель", ["mixer", "concrete_truck"]),
            ("bulldozer", "Бульдозер", ["bulldozer"]),
        ]

        for code, name, ml_classes in equipment_data:
            existing_eq = await session.scalar(
                select(EquipmentType).where(EquipmentType.code == code)
            )
            if not existing_eq:
                eq = EquipmentType(
                    code=code,
                    name=name,
                    ml_class_names=ml_classes,
                )
                session.add(eq)
                logger.info("Equipment type added: %s (%s)", name, code)

        project_types_data = [
            ("school", "Школа", "Общеобразовательные учреждения"),
            ("kindergarten", "Детский сад", "Дошкольные образовательные учреждения"),
            ("hospital", "Больница", "Лечебно-профилактические комплексы"),
            ("polyclinic", "Поликлиника", "Амбулаторные медицинские центры"),
            ("sports_complex", "Спортивный комплекс", "Физкультурно-оздоровительные сооружения"),
            ("residential_building", "Жилой дом", "Многоквартирные жилые здания"),
            ("road", "Автомобильная дорога", "Дорожно-транспортная инфраструктура"),
            ("bridge", "Мостовое сооружение", "Мосты, эстакады и путепроводы"),
            ("parking", "Многоуровневый паркинг", "Гаражи и стояночные комплексы"),
        ]

        for code, name, desc in project_types_data:
            existing_type = await session.scalar(
                select(ProjectType).where(ProjectType.code == code)
            )
            if not existing_type:
                proj_type = ProjectType(
                    code=code,
                    name=name,
                    description=desc,
                )
                session.add(proj_type)
                logger.info("Project type added: %s (%s)", name, code)

        await session.flush()

        school_type = await session.scalar(
            select(ProjectType).where(ProjectType.code == "school")
        )
        if school_type:
            templates = [
                (
                    "Подготовительный этап",
                    "Земляные работы и устройство котлована",
                    1,
                    15,
                    [
                        {"equipment_type_code": "excavator", "default_count": 2},
                        {"equipment_type_code": "dump_truck", "default_count": 2},
                    ],
                ),
                (
                    "Нулевой цикл",
                    "Устройство фундамента и гидроизоляция",
                    2,
                    25,
                    [
                        {"equipment_type_code": "concrete_mixer", "default_count": 3},
                        {"equipment_type_code": "crane", "default_count": 1},
                    ],
                ),
                (
                    "Надземная часть",
                    "Возведение несущих конструкций и перекрытий",
                    3,
                    40,
                    [
                        {"equipment_type_code": "crane", "default_count": 2},
                        {"equipment_type_code": "concrete_mixer", "default_count": 2},
                    ],
                ),
            ]

            for s_name, sub_name, seq, dur, eq_req in templates:
                existing_tmpl = await session.scalar(
                    select(StageTemplate).where(
                        StageTemplate.type_id == school_type.id,
                        StageTemplate.sequence_order == seq,
                    )
                )
                if not existing_tmpl:
                    tmpl = StageTemplate(
                        type_id=school_type.id,
                        stage_name=s_name,
                        substage_name=sub_name,
                        sequence_order=seq,
                        default_duration_days=dur,
                        default_equipment=eq_req,
                    )
                    session.add(tmpl)
                    logger.info("Stage template added: #%d %s", seq, sub_name)

        await session.commit()
    logger.info("Database seeding completed successfully")


if __name__ == "__main__":
    asyncio.run(seed())