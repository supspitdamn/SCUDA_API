import fastapi
import api.schemas as schemas
from fastapi import FastAPI, HTTPException, Depends
from api.database import db_init, get_db, lifespan, DB_CONFIG, db_clear
import psycopg2

DEVICE_ID = "esp32_34CDB033BBD8"

app = FastAPI(debug=True, title = "СКУД API система", lifespan=lifespan)

# Часть админа
@app.post("/admin/add-employee", tags=["Admin"], response_model=schemas.Employee)
def add_employee(emp: schemas.EmployeeCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            # 1. Сначала находим ID роли по её названию
            crs.execute("SELECT id FROM roles WHERE role_name = %s", (emp.role_name,))
            role_row = crs.fetchone()
            
            if not role_row:
                raise HTTPException(status_code=404, detail=f"Роль '{emp.role_name}' не найдена")
            
            role_id = role_row[0]

            # 2. Вставляем сотрудника
            query = """
                    INSERT INTO employees (card_id, full_name, department, role_id, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, card_id, full_name, department, role_id, is_active
                    """
            
            crs.execute(query, (
                emp.card_id,
                emp.full_name,
                emp.department,
                role_id, 
                1 if emp.is_active else 0
            ))
            
            row = crs.fetchone()
            db.commit()

            if row:
                return {
                    "id": row[0],
                    "card_id": row[1],
                    "full_name": row[2],
                    "department": row[3],
                    "is_active": bool(row[5]),
                    "role_name": emp.role_name
                }
            
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Сотрудник с таким card_id уже существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")

@app.post("/admin/add-room", tags = ["Admin"], response_model=schemas.Room)
def add_room(emp: schemas.RoomCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO rooms (
                    room_number,
                    description
                    )
                    VALUES (
                    %s, %s
                    )
                    RETURNING *
                    """
            
            crs.execute(queue, (
                         emp.room_number,
                         emp.description
                         ))
            
            response = crs.fetchone()
            db.commit()
            return {
                "id": response[0],
                "room_number": response[1],
                "description": response[2]
            }
    except HTTPException as http_ex:
        raise http_ex
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code = 400, detail = "Такая комната существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = str(e))

@app.post("/admin/add-access-point", tags = ["Admin"], response_model = schemas.AccessPoint)
def add_access_point(ap: schemas.AccessPointCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO access_points (
                    room_id,
                    entrance_name,
                    device_mac,
                    direction
                    )
                    VALUES (
                    %s, %s, %s, %s
                    )
                    RETURNING *
                    """
            
            crs.execute(queue, (
                ap.room_id,
                ap.entrance_name,
                ap.device_mac.upper(),
                ap.direction.value
            ))

            response = crs.fetchone()

            db.commit()

            return {
                "id": response[0],
                "room_id": response[1],
                "entrance_name": response[2],
                "device_mac": response[3],
                "direction": response[4],
                "whitelist_version": response[5]
            }
        
    except HTTPException as http_ex:
        raise http_ex
        
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail = "Указанная комната не существует")
    
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail = "Такой вход уже существует")
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = str(e))

@app.post("/admin/add-role", tags=["Admin"], response_model=schemas.Role)
def add_role(role: schemas.RoleCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            queue = """
                INSERT INTO roles (role_name) 
                VALUES (%s) 
                RETURNING id, role_name
            """
            crs.execute(queue, (role.role_name,))
            response = crs.fetchone()
            db.commit()
            return {
                "id": response[0], 
                "role_name": response[1]
            }
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Такая роль уже существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/add-access-group", tags = ["Admin"], response_model=schemas.AccessGroup)
def add_access_group(ag: schemas.AccessGroupCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO access_groups (
                    group_name
                    )
                    VALUES (%s)
                    RETURNING id, group_name
                    """
            
            crs.execute(queue, (ag.group_name,))

            response = crs.fetchone()

            db.commit()

            print(f"Группе {response[1]} успешно создана с id {response[0]}")

            return {"id" : response[0], "group_name" : response[1]}
        
    except HTTPException as htex:
        raise htex
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Группа с таким названием уже существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail=f"Ошибка добавления группы доступа. Детали: {str(e)}")

@app.post("/admin/assign-group-to-employee", tags=["Admin"], response_model=schemas.EmployeeAccessGroup)
def assign_group_to_employee(agte: schemas.EmployeeAccessGroupCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("SELECT id FROM employees WHERE card_id = %s", (agte.card_id,))
            employee_row = crs.fetchone()

            crs.execute("SELECT id FROM access_groups WHERE group_name = %s", (agte.group_name,))
            group_row = crs.fetchone()
            
            if not employee_row:
                raise HTTPException(status_code=404, detail=f"Сотрудник с картой {agte.card_id} не найден")
            
            if not group_row:
                raise HTTPException(status_code=404, detail=f"Группа {agte.group_name} не найдена")
            
            emp_id = employee_row[0]
            grp_id = group_row[0]

            query = """
                    INSERT INTO employee_access_group (employee_id, group_id)
                    VALUES (%s, %s)
                    RETURNING id
                    """
            
            crs.execute(query, (emp_id, grp_id))
            res_id = crs.fetchone()[0]

            update_version_query = """
                UPDATE access_points 
                SET whitelist_version = whitelist_version + 1 
                WHERE room_id IN (
                    SELECT room_id FROM group_rooms WHERE group_id = %s
                )
            """
            crs.execute(update_version_query, (grp_id,))
            
            db.commit()

            return {
                "id": res_id,
                "card_id": agte.card_id,
                "group_name": agte.group_name
            }

    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Пользователь уже находится в этой группе")
    except HTTPException as htex:
        raise htex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")

@app.post("/admin/assign-room-to-group", tags=["Admin"], response_model=schemas.RoomGroup)
def assign_room_to_group(data: schemas.RoomGroupCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            # Находим ID группы по имени
            crs.execute("SELECT id FROM access_groups WHERE group_name = %s", (data.group_name,))
            group_row = crs.fetchone()
            
            if not group_row:
                raise HTTPException(status_code=404, detail=f"Группа '{data.group_name}' не найдена")
            
            group_id = group_row[0]

            # Привязываем комнату к группе
            query = """
                    INSERT INTO group_rooms (group_id, room_id)
                    VALUES (%s, %s)
                    RETURNING id
                    """
            crs.execute(query, (group_id, data.room_id))
            res_id = crs.fetchone()[0]

            update_version_query = """
                UPDATE access_points 
                SET whitelist_version = whitelist_version + 1 
                WHERE room_id = %s
            """
            crs.execute(update_version_query, (data.room_id,))
            
            db.commit()

            return {
                "id": res_id, 
                "group_name": data.group_name, 
                "room_id": data.room_id
            }

    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Эта комната уже добавлена в данную группу")
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(status_code=404, detail="Указанная комната не существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")
    
# Методы удаления/измения статусов

@app.delete("/admin/remove-employee-from-access-group", tags=["Admin"], response_model=schemas.StatusResponse)
def remove_employee_from_access_group(card_id: str, group_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            query = """
                SELECT eag.id, e.full_name, eag.group_id 
                FROM employee_access_group eag
                JOIN employees e ON eag.employee_id = e.id
                JOIN access_groups ag ON eag.group_id = ag.id
                WHERE e.card_id = %s AND ag.group_name = %s
            """
            crs.execute(query, (card_id, group_name))
            res = crs.fetchone()

            if not res:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Связь не найдена или сотрудник с картой {card_id} не состоит в группе {group_name}"
                )

            record_id, full_name, group_id = res

            crs.execute("DELETE FROM employee_access_group WHERE id = %s", (record_id,))

            update_version_query = """
                UPDATE access_points 
                SET whitelist_version = whitelist_version + 1 
                WHERE room_id IN (
                    SELECT room_id FROM group_rooms WHERE group_id = %s
                )
            """
            crs.execute(update_version_query, (group_id,))

            db.commit()

            return {
                "status": "ОК",
                "message": f"Сотрудник {full_name} успешно удален из группы {group_name}. Вайтлисты МК обновлены."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/remove-room-from-access-group/{group_name}/{room_number}", tags=["Admin"], response_model=schemas.StatusResponse)
def remove_room_from_access_group(group_name: str, room_number: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("SELECT id FROM rooms WHERE room_number = %s", (room_number,))
            room_row = crs.fetchone()
            
            if not room_row:
                raise HTTPException(status_code=404, detail=f"Комната №{room_number} не найдена")
                
            room_id = room_row[0]

            query = """
                DELETE FROM group_rooms 
                WHERE group_id = (SELECT id FROM access_groups WHERE group_name = %s)
                  AND room_id = %s
            """
            crs.execute(query, (group_name, room_id))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Связь не найдена. Проверьте название группы и номер комнаты.")
            
            update_version_query = """
                UPDATE access_points 
                SET whitelist_version = whitelist_version + 1 
                WHERE room_id = %s
            """
            crs.execute(update_version_query, (room_id,))
            
            db.commit()
            return {
                "status": "ОК", 
                "message": f"Комната №{room_number} исключена из группы '{group_name}'"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@app.delete("/admin/remove-access-group/{group_name}", tags=["Admin"], response_model=schemas.StatusResponse)
def remove_access_group(group_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT DISTINCT gr.room_id 
                FROM group_rooms gr
                JOIN access_groups ag ON gr.group_id = ag.id
                WHERE ag.group_name = %s
            """, (group_name,))
            rooms = [row[0] for row in crs.fetchall()]

            crs.execute("DELETE FROM access_groups WHERE group_name = %s", (group_name,))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Группа '{group_name}' не найдена")
            
            if rooms:
                crs.execute("""
                    UPDATE access_points 
                    SET whitelist_version = whitelist_version + 1 
                    WHERE room_id = ANY(%s)
                """, (rooms,))
            
            db.commit()
            return {
                "status": "ОК", 
                "message": f"Группа '{group_name}' и все её привязки успешно удалены"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/remove-employee/{card_id}", tags=["Admin"], response_model=schemas.StatusResponse)
def delete_employee(card_id: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT DISTINCT gr.room_id 
                FROM group_rooms gr
                JOIN employee_access_group eag ON gr.group_id = eag.group_id
                JOIN employees e ON eag.employee_id = e.id
                WHERE e.card_id = %s
            """, (card_id,))
            rooms = [row[0] for row in crs.fetchall()]

            crs.execute("DELETE FROM employees WHERE card_id = %s", (card_id,))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник с такой картой не найден")
            
            if rooms:
                crs.execute("""
                    UPDATE access_points 
                    SET whitelist_version = whitelist_version + 1 
                    WHERE room_id = ANY(%s)
                """, (rooms,))
            
            db.commit()
            return {"status": "ОК", "message": f"Сотрудник с картой {card_id} успешно удален"}
        
    except HTTPException:
        raise
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить: по этой карте есть записи в логах доступа. Сначала очистите логи или деактивируйте карту."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/admin/employee-change-card-status/{card_id}", tags=["Admin"], response_model=schemas.StatusResponse)
def change_employee_card_status(card_id: str, restrict: bool, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT DISTINCT gr.room_id 
                FROM group_rooms gr
                JOIN employee_access_group eag ON gr.group_id = eag.group_id
                JOIN employees e ON eag.employee_id = e.id
                WHERE e.card_id = %s
            """, (card_id,))
            rooms = [row for row in crs.fetchall()]

            new_status = 0 if restrict else 1
            
            crs.execute(
                "UPDATE employees SET is_active = %s WHERE card_id = %s",
                (new_status, card_id)
            )

            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник с такой картой не найден")

            if rooms:
                crs.execute("""
                    UPDATE access_points 
                    SET whitelist_version = whitelist_version + 1 
                    WHERE room_id = ANY(%s)
                """, (rooms,))

            db.commit()
            
            status_text = "ЗАБЛОКИРОВАН" if restrict else "АКТИВИРОВАН"
            return {
                "status": "ОК", 
                "message": f"Доступ по карте {card_id} теперь {status_text}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@app.patch("/admin/change-employee-role/{card_id}", tags=["Admin"], response_model=schemas.StatusResponse)
def change_employee_role(card_id: str, new_role_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT DISTINCT gr.room_id 
                FROM group_rooms gr
                JOIN employee_access_group eag ON gr.group_id = eag.group_id
                JOIN employees e ON eag.employee_id = e.id
                WHERE e.card_id = %s
            """, (card_id,))
            rooms = [row for row in crs.fetchall()]

            query = """
                UPDATE employees 
                SET role_id = (SELECT id FROM roles WHERE role_name = %s)
                WHERE card_id = %s
                RETURNING id
            """
            crs.execute(query, (new_role_name, card_id))
            res = crs.fetchone()

            if not res:
                crs.execute("SELECT id FROM roles WHERE role_name = %s", (new_role_name,))
                if not crs.fetchone():
                    raise HTTPException(status_code=404, detail=f"Роль '{new_role_name}' не найдена")
                
                raise HTTPException(status_code=404, detail=f"Сотрудник с картой {card_id} не найден")

            if rooms:
                crs.execute("""
                    UPDATE access_points 
                    SET whitelist_version = whitelist_version + 1 
                    WHERE room_id = ANY(%s)
                """, (rooms,))

            db.commit()
            return {
                "status": "ОК", 
                "message": f"Сотруднику с картой {card_id} успешно назначена роль '{new_role_name}'"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@app.delete("/admin/remove-room/{room_number}", tags=["Admin"], response_model=schemas.StatusResponse)
def remove_room(room_number: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("SELECT id FROM rooms WHERE room_number = %s", (room_number,))
            room_row = crs.fetchone()

            if not room_row:
                raise HTTPException(status_code=404, detail=f"Комната №{room_number} не найдена")

            room_id = room_row[0]

            crs.execute("SELECT device_mac FROM access_points WHERE room_id = %s", (room_id,))
            devices = [row[0] for row in crs.fetchall()]

            crs.execute("DELETE FROM rooms WHERE id = %s", (room_id,))

            db.commit()

            if devices:
                from mqtt_worker import mqtt_client
                import json
                for mac in devices:
                    empty_payload = {
                        "request_id": f"room-delete-sync-{room_id}",
                        "version": 0,
                        "cards": []
                    }
                    mqtt_client.publish(f"skud/{mac}/cmd/sync_cards", json.dumps(empty_payload))

            return {"status": "ОК", "message": f"Комната №{room_number} успешно удалена из системы. Связанные МК очищены."}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")

@app.delete("/admin/remove-access-point/{room_number}/{entrance_name}", tags=["Admin"], response_model=schemas.StatusResponse)
def delete_access_point(room_number: int, entrance_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT device_mac 
                FROM access_points 
                WHERE entrance_name = %s 
                  AND room_id = (SELECT id FROM rooms WHERE room_number = %s)
            """, (entrance_name, room_number))
            row = crs.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, 
                    detail=f"В комнате №{room_number} не найдена точка доступа '{entrance_name}'"
                )
            
            device_mac = row[0]

            query = """
                DELETE FROM access_points 
                WHERE entrance_name = %s 
                  AND room_id = (SELECT id FROM rooms WHERE room_number = %s)
            """
            crs.execute(query, (entrance_name, room_number))
            
            db.commit()

            try:
                from mqtt_worker import mqtt_client
                import json
                empty_payload = {
                    "request_id": f"ap-delete-sync-{device_mac}",
                    "version": 0,
                    "cards": []
                }
                mqtt_client.publish(f"skud/{device_mac}/cmd/sync_cards", json.dumps(empty_payload))
            except Exception:
                pass

            return {
                "status": "ОК", 
                "message": f"Точка доступа '{entrance_name}' комнаты №{room_number} успешно удалена. МК очищен."
            }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/clear-database", tags=["Admin"])
def clear_database(db = Depends(get_db)):
    try:
        
        db_clear(conn=db)
        print("База данных очищена")
        
        db_init(conn=db)
        print("База данных реинициализирована")
        
        return {"status": "ОК", "message": "База данных полностью сброшена и реинициализирована"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# просмотр информации

@app.get("/admin/view-logs", tags=["Admin"], response_model=schemas.ViewLogsResponse)
def view_logs(db = Depends(get_db), limit: int = 10, offset: int = 0):
    try:
        with db.cursor() as crs:
            crs.execute("""
                SELECT
                    l.id,
                    COALESCE(e.full_name, 'Неизвестно'),
                    COALESCE(r.room_number, 0),
                    COALESCE(ap.entrance_name, 'Удаленная точка прохода'),
                    l.event_time,
                    l.is_granted
                FROM access_logs AS l
                LEFT JOIN employees AS e ON l.employee_id = e.id 
                LEFT JOIN access_points AS ap ON l.access_point_id = ap.id
                LEFT JOIN rooms AS r ON ap.room_id = r.id
                ORDER BY l.event_time DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))

            response = crs.fetchall()

            logs = []
            for row in response:
                logs.append({
                    "id": row[0],
                    "employee_name": row[1],
                    "room_number": row[2],
                    "entrance": row[3],
                    "time": row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else "Нет данных",
                    "is_granted": bool(row[5])
                })

            return {
                "status": "success",
                "data": logs
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/view-employees", tags=["Admin"], response_model=list[schemas.Employee])
def view_employees(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            queue = """
                    SELECT 
                        e.id,
                        e.card_id,
                        e.full_name, 
                        e.department,
                        e.is_active,
                        r.role_name
                    FROM employees AS e
                    JOIN roles AS r ON e.role_id = r.id
                    ORDER BY e.full_name
                    LIMIT %s
                    OFFSET %s
                    """
            crs.execute(queue, (limit, offset))
            rows = crs.fetchall()

        return [
            {
                "id": r[0],
                "card_id": r[1],
                "full_name": r[2],
                "department": r[3],
                "is_active": bool(r[4]),
                "role_name": r[5]
            } for r in rows
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/view-rooms", tags=["Admin"], response_model=list[schemas.Room])
def view_rooms(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            queue = """
                    SELECT
                        r.id,
                        r.room_number,
                        r.description
                    FROM rooms AS r
                    ORDER BY r.room_number
                    LIMIT %s OFFSET %s
                    """
            crs.execute(queue, (limit, offset))
            rows = crs.fetchall()

        return [
            {
                "id": r[0], 
                "room_number": r[1], 
                "description": r[2]
            } for r in rows
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/view-roles", tags=["Admin"], response_model=list[schemas.Role])
def view_roles(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            queue = """
                    SELECT
                        id,
                        role_name
                    FROM
                        roles
                    LIMIT %s
                    OFFSET %s
                    """
            crs.execute(queue, (limit, offset))
            rows = crs.fetchall()

        return [
            {
                "id": r[0], 
                "role_name": r[1]
            } for r in rows
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/employee-info/{card_id}", tags=["Admin"], response_model=None)
def get_employee_info(card_id: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute("""
                SELECT e.id, e.full_name, e.department, r.role_name, e.is_active
                FROM employees e
                JOIN roles r ON e.role_id = r.id
                WHERE e.card_id = %s
            """, (card_id,))

            base = crs.fetchone()
            if not base:
                raise HTTPException(status_code=404, detail="Сотрудник с такой картой не найден")
            
            internal_id = base[0]

            crs.execute("""
                SELECT ag.group_name 
                FROM access_groups ag
                JOIN employee_access_group eag ON ag.id = eag.group_id
                WHERE eag.employee_id = %s
            """, (internal_id,))

            groups = [row[0] for row in crs.fetchall()]

            crs.execute("""
                SELECT DISTINCT r.room_number, r.description
                FROM rooms r
                JOIN group_rooms gr ON r.id = gr.room_id
                JOIN employee_access_group eag ON gr.group_id = eag.group_id
                WHERE eag.employee_id = %s
                ORDER BY r.room_number
            """, (internal_id,))

            rooms = [{"room_number": row[0], "description": row[1]} for row in crs.fetchall()]

            return {
                "id": internal_id,
                "card_id": card_id,
                "full_name": base[1],
                "department": base[2],
                "role_name": base[3],
                "is_active": bool(base[4]),
                "assigned_groups": groups,
                "accessible_rooms": rooms
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


