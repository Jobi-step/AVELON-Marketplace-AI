import sqlite3
from datetime import datetime, timezone


DB_NAME = "avelon_marketplace.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            tariff TEXT DEFAULT 'free',
            generations_used INTEGER DEFAULT 0,
            free_generations INTEGER DEFAULT 3,
            subscription_until TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            supplier_text TEXT,
            purchase_price REAL,
            recommended_price REAL,
            city TEXT,
            competition TEXT,
            sale_probability TEXT,
            sale_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


def create_user_if_not_exists(telegram_id, username=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users (
            telegram_id,
            username
        )
        VALUES (?, ?)
        """,
        (
            telegram_id,
            username,
        ),
    )

    if username:
        cursor.execute(
            """
            UPDATE users
            SET username = ?
            WHERE telegram_id = ?
            """,
            (
                username,
                telegram_id,
            ),
        )

    conn.commit()
    conn.close()


def get_user(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            telegram_id,
            username,
            tariff,
            generations_used,
            free_generations,
            subscription_until,
            created_at
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    user = cursor.fetchone()
    conn.close()

    return user


def get_remaining_free_generations(telegram_id):
    user = get_user(telegram_id)

    if not user:
        return 3

    generations_used = user[3]
    free_generations = user[4]

    return max(
        free_generations - generations_used,
        0,
    )


def increment_generation(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET generations_used = generations_used + 1
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    conn.commit()
    conn.close()


def save_product(telegram_id, product):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO saved_products (
            telegram_id,
            title,
            description,
            supplier_text,
            purchase_price,
            recommended_price,
            city,
            competition,
            sale_probability,
            sale_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            telegram_id,
            product.get("title", ""),
            product.get("description", ""),
            product.get("supplier_text", ""),
            product.get("purchase_price", 0),
            product.get("recommended_price", 0),
            product.get("city", ""),
            product.get("competition", ""),
            product.get("sale_probability", ""),
            product.get("sale_time", ""),
        ),
    )

    conn.commit()
    conn.close()


def get_saved_products(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            description,
            supplier_text,
            purchase_price,
            recommended_price,
            city,
            competition,
            sale_probability,
            sale_time,
            created_at
        FROM saved_products
        WHERE telegram_id = ?
        ORDER BY id DESC
        """,
        (telegram_id,),
    )

    products = cursor.fetchall()
    conn.close()

    return products


def delete_saved_product(product_id, telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM saved_products
        WHERE id = ?
        AND telegram_id = ?
        """,
        (
            product_id,
            telegram_id,
        ),
    )

    conn.commit()
    conn.close()

    from datetime import datetime, timezone


def ensure_subscription_columns():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "paid_generations_used" not in columns:
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN paid_generations_used INTEGER DEFAULT 0
            """
        )

    if "generation_limit" not in columns:
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN generation_limit INTEGER DEFAULT 0
            """
        )

    conn.commit()
    conn.close()


def activate_subscription(
    telegram_id,
    tariff,
    subscription_until,
    generation_limit,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET
            tariff = ?,
            subscription_until = ?,
            generation_limit = ?,
            paid_generations_used = 0
        WHERE telegram_id = ?
        """,
        (
            tariff,
            str(subscription_until),
            generation_limit,
            telegram_id,
        ),
    )

    conn.commit()
    conn.close()


def increment_paid_generation(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET paid_generations_used = paid_generations_used + 1
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    conn.commit()
    conn.close()


def get_paid_generation_info(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            paid_generations_used,
            generation_limit
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    result = cursor.fetchone()
    conn.close()

    if not result:
        return 0, 0

    return result[0] or 0, result[1] or 0


def expire_subscription_if_needed(telegram_id):
    user = get_user(telegram_id)

    if not user:
        return

    tariff = user[2]
    subscription_until = user[5]

    if tariff == "free" or not subscription_until:
        return

    try:
        expires_at = int(subscription_until)
    except (TypeError, ValueError):
        return

    now_timestamp = int(
        datetime.now(timezone.utc).timestamp()
    )

    if now_timestamp < expires_at:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET
            tariff = 'free',
            subscription_until = NULL,
            paid_generations_used = 0,
            generation_limit = 0
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    conn.commit()
    conn.close()