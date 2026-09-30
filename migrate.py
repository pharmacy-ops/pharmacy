import sqlite3
import psycopg2
from db_config import get_connection


SQLITE_DB = "pharmacy.db"


def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = get_connection()

    try:
        sqlite_cur = sqlite_conn.cursor()
        pg_cur = pg_conn.cursor()

        # -------------------------
        # داروها
        # -------------------------

        medicines = sqlite_cur.execute("""
            SELECT *
            FROM medicines
            ORDER BY id
        """).fetchall()

        print(f"تعداد داروهای قدیمی: {len(medicines)}")

        for row in medicines:

            pg_cur.execute("""
                SELECT id
                FROM medicines
                WHERE name_fa = %s
            """, (row["name_fa"],))

            exists = pg_cur.fetchone()

            if exists:
                continue

            pg_cur.execute("""
                INSERT INTO medicines
                (
                    name_fa,
                    name_en,
                    stock,
                    unit,
                    min_stock,
                    created_at,
                    updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                row["name_fa"],
                row["name_en"],
                row["stock"],
                row["unit"],
                row["min_stock"],
                row["created_at"],
                row["updated_at"]
            ))

        print("داروها منتقل شدند.")


        # -------------------------
        # کاربران
        # -------------------------

        users = sqlite_cur.execute("""
            SELECT *
            FROM users
            ORDER BY id
        """).fetchall()

        print(f"تعداد کاربران قدیمی: {len(users)}")

        for row in users:

            pg_cur.execute("""
                SELECT id
                FROM users
                WHERE username = %s
            """, (row["username"],))

            exists = pg_cur.fetchone()

            if exists:
                continue

            pg_cur.execute("""
                INSERT INTO users
                (
                    username,
                    password,
                    role,
                    active,
                    created_at
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                row["username"],
                row["password"],
                row["role"],
                bool(row["active"]),
                row["created_at"]
            ))

        print("کاربران منتقل شدند.")


        # -------------------------
        # تاریخچه مصرف
        # -------------------------

        usage = sqlite_cur.execute("""
            SELECT *
            FROM usage_history
            ORDER BY id
        """).fetchall()

        print(f"تعداد سوابق مصرف: {len(usage)}")

        for row in usage:

            pg_cur.execute("""
                SELECT id
                FROM usage_history
                WHERE operation_id = %s
            """, (row["operation_id"],))

            exists = pg_cur.fetchone()

            if exists:
                continue

            pg_cur.execute("""
                INSERT INTO usage_history
                (
                    operation_id,
                    medicine_id,
                    medicine_name,
                    amount,
                    unit,
                    username,
                    created_at,
                    sync_status
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                row["operation_id"],
                row["medicine_id"],
                row["medicine_name"],
                row["amount"],
                row["unit"],
                row["username"],
                row["created_at"],
                "synced"
            ))


        # -------------------------
        # ورود دارو
        # -------------------------

        entries = sqlite_cur.execute("""
            SELECT *
            FROM stock_entries
            ORDER BY id
        """).fetchall()

        print(f"تعداد سوابق ورود: {len(entries)}")

        for row in entries:

            pg_cur.execute("""
                SELECT id
                FROM stock_entries
                WHERE operation_id = %s
            """, (row["operation_id"],))

            exists = pg_cur.fetchone()

            if exists:
                continue

            pg_cur.execute("""
                INSERT INTO stock_entries
                (
                    operation_id,
                    medicine_id,
                    medicine_name,
                    amount,
                    unit,
                    username,
                    created_at,
                    sync_status
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                row["operation_id"],
                row["medicine_id"],
                row["medicine_name"],
                row["amount"],
                row["unit"],
                row["username"],
                row["created_at"],
                "synced"
            ))


        # -------------------------
        # اصلاح موجودی
        # -------------------------

        corrections = sqlite_cur.execute("""
            SELECT *
            FROM stock_corrections
            ORDER BY id
        """).fetchall()

        print(
            f"تعداد اصلاحات: {len(corrections)}"
        )

        for row in corrections:

            pg_cur.execute("""
                SELECT id
                FROM stock_corrections
                WHERE operation_id = %s
            """, (row["operation_id"],))

            exists = pg_cur.fetchone()

            if exists:
                continue

            pg_cur.execute("""
                INSERT INTO stock_corrections
                (
                    operation_id,
                    medicine_id,
                    medicine_name,
                    old_stock,
                    new_stock,
                    difference,
                    username,
                    created_at,
                    sync_status
                )
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                row["operation_id"],
                row["medicine_id"],
                row["medicine_name"],
                row["old_stock"],
                row["new_stock"],
                row["difference"],
                row["username"],
                row["created_at"],
                "synced"
            ))


        pg_conn.commit()

        print()
        print("==============================")
        print("انتقال اطلاعات با موفقیت انجام شد")
        print("==============================")


    except Exception as e:

        pg_conn.rollback()

        print()
        print("خطا در انتقال اطلاعات:")
        print(e)

    finally:

        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()