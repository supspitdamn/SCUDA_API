import fastapi
import schemas
import database
from fastapi import FastAPI, HTTPException, Depends
from database import db_init, get_db, lifespan
import psycopg2
from contextlib import asynccontextmanager

app = fastapi.FastAPI(debug=True, title = "СКУД API система", lifespan=lifespan)

# Сервисная часть

@app.post("/service/check-access", tags=["Service"])
async def check_access():
    pass

@app.post("/service/process_access", tags = ["Service"])
async def proccess_access():
    pass

# Часть админа

# добавление нового

@app.post("/admin/add-employee", tags=["Admin"], response_model=schemas.Employee)
async def add_employee(emp: schemas.EmployeeCreate, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO employees (
                    card_id,
                    full_name,
                    department,
                    role_id,
                    is_active
                    )
                    VALUES(
                    %s,  %s,  %s, %s,  %s
                    )
                    RETURNING *
                    """
            
            crs.execute(queue,(
                emp.card_id,
                emp.full_name,
                emp.department,
                emp.role_id, 
                emp.is_active))
            
            row = crs.fetchone() # Получаем кортеж, например (1, 'card123', 'Имя', 'Департамент', 2, 1)
            db.commit()

            if row:

                return {
                    "id": row[0],
                    "card_id": row[1],
                    "full_name": row[2],
                    "department": row[3],
                    "role_id": row[4],
                    "is_active": row[5]
                }
            
    except HTTPException as http_ex:
        raise http_ex
        
    except psycopg2.errors.UniqueViolation: # Повторное создание того же сотрудника
        db.rollback()
        raise HTTPException(status_code=400, detail="Такой пользователь существует")
    
    except Exception as e: # Какие-то проблемы сервера
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
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

@app.post("/admin/assign-group-to-employee", tags = ["Admin"], response_model=schemas.EmployeeAccessGroup)
async def assign_group_to_employee(emp: schemas.EmployeeAccessGroupCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO employee_access_group (
                    employee_id,
                    group_id
                    )
                    VALUES (%s, %s)
                    RETURNING id, employee_id, group_id
                    """
            
            crs.execute(queue, (emp.employee_id, emp.group_id))

            response = crs.fetchone()

            db.commit()

            print(f"Пользователь с id {response[1]} был добавлен в группу {response[2]}")

            return {"id": response[0],
                    "employee_id": response[1],
                    "group_id": response[2]}
    except HTTPException as htex:
        raise htex
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code = 400, detail = "Пользователь уже находится в этой группе")
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(status_code=404, detail="Указанный сотрудник или группа доступа не найдены")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = f"Ошибка сервера. Детали: {e}")

@app.post("/admin/assign-room-to-group", tags = ["Admin"], response_model=schemas.RoomGroup)
async def assign_room_to_group(emp: schemas.RoomGroupCreate, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            queue = """
                    INSERT INTO group_rooms (
                    group_id,
                    room_id
                    )
                    VALUES (%s, %s)
                    RETURNING id, group_id, room_id
                    """
            
            crs.execute(queue, (emp.group_id, emp.room_id))

            response = crs.fetchone()

            db.commit()

            print(f"Комната с id {response[2]} внесена в группу {response[1]}")

            return {"id": response[0],
                    "group_id": response[1],
                    "room_id": response[2]}
    except HTTPException as htex:
        raise htex
    except psycopg2.errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code = 400, detail = "В группе уже существует эта комната")
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(status_code = 404, detail = "Группа или комната не найдены")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = str(e))
    
# Методы удаления/измения статусов

@app.delete("/admin/remove-employee-from-access-group/{employee_id}/{group_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def remove_employee_from_access_group(employee_id : int, group_id: int, db = Depends(get_db)):

    try:

        with db.cursor() as crs:

            queue = """
                    SELECT FROM employee_access_group WHERE group_id = %s and employee_id = %s
                    """
            
            crs.execute(queue, (group_id, employee_id))

            if not crs.fetchone():

                raise HTTPException(status_code = 404, detail = f"Пользователь с id {employee_id} не найден в группе доступа с id {group_id}")

            queue = """
                    DELETE FROM employee_access_group WHERE group_id = %s and employee_id = %s
                    """

            crs.execute(queue, (group_id, employee_id))

            db.commit()

            print(f"Пользователь с id {employee_id} был удален из группы доступа с id {group_id}")

            return {"status": "ОК",
                     "message" : f"Пользователь с id {employee_id} был удален из группы доступа с id {group_id}"}
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code = 500, detail = str(e))

@app.delete("/admin/remove-room-from-access-group/{group_id}/{room_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def remove_room_from_access_group(group_id: int, room_id: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute(
                "DELETE FROM group_rooms WHERE group_id = %s AND room_id = %s",
                (group_id, room_id)
            )
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Связь группы и комнаты не найдена")
            
            db.commit()
            return {"status": "ОК", "message": f"Комната {room_id} исключена из группы {group_id}"}
            
    except HTTPException as htex:
        raise htex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/admin/remove-access-group/{group_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def remove_access_group(group_id: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:
            crs.execute("DELETE FROM access_groups WHERE id = %s", (group_id,))
            
            if crs.rowcount == 0:
                raise HTTPException(status_code=404, detail="Группа доступа не найдена")
            
            db.commit()
            return {"status": "ОК", "message": f"Группа {group_id} полностью удалена из системы"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))   

@app.delete("/admin/remove-employee/{employee_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def delete_employee(employee_id: int, db = Depends(get_db)):

    try:
        with db.cursor() as crs:
            crs.execute("SELECT id FROM employees WHERE id = %s", (employee_id,))
            response = crs.fetchone()
            if not response:
                raise HTTPException(status_code=404, detail = "Сотрудник не найден")
            
            crs.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
            db.commit()
            return {"status": "ОК", "message": f"Сотрудник с id {employee_id} успешно удален"}
        
    except HTTPException as http_ex:
        raise http_ex
    except psycopg2.errors.ForeignKeyViolation:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить: у сотрудника есть связанные записи в логах доступа."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/admin/employee-change-card-status/{employee_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def change_employee_card_status(employee_id: int, restrict: bool, db = Depends(get_db)):
    
    try:
        with db.cursor() as crs:

            crs.execute("SELECT is_active from employees WHERE id = %s", (employee_id,))

            response = crs.fetchone()
            if not response:
                raise HTTPException(status_code=404, detail = "Сотрудник не найден")

            crs.execute(
                """
                UPDATE employees SET is_active = %s WHERE id = %s
                """,
                (0 if restrict else 1, employee_id,)
            )

            db.commit()
            return {"status": "ОК", "message" : f"Доступ сотруднику {employee_id} изменен на {'Не активен' if restrict else 'Активен'}"}
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))
    
@app.patch("/admin/change_access_level_by_role/{role_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def change_access_level_by_role(role_id: int, access_level: int, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            crs.execute("SELECT id FROM roles WHERE id = %s ", (role_id,))

            response = crs.fetchone()

            if not response:
                raise HTTPException(status_code = 404, detail="Такой роли не существует")

            crs.execute("UPDATE roles SET access_level = %s WHERE id = %s", (access_level, role_id))

            db.commit()

            return {"status": "ОК", "message": f"Уровень доступа для роли {role_id} изменен на {access_level}"}
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

@app.patch("/admin/change_access_level_by_employee/{employee_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def change_access_level_by_employee(employee_id: int, new_role_id: int, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            crs.execute("SELECT id FROM employees WHERE id = %s", (employee_id,))

            response = crs.fetchone()

            if not response:
                raise HTTPException(status_code=404, detail = "Сотрудник не найден")
            
            crs.execute("SELECT id FROM roles WHERE id = %s", (new_role_id,))

            response = crs.fetchone()

            if not response:
                raise HTTPException(status_code=404, detail = "Роль не найдена")
            
            crs.execute("UPDATE employees SET role_id = %s WHERE id = %s", (new_role_id, employee_id,))

            db.commit()

            return {"status": "ОК", "message": f"Сотруднику {employee_id} назначена роль {new_role_id}"}
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

@app.patch("/admin/change-room-access-level/{room_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def change_room_access_level(room_id: int, level: int, db = Depends(get_db)):
    
    try:
        with db.cursor() as crs:

            crs.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))

            response = crs.fetchone()

            if not response:

                raise HTTPException(status_code = 404, detail = "Комната не найдена")

            crs.execute("UPDATE rooms SET entry_level = %s WHERE id = %s", (level, room_id))

            db.commit()

            return {"status": "ОК", "message": f"Комнате {room_id} назначен уровень допуска {level}"}
        
    except HTTPException as http_ex:
        raise http_ex   
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

@app.delete("/admin/remove_room/{room_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def remove_room(room_id: int, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            crs.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))

            response = crs.fetchone()

            if not response:

                raise HTTPException(status_code = 404, detail = "Комната не найдена")
            
            crs.execute("DELETE FROM rooms WHERE id = %s", (room_id,))

            db.commit()

            return {"status": "ОК", "message" : f"Комната {room_id} удалена"}
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

@app.delete("/admin/remove-access-point/{room_id}/{access_point_id}", tags = ["Admin"], response_model=schemas.StatusResponse)
async def delete_access_point(room_id: int, access_point_id: int, db = Depends(get_db)):

    try:
        with db.cursor() as crs:

            crs.execute("SELECT id FROM access_points WHERE id = %s AND room_id = %s ", (access_point_id, room_id))

            response = crs.fetchone()

            if not response:

                raise HTTPException(status_code = 404, detail = f"В комнате {room_id} не найдена точка доступа {access_point_id}")
            
            crs.execute("DELETE FROM access_points WHERE id = %s", (access_point_id,))
            
            db.commit()

            return {"status": "ОК", "message" : f"Точка доступа {access_point_id} комнаты {room_id} удалена"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail = str(e))

# просмотр информации

@app.get("/admin/view-logs", tags = ["Admin"], response_model=schemas.ViewLogsResponse)
async def view_logs(db = Depends(get_db), limit : int = 10, offset : int = 0):

    try:

        with db.cursor() as crs:

            crs.execute("""
                SELECT
                    l.id,
                    e.full_name,
                    r.room_number,
                    ap.entrance_name,
                    l.event_time,
                    l.is_granted,
                    -- Собираем названия групп сотрудника в одну строку (PostgreSQL специфично)
                    array_to_string(array_agg(distinct ag.group_name), ', ') as groups
                FROM access_logs AS l
                JOIN employees AS e ON l.employee_id = e.id
                JOIN access_points AS ap ON l.access_point_id = ap.id
                JOIN rooms AS r ON ap.room_id = r.id
                -- Присоединяем группы через новые таблицы
                LEFT JOIN employee_access_group eag ON e.id = eag.employee_id
                LEFT JOIN access_groups ag ON eag.group_id = ag.id
                GROUP BY l.id, e.full_name, r.room_number, ap.entrance_name, l.event_time, l.is_granted
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
                "status": "success",
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
                        roles_name,
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
    
@app.get("/admin/employee-info/{employee_id}", tags=["Admin"])
async def get_employee_info(employee_id: int, db = Depends(get_db)):
    try:
        with db.cursor() as crs:

            crs.execute("""
                SELECT e.full_name, e.card_id, e.department, r.role_name, e.is_active
                FROM employees e
                JOIN roles r ON e.role_id = r.id
                WHERE e.id = %s
            """, (employee_id,))

            base = crs.fetchone()
            if not base:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")

            crs.execute("""
                SELECT ag.group_name 
                FROM access_groups ag
                JOIN employee_access_group eag ON ag.id = eag.group_id
                WHERE eag.employee_id = %s
            """, (employee_id,))

            groups = [row[0] for row in crs.fetchall()]

            crs.execute("""
                SELECT DISTINCT r.room_number, r.description
                FROM rooms r
                JOIN group_rooms gr ON r.id = gr.room_id
                JOIN employee_access_group eag ON gr.group_id = eag.group_id
                WHERE eag.employee_id = %s
                ORDER BY r.room_number
            """, (employee_id,))

            rooms = [{"number": row[0], "desc": row[1]} for row in crs.fetchall()]

            return {
                "id": employee_id,
                "name": base[0],
                "role": base[3],
                "is_active": bool(base[4]),
                "assigned_groups": groups,
                "accessible_rooms": rooms  # Список конкретных кабинетов
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
