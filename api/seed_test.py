import psycopg2
from api.database import DB_CONFIG
from api.scuda import DEVICE_ID

DEVICE_ID = DEVICE_ID.strip().upper()


def run_seed():
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as crs:
        try:
            print("Очистка старых тестовых данных...")
            crs.execute(
                "TRUNCATE employee_access_group, group_rooms, access_points, employees, rooms, access_groups, roles RESTART IDENTITY CASCADE;"
            )

            print("Наполнение тестовыми данными...")
            crs.execute(
                "INSERT INTO roles (role_name, access_level) VALUES ('Инженер', 10) RETURNING id"
            )
            role_id = crs.fetchone()[0]

            crs.execute(
                "INSERT INTO rooms (room_number, description, entry_level) VALUES (101, 'Серверная', 5) RETURNING id"
            )
            room_id = crs.fetchone()[0]

            crs.execute(
                "INSERT INTO access_groups (group_name) VALUES ('Администраторы ИТ') RETURNING id"
            )
            group_id = crs.fetchone()[0]

            crs.execute(
                """
                INSERT INTO access_points (room_id, entrance_name, device_mac, direction, whitelist_version) 
                VALUES (%s, 'Главная дверь серверной', %s, 'BOTH', 0)
            """,
                (room_id, DEVICE_ID),
            )

            crs.execute(
                """
                INSERT INTO employees (card_id, full_name, department, role_id, is_active) 
                VALUES ('75D37506', 'Тестовый Сотрудник', 'IT', %s, 1) RETURNING id
            """,
                (role_id,),
            )
            employee_id = crs.fetchone()[0]

            crs.execute(
                "INSERT INTO employee_access_group (employee_id, group_id) VALUES (%s, %s)",
                (employee_id, group_id),
            )
            crs.execute(
                "INSERT INTO group_rooms (group_id, room_id) VALUES (%s, %s)",
                (group_id, room_id),
            )

            conn.commit()
            print("Тестовые данные успешно загружены! Связи Many-to-Many созданы.")

            queue = """
                SELECT DISTINCT e.card_id
                FROM employees AS e
                JOIN employee_access_group eag ON e.id = eag.employee_id
                JOIN access_groups ag ON eag.group_id = ag.id
                JOIN group_rooms gr ON ag.id = gr.group_id
                JOIN access_points ap ON gr.room_id = ap.room_id
                WHERE ap.device_mac = %s AND e.is_active = 1
            """
            crs.execute(queue, (DEVICE_ID,))
            check_cards = [row[0] for row in crs.fetchall()]
            print(
                f"Проверка связи воркера: для {DEVICE_ID} найдено карт в БД -> {check_cards}"
            )

        except Exception as e:
            conn.rollback()
            print(f"Ошибка сиддера: {e}")
        finally:
            conn.close()


if __name__ == "__main__":
    run_seed()
