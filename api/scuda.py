import fastapi
import api.schemas as schemas
import api.database as database
from fastapi import FastAPI, HTTPException, Depends
from api.database import db_init, get_db, lifespan
import psycopg2
from contextlib import asynccontextmanager

app = FastAPI(debug=True, title = "СКУД API система", lifespan=lifespan)

# Сервисная часть

@app.post("/service/receive-from-mk", tags=["Service"], response_model=schemas.StatusResponse)
async def receive_from_mk(log: schemas.FromMKtoServerAccessLog, db = Depends(get_db)):
    with db.cursor() as crs:
        try:
            
            crs.execute("SELECT id FROM employees WHERE card_id = %s", (log.card_id,))
            res = crs.fetchone()
            emp_id = res[0] if res else None

            crs.execute("SELECT id FROM access_points WHERE entrance_name = %s", (log.device,))
            ap_res = crs.fetchone()
            
            if not ap_res:
                raise HTTPException(status_code=400, detail=f"Устройство {log.device} не зарегистрировано")
            
            ap_id = ap_res[0]

            queue = """
                INSERT INTO access_logs (employee_id, card_id_text, access_point_id, event_time, is_granted)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            crs.execute(queue, (
                emp_id,           # Будет ID или NULL, если карта чужая
                log.card_id,      # Текстовый номер карты запишется ВСЕГДА
                ap_id, 
                log.ts, 
                1 if log.access == "granted" else 0
            ))

            db.commit()
            return {"status": "ОК", "message": "Лог записан"}
        
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")

        
@app.get("/service/get-whitelist-for-mk/{device_name}", tags = ["Service"], response_model=schemas.WhiteListResponse)
async def get_whitelist_for_mk(device_name: str, db = Depends(get_db)):
    with db.cursor() as crs:

        try:

            queue = """
                    SELECT DISTINCT e.card_id
                    FROM employees AS e
                    JOIN employee_access_group eag ON e.id = eag.employee_id
                    JOIN group_rooms gr ON eag.group_id = gr.group_id
                    JOIN access_points ap ON gr.room_id = ap.room_id
                    WHERE ap.entrance_name = %s AND e.is_active = 1
                    """
            
            crs.execute(queue, (device_name,))

            rows = crs.fetchall()

            card_list = [row[0] for row in rows]

            if not card_list:

                crs.execute("SELECT id FROM access_points WHERE entrance_name = %s", (device_name,))

                if not crs.fetchone():
              
                    raise HTTPException(status_code=404, detail="Устройство не найдено")
            return {
                "status": "success",
                "device": device_name,
                "cards": card_list
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")

# Часть админа
# добавление нового

@app.post("/admin/add-employee", tags=["Admin"], response_model=schemas.Employee)
async def add_employee(emp: schemas.EmployeeCreate, db = Depends(get_db)):
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
                    "role_id": row[4],
                    "is_active": bool(row[5]),
                    "role_name": emp.role_name  # Добавляем недостающее поле из входных данных
                }
            
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Сотрудник с таким card_id уже существует")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")

@app.post("/admin/add-room", tags = ["Admin"], response_model=schemas.Room)
async def add_room(emp: schemas.RoomCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO rooms (
                    room_number,
                    description,
                    entry_level
                    )
                    VALUES (
                    %s, %s, %s
                    )
                    RETURNING *
                    """
            
            crs.execute(queue, (
                         emp.room_number,
                         emp.description, 
                         emp.entry_level
                         ))
            
            response = crs.fetchone()
            db.commit()
            return {
                "id": response[0],
                "room_number": response[1],
                "description": response[2],
                "entry_level": response[3]
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
async def add_access_point(emp: schemas.AccessPointCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO access_points (
                    room_id,
                    entrance_name,
                    direction
                    )
                    VALUES (
                    %s, %s, %s
                    )
                    RETURNING *
                    """
            
            crs.execute(queue, (
                emp.room_id,
                emp.entrance_name,
                emp.direction.value
            ))

            response = crs.fetchone()

            db.commit()

            return {
                "id": response[0],
                "room_id": response[1],
                "entrance_name": response[2],
                "direction": response[3]
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

@app.post("/admin/add-role", tags = ["Admin"], response_model=schemas.Role)
async def add_role(emp: schemas.RoleCreate, db = Depends(get_db)):

    try:

        with db.cursor() as crs:

            queue = """
                    INSERT INTO roles (role_name, access_level)
                    VALUES (%s, %s)
                    RETURNING id, role_name, access_level
                    """
            
            crs.execute(queue, (emp.role_name, emp.access_level))

            response = crs.fetchone()

            db.commit()

            return {"id": response[0],
                     "role_name": response[1],
                       "access_level": response[2]
            }
        
    except HTTPException as http_ex:
        raise http_ex
        
    except psycopg2.errors.UniqueViolation:

        db.rollback()
        raise HTTPException(status_code=400, detail = "Такая роль уже существует")

    except Exception as e:

        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

@app.post("/admin/add-access-group", tags = ["Admin"], response_model=schemas.AccessGroup)
async def add_access_group(emp: schemas.AccessGroupCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO access_groups (
                    group_name
                    )
                    VALUES (%s)
                    RETURNING id, group_name
                    """
            
            crs.execute(queue, (emp.group_name,))

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
        raise HTTPException(status_code = 500, detail="Ошибка добавления роли")

@app.post("/admin/assign-group-to-employee", tags=["Admin"], response_model=schemas.EmployeeAccessGroup)
async def assign_group_to_employee(emp: schemas.EmployeeAccessGroupCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("SELECT id FROM employees WHERE card_id = %s", (emp.card_id,))
            employee_row = crs.fetchone()

            crs.execute("SELECT id FROM access_groups WHERE group_name = %s", (emp.group_name,))
            group_row = crs.fetchone()
            
            if not employee_row:
                raise HTTPException(status_code=404, detail=f"Сотрудник с картой {emp.card_id} не найден")
            
            if not group_row:
                raise HTTPException(status_code=404, detail=f"Группа {emp.group_name} не найдена")
            
            emp_id = employee_row[0]
            grp_id = group_row[0]

            query = """
                    INSERT INTO employee_access_group (employee_id, group_id)
                    VALUES (%s, %s)
                    RETURNING id
                    """
            
            crs.execute(query, (emp_id, grp_id))
            res_id = crs.fetchone()[0]
            db.commit()

            return {
                "id": res_id,
                "card_id": emp.card_id,
                "group_name": emp.group_name
            }

    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=400, detail="Пользователь уже находится в этой группе")
    except HTTPException as htex:
        raise htex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {e}")


@app.post("/admin/assign-room-to-group", tags=["Admin"])
async def assign_room_to_group(data: schemas.RoomGroupCreate, db = Depends(get_db)):
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
                    RETURNING id, group_id, room_id
                    """
            crs.execute(query, (group_id, data.room_id))
            res = crs.fetchone()
            db.commit()

            return {"id": res[0], "group_id": res[1], "room_id": res[2]}

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
async def remove_employee_from_access_group(card_id: str, group_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            query = """
                SELECT eag.id, e.full_name 
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

            record_id, full_name = res

            crs.execute("DELETE FROM employee_access_group WHERE id = %s", (record_id,))
            db.commit()

            return {
                "status": "ОК",
                "message": f"Сотрудник {full_name} успешно удален из группы {group_name}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/remove-room-from-access-group/{group_name}/{room_number}", tags=["Admin"], response_model=schemas.StatusResponse)
async def remove_room_from_access_group(group_name: str, room_number: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            query = """
                DELETE FROM group_rooms 
                WHERE group_id = (SELECT id FROM access_groups WHERE group_name = %s)
                  AND room_id = (SELECT id FROM rooms WHERE room_number = %s)
            """
            
            crs.execute(query, (group_name, room_number))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Связь не найдена. Проверьте название группы и номер комнаты.")
            
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
async def remove_access_group(group_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute("DELETE FROM access_groups WHERE group_name = %s", (group_name,))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Группа '{group_name}' не найдена")
            
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
async def delete_employee(card_id: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute("DELETE FROM employees WHERE card_id = %s", (card_id,))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник с такой картой не найден")
            
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
async def change_employee_card_status(card_id: str, restrict: bool, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            new_status = 0 if restrict else 1
            
            crs.execute(
                "UPDATE employees SET is_active = %s WHERE card_id = %s",
                (new_status, card_id)
            )

            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Сотрудник с такой картой не найден")

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
 
@app.patch("/admin/change-access-level-by-role/{role_name}", tags=["Admin"], response_model=schemas.StatusResponse)
async def change_access_level_by_role(role_name: str, access_level: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute(
                "UPDATE roles SET access_level = %s WHERE role_name = %s",
                (access_level, role_name)
            )

            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Роль '{role_name}' не найдена")

            db.commit()

            return {
                "status": "ОК", 
                "message": f"Уровень доступа для роли '{role_name}' успешно изменен на {access_level}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/admin/change-employee-role/{card_id}", tags=["Admin"], response_model=schemas.StatusResponse)
async def change_employee_role(card_id: str, new_role_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

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

@app.patch("/admin/change-room-access-level/{room_number}", tags=["Admin"], response_model=schemas.StatusResponse)
async def change_room_access_level(room_number: int, level: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute(
                "UPDATE rooms SET entry_level = %s WHERE room_number = %s",
                (level, room_number)
            )

            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Комната №{room_number} не найдена")

            db.commit()

            return {
                "status": "ОК", 
                "message": f"Комнате №{room_number} успешно назначен уровень допуска {level}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@app.delete("/admin/remove-room/{room_number}", tags=["Admin"], response_model=schemas.StatusResponse)
async def remove_room(room_number: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute("DELETE FROM rooms WHERE room_number = %s", (room_number,))

            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Комната №{room_number} не найдена")

            db.commit()
            return {"status": "ОК", "message": f"Комната №{room_number} успешно удалена из системы"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")

@app.delete("/admin/remove-access-point/{room_number}/{entrance_name}", tags=["Admin"], response_model=schemas.StatusResponse)
async def delete_access_point(room_number: int, entrance_name: str, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            query = """
                DELETE FROM access_points 
                WHERE entrance_name = %s 
                  AND room_id = (SELECT id FROM rooms WHERE room_number = %s)
            """
            
            crs.execute(query, (entrance_name, room_number))
            
            if crs.rowcount == 0:
                raise HTTPException(
                    status_code=404, 
                    detail=f"В комнате №{room_number} не найдена точка доступа '{entrance_name}'"
                )
            
            db.commit()
            return {
                "status": "ОК", 
                "message": f"Точка доступа '{entrance_name}' комнаты №{room_number} успешно удалена"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/clear-database", tags = ["Admin"])
async def clear_database(db = Depends(get_db)):
    try:
        database.db_clear(conn=db)
        print("База данных очищена")
        db_init()
        print("База данных реинициализированная")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# просмотр информации

@app.get("/admin/view-logs", tags = ["Admin"], response_model=schemas.ViewLogsResponse)
async def view_logs(db = Depends(get_db), limit : int = 10, offset : int = 0):

    try:

        with db.cursor() as crs:

            crs.execute("""
                SELECT
                    l.id,
                    COALESCE(e.full_name, 'Неизвестно'), -- Если сотрудника нет, напишем 'Неизвестно'
                    r.room_number,
                    ap.entrance_name,
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

            db.commit()

            logs = []
            for row in response:
                logs.append({
                    "id": row[0],
                    "employee_name": row[1],
                    "room_number": row[2],
                    "entrance": row[3],
                    "time": row[4].strftime("%Y-%m-%d %H:%M:%S"),
                    "is_granted": bool(row[5])
                })

            return {
                "status": "ОК",
                "data": logs
            }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/view-employees", tags = ["Admin"], response_model=None)
async def view_employees(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    try:

        with db.cursor() as crs:

            queue = """
                    SELECT 
                        e.id,
                        e.full_name, 
                        e.card_id,
                        e.department,
                        r.role_name,
                        e.is_active
                    FROM employees AS e
                    JOIN roles AS r ON e.role_id = r.id
                    ORDER BY  e.full_name
                    LIMIT %s
                    OFFSET %s
                    """
            crs.execute(queue, (limit, offset))
            
            rows = crs.fetchall()

        return [
            {"id": r[0],
              "name": r[1],
                "card": r[2],
                  "dept": r[3],
                    "role": r[4],
                      "active": bool(r[5])
                      } for r in rows]
    
    except Exception as e:
        raise HTTPException(status_code = 500, detail = str(e))

@app.get("/admin/view-rooms", tags = ["Admin"], response_model = None)
async def view_rooms(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    
    try:
        with db.cursor() as crs:

            queue = """
                    SELECT
                        r.id,
                        r.room_number,
                        r.description,
                        r.entry_level
                    FROM rooms AS r
                    ORDER BY r.room_number
                    LIMIT %s OFFSET %s
                    """
            
            crs.execute(queue, (limit, offset))

            rows = crs.fetchall()

            return [{"id": r[0], "number": r[1], "desc": r[2], "level": r[3]} for r in rows]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/view-roles", tags = ["Admin"], response_model=None)
async def view_roles(limit: int = 10, offset: int = 0, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            queue = """
                    SELECT
                        id,
                        role_name,
                        access_level
                    FROM
                        roles
                    ORDER BY access_level ASC
                    LIMIT %s
                    OFFSET %s
                    """
            
            crs.execute(queue, (limit, offset))

            rows = crs.fetchall()

            return [{"id": r[0], "role_name": r[1], "acccess_level": r[2]} for r in rows]
        
    except Exception as e:
        raise HTTPException(status_code = 500, detail = str(e))
    
@app.get("/admin/employee-info/{card_id}", tags=["Admin"])
async def get_employee_info(card_id: str, db = Depends(get_db)):
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

            rooms = [{"number": row[0], "desc": row[1]} for row in crs.fetchall()]

            return {
                "card_id": card_id,
                "name": base[1],
                "department": base[2],
                "role": base[3],
                "is_active": bool(base[4]),
                "assigned_groups": groups,
                "accessible_rooms": rooms
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

