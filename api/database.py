import psycopg2
from contextlib import asynccontextmanager
from psycopg2 import pool
from fastapi import Request
from fastapi import HTTPException
# использование postgre обусловлено возможным большим потоков запросов к БД

DB_CONFIG = {
    "dbname": "SCUDA_INFO",
    "user": "postgres",         
    "password": "75egve57",     # Ваш пароль из инсталлятора
    "host": "127.0.0.1",        # Прямой адрес
    "port": 5432,
}

@asynccontextmanager
async def lifespan(app):

    print("Создание пула соединений...")
    app.db_pool = pool.ThreadedConnectionPool(1, 20, **DB_CONFIG)
    conn = app.db_pool.getconn()

    try:
        db_init(conn)
        conn.commit()

    except Exception as e:
        raise RuntimeError("Приложение не может быть запущено без БД") from e
    
    finally:
        app.db_pool.putconn(conn)

    yield

    print("Закрытие пула соединений...")
    app.db_pool.closeall()

def get_db(request: Request):
    conn = request.app.db_pool.getconn()
    try:
        yield conn
    finally:
        request.app.db_pool.putconn(conn)

def execute_connection():

    """
    Установить соединение с базой данных
    ПРИЗНАНА УСТАРЕВШЕЙ!
    """

    try:

        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    
    except Exception as e:

        print(f"Соединение с БД не установленно. Детали: {e}")
        return None
    
def db_init(conn):
    """
    Инициализация модифицированной БД: добавлена логика групп доступа (Many-to-Many)
    """
    try:
        with conn.cursor() as crs:

            crs.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    role_name TEXT NOT NULL UNIQUE,
                    access_level INTEGER NOT NULL
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS access_groups (
                    id SERIAL PRIMARY KEY,
                    group_name TEXT NOT NULL UNIQUE
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id SERIAL PRIMARY KEY,
                    card_id TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (role_id) REFERENCES roles (id)
                )
            """)

            # Связь Сотрудник <-> Группа доступа. Многие ко многим
            crs.execute("""
                CREATE TABLE IF NOT EXISTS employee_access_group (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE,
                    FOREIGN KEY (group_id) REFERENCES access_groups (id) ON DELETE CASCADE,
                    UNIQUE(employee_id, group_id)
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id SERIAL PRIMARY KEY,
                    room_number INTEGER NOT NULL UNIQUE,
                    description TEXT,
                    entry_level INTEGER NOT NULL
                )
            """)

            # Связь Группа доступа <-> Комната. тоже многие ко многим
            crs.execute("""
                CREATE TABLE IF NOT EXISTS group_rooms (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    room_id INTEGER NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES access_groups (id) ON DELETE CASCADE,
                    FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE,
                    UNIQUE(group_id, room_id)
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS access_points (
                    id SERIAL PRIMARY KEY,  
                    room_id INTEGER NOT NULL,
                    entrance_name TEXT NOT NULL,
                    direction TEXT CHECK (direction IN ('IN', 'OUT', 'BOTH')),
                    FOREIGN KEY (room_id) REFERENCES rooms (id) ON DELETE CASCADE
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER,
                    card_id_text TEXT,
                    access_point_id INTEGER NOT NULL,
                    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_granted INTEGER NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE SET NULL,
                    FOREIGN KEY (access_point_id) REFERENCES access_points (id) ON DELETE CASCADE
                )
            """)

            conn.commit()
            print("Модифицированная база данных успешно инициализирована!")

    except Exception as e:
        print(f"Инициализация провалена: {e}")
        conn.rollback()

def db_clear(conn):
    """
    Очистка базы данных
    """
    tables = [
        "access_logs",
        "access_points",
        "group_rooms",
        "employee_access_group",
        "rooms",
        "employees",
        "access_groups",
        "roles"
    ]
    
    try:
        with conn.cursor() as crs:
            for table in tables:
                # Используем CASCADE для PostgreSQL, чтобы удалить связанные объекты
                crs.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            
            conn.commit()
            print("Все таблицы успешно удалены.")
            
    except Exception as e:
        print(f"Ошибка при удалении таблиц: {e}")
        conn.rollback()

