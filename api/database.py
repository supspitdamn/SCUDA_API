import psycopg2
# использование postgre обусловлено возможным большим потоков запросов к БД

DB_CONFIG = {
    "dbname": "SCUDA_INFO",
    "user": "admin",
    "password": "75egve57",
    "host": "localhost", # Запуск на локальной машине
    "port": 5432 # стандартный порт для postgre
}

def execute_connection():

    """
    Установить соединение с базой данных
    """

    try:

        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    
    except Exception as e:

        print(f"Соединение с БД не установленно. Детали: {e}")
        return None
    
def db_init():

    """
    Инициализация БД
    """

    conn = execute_connection()

    if conn:

        try:

            crs = conn.cursor()

            crs.execute("""
                        CREATE TABLE IF NOT EXISTS roles (
                        id SERIAL PRIMARY KEY,
                        role_name TEXT NOT NULL UNIQUE,
                        access_level INTEGER NOT NULL
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

            crs.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id SERIAL PRIMARY KEY,
                    room_number INTEGER NOT NULL UNIQUE,
                    description TEXT,
                    entry_level INTEGER NOT NULL
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
                    employee_id INTEGER NOT NULL,
                    access_point_id INTEGER NOT NULL,
                    event_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_granted INTEGER NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    FOREIGN KEY (access_point_id) REFERENCES access_points (id)
                )
            """)

            conn.commit()
            print("База данных успешно инициализирована!")

        except Exception as e:

            print(f"Инициализация провалена: {e}")
            conn.rollback()

        finally:

            conn.close()

def db_clear():
    """
    Очистка базы данных (TRUNCATE быстрее для больших таблиц)
    """
    conn = execute_connection()
    if conn:
        try:
            crs = conn.cursor()
            crs.execute("TRUNCATE TABLE access_logs, access_points, rooms, employees, roles CASCADE;")
            conn.commit()
            print("База данных очищена.")
        except Exception as e:
            print(f"Ошибка в очистке базы данных. Детали: {e}")
            conn.rollback()
        finally:
            conn.close()
