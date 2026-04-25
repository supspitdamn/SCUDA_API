import sqlite3

DATA_BASE = "SCUDA_INFO"

def execute_connection():

    """
    Установить соединение с базой данных
    """

    try:

        conn = sqlite3.connect(DATA_BASE)
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
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    entry_level INTEGER NOT NULL
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_number INTEGER NOT NULL,
                    description TEXT,
                    entry_level INTEGER NOT NULL
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS access_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    entrance_name TEXT NOT NULL,
                    direction TEXT CHECK (direction IN ('IN', 'OUT', 'BOTH')),
                    FOREIGN KEY (room_id) REFERENCES rooms (id)
                )
            """)

            crs.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    access_point_id INTEGER NOT NULL, -- Заменили room_id
                    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_granted INTEGER NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    FOREIGN KEY (access_point_id) REFERENCES access_points (id)
                )
            """)

            conn.commit()
            print("База данных успешно инициализирована!")

        except Exception as e:

            print(f"Инициализация провалена: {e}")

        finally:

            conn.close()

def db_clear():
    """
    Очистка базы данных
    """

    conn = execute_connection()

    try:

        crs = conn.cursor()

        crs.execute("""DELETE FROM employees""")

        crs.execute("""DELETE FROM rooms""")

        crs.execute("""DELETE FROM access_points""")

        crs.execute("""DELETE FROM access_logs""")

    except Exception as e:

        print(f"Ошибка в очистке базы данных. Детали: {e}")
