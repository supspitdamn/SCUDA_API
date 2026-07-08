import json
import time
import traceback
import psycopg2
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883

mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
db_pool = None


def init_worker_pool(pool_instance):
    global db_pool
    db_pool = pool_instance
    print(f"[WORKER INIT] Пул успешно передан воркеру: {db_pool}")


def get_whitelist_for_mk_direct(device_mac: str) -> list:
    print(f"[WORKER SQL] Запрос вайтлиста для MAC: {device_mac}")
    if not db_pool:
        print("[WORKER SQL ERROR] db_pool равен None!")
        return []
    
    conn = db_pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor() as crs:
            sql_mac = device_mac.strip().upper()
            crs.execute(
                "SELECT id FROM access_points WHERE device_mac = %s", (sql_mac,)
            )
            ap_row = crs.fetchone()
            if not ap_row:
                print(f"[WORKER SQL WARNING] MAC {sql_mac} отсутствует в БД!")
                return []

            queue = """
                SELECT DISTINCT e.card_id
                FROM employees AS e
                JOIN employee_access_group eag ON e.id = eag.employee_id
                JOIN access_groups ag ON eag.group_id = ag.id
                JOIN group_rooms gr ON ag.id = gr.group_id
                JOIN access_points ap ON gr.room_id = ap.room_id
                WHERE ap.device_mac = %s AND e.is_active = 1
            """
            crs.execute(queue, (sql_mac,))
            rows = crs.fetchall()
            print(f"[WORKER SQL] Найдено строк в fetchall: {rows}")
            
            # ГАРАНТИРОВАННО извлекаем саму строку карты (индекс 0) из кортежа psycopg2
            cards = [str(row[0]).strip() for row in rows if row and row[0]]
            print(f"[WORKER SQL] Итоговый чистый список карт: {cards}")
            return cards
    except Exception as e:
        print(f"[WORKER SQL CRITICAL] get_whitelist упал: {e}")
        traceback.print_exc()
        return []
    finally:
        db_pool.putconn(conn)



def receive_from_mk_direct(payload: dict, device_mac: str):
    print(f"[WORKER LOG] Старт записи лога. MAC: {device_mac}")
    if not db_pool:
        print("[WORKER LOG ERROR] db_pool равен None!")
        return
    
    conn = db_pool.getconn()
    try:
        conn.autocommit = True  # Принудительная запись INSERT без зависания транзакции
        with conn.cursor() as crs:
            sql_mac = device_mac.strip().upper()
            crs.execute(
                "SELECT id FROM access_points WHERE device_mac = %s", (sql_mac,)
            )
            ap_res = crs.fetchone()
            print(f"[WORKER LOG SQL] Поиск точки прохода: {ap_res}")
            if not ap_res:
                print(f"[WORKER LOG ERROR] Отмена. Точка {sql_mac} не найдена.")
                return
            ap_id = ap_res[0]  # Извлекаем чистое число, а не кортеж (1,)

            card_id = payload.get("uid") or payload.get("card_id")
            print(f"[WORKER LOG] Номер карты из JSON: {card_id}")
            if not card_id:
                print(f"[WORKER LOG ERROR] В JSON нет ключа uid/card_id! JSON: {payload}")
                return

            crs.execute("SELECT id FROM employees WHERE card_id = %s", (card_id,))
            res = crs.fetchone()
            print(f"[WORKER LOG SQL] Поиск сотрудника: {res}")
            emp_id = res[0] if res else None  # Извлекаем чистое число или None

            ts = payload.get("ts") or payload.get("timestamp") or int(time.time())
            is_granted = 1 if str(payload.get("access")).lower() == "granted" else 0

            queue = """
                INSERT INTO access_logs (employee_id, card_id_text, access_point_id, event_time, is_granted)
                VALUES (%s, %s, %s, %s, %s)
            """

            print(f"[WORKER LOG SQL] INSERT: emp={emp_id}, card='{card_id}', ap={ap_id}, ts={ts}")
            crs.execute(queue, (emp_id, card_id, ap_id, ts, is_granted))
            print(f"[WORKER SUCCESS] ЛОГ УСПЕШНО ЗАПИСАН! Карта: {card_id}")
    except Exception as e:
        print(f"[WORKER LOG SQL CRITICAL] Ошибка записи лога: {e}")
        traceback.print_exc()
    finally:
        db_pool.putconn(conn)


def check_and_trigger_sync(client, device_mac, device_version):
    print(f"[WORKER SYNC] Сверка версий для {device_mac}. На плате: {device_version}")
    raw_cards = get_whitelist_for_mk_direct(device_mac)
    server_version = len(raw_cards)
    print(f"[WORKER SYNC DIAG] Плата = {device_version} | Server = {server_version}")

    if device_version != server_version:
        print(f"[WORKER SYNC] Версии не равны! Формируем JSON...")
        
        sync_payload = {
            "cmd": "sync_cards",
            "request_id": f"auto-sync-{int(time.time())}",
            "whitelist_version": server_version,
            "cards": raw_cards
        }

        topic = f"skud/{device_mac}/cmd/sync_cards"
        
        print(f"[WORKER SYNC MQTT] Отправка топика с очисткой памяти: '{topic}'")
    
        print(f" -> Payload: {sync_payload}")
        
        res = client.publish(topic, json.dumps(sync_payload))
        print(f" -> Код ответа брокера: {res.rc} (0 = УСПЕХ)")

        conn = db_pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as crs:
                sql_mac = device_mac.strip().upper()
                crs.execute(
                    "UPDATE access_points SET whitelist_version = %s WHERE device_mac = %s;",
                    (server_version, sql_mac),
                )
                print(f"[WORKER SYNC SQL] Версия {server_version} сохранена в БД")
        except Exception as e:
            print(f"[WORKER SYNC SQL ERROR] Ошибка: {e}")
        finally:
            db_pool.putconn(conn)
    else:
        print("[WORKER SYNC] Версии равны, update не требуется.")



def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[WORKER CORE] on_connect вызван. Код ответа (rc): {rc}")
    if rc == 0:
        print("[WORKER CORE] Успешно подключились к Mosquitto!")
        client.subscribe("skud/+/event/access")
        client.subscribe("skud/+/status")
        print("[WORKER CORE] Подписки оформлены.")
    else:
        print(f"[WORKER CORE ERROR] Брокер отклонил подключение! Код: {rc}")


def on_message(client, userdata, msg):
    try:
        print("\n" + "=" * 50)
        print(f"[WORKER INBOUND] Прилетел топик: {msg.topic}")
        raw_body = msg.payload.decode("utf-8")
        print(f"[WORKER INBOUND] Сырой текст JSON: {raw_body}")

        payload = json.loads(raw_body)
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 3:
            print(f"[WORKER INBOUND ERROR] Структура топика битая: {msg.topic}")
            return

        # Забираем оригинальный MAC как есть ('esp32_34CDB033BBD8'), без изменения регистра
        device_mac = topic_parts[1].strip()
        print(f"[WORKER INBOUND] Распознан оригинальный MAC: {device_mac}")

        if "event/access" in msg.topic:
            print("[WORKER INBOUND ROUTE] Пакет: EVENT/ACCESS")
            receive_from_mk_direct(payload, device_mac)
            device_version = (
                payload.get("whitelist_version") or payload.get("version") or 0
            )
            check_and_trigger_sync(client, device_mac, device_version)

        elif "status" in msg.topic:
            print("[WORKER INBOUND ROUTE] Пакет: STATUS")
            device_version = (
                payload.get("whitelist_version") or payload.get("version") or 0
            )
            check_and_trigger_sync(client, device_mac, device_version)

        print("=" * 50 + "\n")
    except Exception as e:
        print(f"[WORKER CRITICAL EXCEPTION] Ошибка в on_message: {e}")
        traceback.print_exc()


def start_mqtt():
    print("[WORKER START] Инициализация фонового MQTT...")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[WORKER START] Поток loop_start() запущен.")
