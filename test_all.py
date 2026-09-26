import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
import traceback
import uuid
import httpx

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

ok_count = 0
err_count = 0


def step(text: str):
    print(f"\n{BOLD}>> {text}{RESET}")


def check(msg: str, condition: bool, err_info: str = ""):
    global ok_count, err_count
    if condition:
        ok_count += 1
        print(f"  {GREEN}✓{RESET} {msg}")
    else:
        err_count += 1
        print(f"  {RED}✗ {msg}{RESET}")
        if err_info:
            print(f"    {YELLOW}Ответ сервера:{RESET} {err_info}")


async def get_client():
    url = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1")
    try:
        async with httpx.AsyncClient(timeout=1.5) as test_conn:
            res = await test_conn.get("http://127.0.0.1:8000/api/v1/dictionaries/project-types")
            if res.status_code in (200, 401):
                print(f"Тестируем запущенный сервис на {url}")
                return httpx.AsyncClient(base_url=url, timeout=30.0)
    except Exception:
        pass

    print("Сервер не поднят на 8000, прогоняем через ASGITransport...")
    from app.main import app
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver/api/v1",
        timeout=30.0,
    )


async def main():
    global ok_count, err_count
    client = await get_client()

    try:
        step("Проверка входа и управления ролями")

        res = await client.post("/auth/login", json={"email": "admin@build.ru", "password": "admin12345"})
        check("Логин под админом", res.status_code == 200, res.text)
        admin_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

        res = await client.post("/auth/login", json={"email": "engineer@build.ru", "password": "engineer123"})
        check("Логин под инженером", res.status_code == 200, res.text)
        eng_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        engineer_id = res.json()["user"]["id"]

        res = await client.post("/auth/login", json={"email": "foreman@build.ru", "password": "foreman123"})
        check("Логин под прорабом", res.status_code == 200, res.text)
        foreman_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
        foreman_id = res.json()["user"]["id"]

        test_email = f"user_{uuid.uuid4().hex[:6]}@build.ru"
        res = await client.post("/auth/register", json={
            "email": test_email,
            "password": "Password123!",
            "first_name": "Тест",
            "last_name": "Тестов"
        })
        check("Регистрация нового пользователя", res.status_code == 201, res.text)

        res = await client.patch(
            "/auth/users/roles",
            headers=admin_headers,
            json={"email": test_email, "roles": ["engineer"]}
        )
        check("Выдача роли инженера через админку", res.status_code == 200 and "engineer" in res.json().get("roles", []))

        step("Создание ОКС и разграничение прав")

        res = await client.get("/dictionaries/project-types", headers=admin_headers)
        school_type = next((t for t in res.json() if t["code"] == "school"), None)
        check("Получение типа проекта (school)", school_type is not None)
        type_id = school_type["id"]

        res = await client.post(
            "/projects",
            headers=foreman_headers,
            json={"name": "Тест", "address": "ул. Тестовая", "type_id": type_id}
        )
        check("Прорабу запрещено создавать проект (403)", res.status_code == 403)

        project_name = f"Школа №{uuid.uuid4().hex[:4].upper()}"
        res = await client.post(
            "/projects",
            headers=admin_headers,
            json={"name": project_name, "address": "г. Москва, ул. Ленина, 10", "type_id": type_id}
        )
        check("Создание ОКС админом", res.status_code == 201, res.text)
        p_data = res.json()
        project_id = p_data["id"]

        check(
            "Дефолтные статусы верны (DRAFT, GREEN, NONE)",
            p_data["status"] == "DRAFT" and
            p_data["current_alert_level"] == "GREEN" and
            p_data["current_special_status"] == "NONE"
        )

        res = await client.post(
            f"/projects/{project_id}/assignments",
            headers=admin_headers,
            json={"user_id": foreman_id, "role_in_project": "foreman"}
        )
        check("Привязка прораба к объекту", res.status_code == 201)

        res = await client.post(
            f"/projects/{project_id}/assignments",
            headers=admin_headers,
            json={"user_id": engineer_id, "role_in_project": "engineer"}
        )
        check("Привязка инженера к объекту", res.status_code == 201)

        step("Формирование графика и работа с Гантом")

        start_date = datetime.now(timezone.utc) - timedelta(days=5)
        res = await client.post(
            f"/projects/{project_id}/schedules/apply-template",
            headers=foreman_headers,
            json={"start_date": start_date.isoformat()}
        )
        check("Применение базового шаблона этапов", res.status_code == 200, res.text)

        res = await client.get(f"/projects/{project_id}/schedules", headers=foreman_headers)
        stages = res.json()
        check("Этапы и техника сформированы", len(stages) >= 3 and len(stages[0]["equipment_requirements"]) > 0)

        first_stage = stages[0]
        first_stage_id = first_stage["id"]

        res = await client.put(
            f"/projects/{project_id}/schedules/bulk-sync",
            headers=foreman_headers,
            json={
                "stages": [
                    {
                        "id": first_stage_id,
                        "stage_name": first_stage["stage_name"],
                        "substage_name": first_stage["substage_name"] + " (корректировка)",
                        "sequence_order": 1,
                        "base_start_date": first_stage["base_start_date"],
                        "base_end_date": first_stage["base_end_date"],
                        "equipment_requirements": [
                            {"equipment_type": "excavator", "required_count": 3},
                            {"equipment_type": "dump_truck", "required_count": 2}
                        ]
                    }
                ]
            }
        )
        check("Ручная корректировка этапа прорабом (bulk-sync)", res.status_code == 200)

        res = await client.post(f"/projects/{project_id}/schedules/confirm", headers=foreman_headers)
        check("Утверждение графика (ACTIVE)", res.status_code == 200)

        res = await client.put(
            f"/projects/{project_id}/schedules/bulk-sync",
            headers=foreman_headers,
            json={"stages": []}
        )
        check("Блокировка правок графика после старта (400)", res.status_code == 400)

        res = await client.post(
            f"/projects/{project_id}/schedules/{first_stage_id}/start",
            headers=foreman_headers
        )
        check("Ручной старт этапа прорабом", res.status_code == 200 and res.json()["status"] == "IN_PROGRESS")

        step("Камеры, снимки и аналитика")

        res = await client.post(
            f"/projects/{project_id}/cameras",
            headers=foreman_headers,
            json={"stream_url": "rtsp://cam.stream.local/live1"}
        )
        check("Добавление камеры", res.status_code == 201)
        camera_id = res.json()["id"]

        fake_photo = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
        res = await client.post(
            f"/cameras/{camera_id}/frames/upload",
            headers=eng_headers,
            files={"file": ("snap.jpg", fake_photo, "image/jpeg")}
        )
        check("Загрузка кадра на сервер", res.status_code == 201)
        image_path = res.json()["image_path"]

        res = await client.post(
            f"/cameras/{camera_id}/frames",
            headers=admin_headers,
            json={
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "image_path": image_path,
                "detection_result": {
                    "classes": ["excavator", "dump_truck"],
                    "boxes": [[10, 20, 100, 150]]
                }
            }
        )
        check("Запись результатов детекции", res.status_code == 201)
        frame_id = res.json()["id"]

        res = await client.patch(
            f"/frames/{frame_id}/evidence",
            headers=eng_headers,
            json={"is_saved_for_report": True}
        )
        check("Инженер сохранил кадр для отчета", res.status_code == 200)

        now = datetime.now(timezone.utc)
        res = await client.post(
            "/monitoring/interval-analytics",
            headers=admin_headers,
            json={
                "project_id": project_id,
                "schedule_id": first_stage_id,
                "camera_id": camera_id,
                "interval_start": (now - timedelta(minutes=30)).isoformat(),
                "interval_end": now.isoformat(),
                "compliance_status": "WARNING",
                "active_equipment_count": 1,
                "idle_equipment_count": 2,
                "required_equipment_count": 5,
                "equipment_summary": {
                    "detected_active": [{"type": "excavator", "count": 1}],
                    "detected_idle": [{"type": "excavator", "count": 2}]
                },
                "notes": "Простой двух единиц техники"
            }
        )
        check("Сохранение интервальной аналитики", res.status_code == 201)

        step("Алерты и автоматическая эскалация")

        res = await client.post(
            "/alerts/trigger",
            headers=admin_headers,
            json={
                "project_id": project_id,
                "schedule_id": first_stage_id,
                "severity": "YELLOW",
                "trigger_type": "EQUIPMENT_IDLE",
                "trigger_frame_id": frame_id,
                "escalation_hours": 48
            }
        )
        check("Создание желтого алерта", res.status_code == 200)
        yellow_alert_id = res.json()["id"]

        res = await client.get(f"/projects/{project_id}", headers=eng_headers)
        check("Светофор перешел в YELLOW", res.json()["current_alert_level"] == "YELLOW")

        res = await client.post(
            "/alerts/trigger",
            headers=admin_headers,
            json={
                "project_id": project_id,
                "schedule_id": first_stage_id,
                "severity": "YELLOW",
                "trigger_type": "CRANE_DEFICIT",
                "escalation_hours": -1
            }
        )
        expired_id = res.json()["id"]

        res = await client.post("/alerts/check-escalations", headers=admin_headers)
        check("Запуск эскалации просроченных алертов", res.status_code == 200)
        check("Просроченный алерт стал RED", expired_id in res.json().get("escalated_alert_ids", []))

        res = await client.get(f"/projects/{project_id}", headers=eng_headers)
        check("Светофор объекта стал RED", res.json()["current_alert_level"] == "RED")

        step("Сценарий 1: Ложная тревога и возврат в зеленую зону")

        res = await client.post(
            f"/alerts/{expired_id}/resolve",
            headers=eng_headers,
            json={
                "action_taken": "FALSE_ALARM",
                "engineer_comment": "Техника на месте, была перекрыта опорой."
            }
        )
        check("Инженер отметил ложную тревогу (FALSE_ALARM)", res.status_code == 200)

        await client.post(
            f"/alerts/{yellow_alert_id}/resolve",
            headers=eng_headers,
            json={"action_taken": "FALSE_ALARM", "engineer_comment": "Простой прекращен"}
        )
        res = await client.get(f"/projects/{project_id}", headers=eng_headers)
        check("Светофор вернулся в GREEN", res.json()["current_alert_level"] == "GREEN")

        step("Сценарий 2: Фиолетовый статус и каскадный сдвиг сроков")

        res = await client.post(
            "/alerts/trigger",
            headers=admin_headers,
            json={
                "project_id": project_id,
                "schedule_id": first_stage_id,
                "severity": "RED",
                "trigger_type": "CONCRETE_MIXER_ABSENT"
            }
        )
        red_mixer_id = res.json()["id"]

        purple_deadline = datetime.now(timezone.utc) + timedelta(days=3)
        res = await client.post(
            f"/alerts/{red_mixer_id}/resolve",
            headers=eng_headers,
            json={
                "action_taken": "PURPLE_STATUS",
                "engineer_comment": "Миксер застрял на МКАДе. Готовим допсоглашение.",
                "target_deadline": purple_deadline.isoformat(),
                "evidence_frame_ids": [frame_id]
            }
        )
        check("Перевод в фиолетовый статус (PURPLE_STATUS)", res.status_code == 200)

        res = await client.get(f"/projects/{project_id}", headers=eng_headers)
        check(
            "Статус проекта PURPLE, алерт заглушен в GREEN",
            res.json()["current_special_status"] == "PURPLE" and
            res.json()["current_alert_level"] == "GREEN"
        )

        res = await client.post(
            f"/projects/{project_id}/schedules/cascade-shift",
            headers=eng_headers,
            json={
                "from_schedule_id": first_stage_id,
                "shift_days": 4,
                "target_timeline": "BASE",
                "reason_comment": "Сдвиг сроков из-за срыва поставки бетона",
                "document_reference": "Доп. соглашение №12",
                "close_special_status": True
            }
        )
        check("Каскадный сдвиг сроков цепочки этапов (+4 дня)", res.status_code == 200, res.text)
        check("Сдвинуто не менее 2 последующих этапов", res.json()["shifted_stages_count"] >= 2)

        res = await client.get(f"/projects/{project_id}", headers=eng_headers)
        check("Фиолетовый статус автоматически снят после сдвига", res.json()["current_special_status"] == "NONE")

        step("Сценарий 3: Оранжевый статус и штрафной отчет")

        res = await client.post(
            "/alerts/trigger",
            headers=admin_headers,
            json={
                "project_id": project_id,
                "schedule_id": first_stage_id,
                "severity": "RED",
                "trigger_type": "EXCAVATOR_BROKEN"
            }
        )
        red_broken_id = res.json()["id"]

        orange_deadline = datetime.now(timezone.utc) + timedelta(days=2)
        res = await client.post(
            f"/alerts/{red_broken_id}/resolve",
            headers=eng_headers,
            json={
                "action_taken": "ORANGE_STATUS",
                "engineer_comment": "Поломка по вине бригады. Сроки не двигаем, даем 48ч на нагон.",
                "target_deadline": orange_deadline.isoformat()
            }
        )
        check("Перевод в оранжевый статус (ORANGE_STATUS)", res.status_code == 200)

        res = await client.get(f"/special-statuses/projects/{project_id}/current", headers=eng_headers)
        check("Окно оранжевого статуса активно", res.status_code == 200 and res.json() is not None)
        window_id = res.json()["id"]

        res = await client.post(
            f"/special-statuses/windows/{window_id}/close",
            headers=eng_headers,
            json={"close_comment": "Время на нагон истекло, составляем отчет."}
        )
        check("Закрытие окна спецстатуса", res.status_code == 200)

        res = await client.post(
            f"/special-statuses/windows/{window_id}/orange-report",
            headers=eng_headers,
            json={
                "is_plan_caught_up": False,
                "time_lost_hours": 14.5,
                "responsible_party": "ООO Механизация",
                "summary_meta": {"idle_count": 1, "fine_rub": 100000}
            }
        )
        check("Сохранение штрафного отчета с потерянными часами", res.status_code == 200, res.text)

        res = await client.get(f"/special-statuses/projects/{project_id}/orange-reports", headers=eng_headers)
        check("Отчет виден в реестре объекта", len(res.json()) >= 1)

        step("Досрочное завершение этапа и сводная аналитика")

        res = await client.post(
            f"/projects/{project_id}/schedules/{first_stage_id}/complete-early",
            headers=foreman_headers,
            json={
                "actual_end_date": datetime.now(timezone.utc).isoformat(),
                "foreman_comment": "Закончили раньше срока"
            }
        )
        check("Прораб закрыл этап досрочно (COMPLETED)", res.status_code == 200 and res.json()["status"] == "COMPLETED")

        res = await client.get(f"/projects/{project_id}/live-summary", headers=foreman_headers)
        check("Получение сводки Live Summary", res.status_code == 200)
        check("Готовность объекта больше 0%", res.json().get("physical_progress_percent", 0) > 0)

        res = await client.get("/analytics/department-overview", headers=admin_headers)
        check("Дашборд департамента возвращает данные", res.status_code == 200)
        check("Потерянные часы учтены в общей статистике", res.json().get("total_idle_hours", 0) >= 14.5)

        res = await client.get(f"/projects/{project_id}/audit-trail", headers=admin_headers)
        check("Аудит зафиксировал действия по проекту", res.status_code == 200 and len(res.json()) >= 4)

    except Exception:
        print(f"\n{RED}Тесты прерваны из-за ошибки:{RESET}")
        traceback.print_exc()
        err_count += 1
    finally:
        await client.aclose()

    print("\n" + "-" * 40)
    if err_count == 0:
        print(f"{GREEN}{BOLD}Все проверки пройдены ({ok_count} из {ok_count}){RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}Есть ошибки: упало {err_count}, успешно {ok_count}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())