import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import uuid
from datetime import datetime, date
import pandas as pd
import io

from db_config import get_connection


# =========================================================
# تنظیمات صفحه
# =========================================================

st.set_page_config(
    page_title="سیستم مدیریت داروخانه",
    page_icon="💊",
    layout="wide"
)


# =========================================================
# توابع پایه
# =========================================================

def conn():
    """
    اتصال به PostgreSQL مرکزی Supabase
    """
    return get_connection()


def now():
    return datetime.now()


def pwd(x):
    return hashlib.sha256(
        x.encode("utf-8")
    ).hexdigest()


def fetch_dataframe(query, params=None):
    """
    اجرای SELECT و تبدیل نتیجه به DataFrame
    """
    c = conn()

    try:
        with c.cursor() as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall()

            if not rows:
                return pd.DataFrame()

            columns = [
                desc[0]
                for desc in cur.description
            ]

            return pd.DataFrame(
                rows,
                columns=columns
            )

    finally:
        c.close()


# =========================================================
# ساخت مدیر اولیه
# =========================================================

def init_db():

    c = conn()

    try:
        with c.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute("""
                SELECT id
                FROM users
                WHERE username = %s
            """, ("admin",))

            admin = cur.fetchone()

            if admin is None:

                cur.execute("""
                    INSERT INTO users
                    (
                        username,
                        password,
                        role,
                        active,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    "admin",
                    pwd("admin123"),
                    "مدیر",
                    True,
                    now()
                ))

        c.commit()

    except Exception:
        c.rollback()
        raise

    finally:
        c.close()


# =========================================================
# ورود
# =========================================================

def login():

    st.title("💊 سیستم مدیریت داروخانه")
    st.subheader("ورود به سامانه")

    with st.form("login"):

        username = st.text_input(
            "نام کاربری"
        )

        password = st.text_input(
            "رمز عبور",
            type="password"
        )

        submitted = st.form_submit_button(
            "ورود",
            use_container_width=True
        )

    if submitted:

        c = conn()

        try:

            with c.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                cur.execute("""
                    SELECT *
                    FROM users
                    WHERE username = %s
                    AND password = %s
                    AND active = TRUE
                """, (
                    username.strip(),
                    pwd(password)
                ))

                user = cur.fetchone()

            if user:

                st.session_state.logged = True
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]

                st.rerun()

            else:

                st.error(
                    "نام کاربری یا رمز عبور اشتباه است."
                )

        finally:
            c.close()


# =========================================================
# منوی کناری
# =========================================================

def sidebar():

    st.sidebar.title("💊 داروخانه")

    st.sidebar.write(
        f"کاربر: {st.session_state.username}"
    )

    st.sidebar.write(
        f"نقش: {st.session_state.role}"
    )

    pages = [
        "داشبورد",
        "موجودی داروها",
        "ثبت داروی جدید",
        "ورود دارو",
        "مصرف دارو",
        "اصلاح موجودی",
        "تاریخچه مصرف",
        "تاریخچه ورود",
        "گزارش روزانه",
        "ورود داروها از Excel",
        "خروجی Excel"
    ]

    if st.session_state.role == "مدیر":

        pages += [
            "حذف دارو",
            "مدیریت کاربران"
        ]

    page = st.sidebar.radio(
        "منو",
        pages
    )

    if st.sidebar.button(
        "🚪 خروج",
        use_container_width=True
    ):

        st.session_state.logged = False

        if "username" in st.session_state:
            del st.session_state.username

        if "role" in st.session_state:
            del st.session_state.role

        st.rerun()

    return page


# =========================================================
# داشبورد
# =========================================================

def dashboard():

    st.title("🏠 داشبورد")

    medicines = fetch_dataframe("""
        SELECT *
        FROM medicines
        ORDER BY name_fa
    """)

    c = conn()

    try:

        with c.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM usage_history
                WHERE created_at::date = %s
            """, (date.today(),))

            result = cur.fetchone()

            used = result["total"] if result else 0

    finally:
        c.close()

    if medicines.empty:
        total_stock = 0
        low_stock = 0

    else:

        medicines["stock"] = pd.to_numeric(
            medicines["stock"],
            errors="coerce"
        ).fillna(0)

        medicines["min_stock"] = pd.to_numeric(
            medicines["min_stock"],
            errors="coerce"
        ).fillna(0)

        total_stock = medicines["stock"].sum()

        low_stock = int(
            (
                medicines["stock"]
                <= medicines["min_stock"]
            ).sum()
        )

    a, b, d, e = st.columns(4)

    a.metric(
        "تعداد دارو",
        len(medicines)
    )

    b.metric(
        "مجموع موجودی",
        total_stock
    )

    d.metric(
        "موجودی کم",
        low_stock
    )

    e.metric(
        "مصرف امروز",
        used
    )

    if not medicines.empty:

        low = medicines[
            medicines["stock"]
            <= medicines["min_stock"]
        ]

        if not low.empty:

            st.subheader(
                "⚠️ داروهای با موجودی کم"
            )

            st.dataframe(
                low[
                    [
                        "id",
                        "name_fa",
                        "stock",
                        "unit",
                        "min_stock"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# موجودی داروها
# =========================================================

def inventory():

    st.title("📋 موجودی داروها")

    search = st.text_input(
        "جستجوی دارو"
    )

    df = fetch_dataframe("""
        SELECT *
        FROM medicines
        ORDER BY name_fa
    """)

    if search and not df.empty:

        s = search.strip().lower()

        df = df[
            df["name_fa"]
            .fillna("")
            .str.lower()
            .str.contains(
                s,
                na=False
            )
            |
            df["name_en"]
            .fillna("")
            .str.lower()
            .str.contains(
                s,
                na=False
            )
        ]

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# ثبت داروی جدید
# =========================================================

def add_medicine():

    st.title("➕ ثبت داروی جدید")

    with st.form("add_medicine"):

        name_fa = st.text_input(
            "نام فارسی *"
        )

        name_en = st.text_input(
            "نام لاتین"
        )

        stock = st.number_input(
            "موجودی اولیه",
            min_value=0.0,
            value=0.0
        )

        unit = st.text_input(
            "واحد",
            value="عدد"
        )

        min_stock = st.number_input(
            "حداقل موجودی",
            min_value=0.0,
            value=0.0
        )

        submitted = st.form_submit_button(
            "ثبت دارو",
            use_container_width=True
        )

    if submitted:

        if not name_fa.strip():

            st.error(
                "نام فارسی الزامی است."
            )

            return

        c = conn()

        try:

            with c.cursor() as cur:

                t = now()

                cur.execute("""
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    name_fa.strip(),
                    name_en.strip(),
                    stock,
                    unit.strip() or "عدد",
                    min_stock,
                    t,
                    t
                ))

            c.commit()

            st.success(
                "دارو با موفقیت ثبت شد."
            )

        except psycopg2.errors.UniqueViolation:

            c.rollback()

            st.error(
                "این دارو قبلاً ثبت شده است."
            )

        except Exception as e:

            c.rollback()

            st.error(
                f"خطا در ثبت دارو: {e}"
            )

        finally:
            c.close()


# =========================================================
# انتخاب دارو
# =========================================================

def choose_medicine():

    c = conn()

    try:

        with c.cursor(
            cursor_factory=RealDictCursor
        ) as cur:

            cur.execute("""
                SELECT *
                FROM medicines
                ORDER BY name_fa
            """)

            medicines = cur.fetchall()

    finally:
        c.close()

    if not medicines:

        st.warning(
            "ابتدا حداقل یک دارو ثبت کنید."
        )

        return None

    names = [
        m["name_fa"]
        for m in medicines
    ]

    selected = st.selectbox(
        "دارو",
        names
    )

    return next(
        m for m in medicines
        if m["name_fa"] == selected
    )


# =========================================================
# ورود دارو
# =========================================================

def stock_entry():

    st.title("📥 ورود دارو")

    medicine = choose_medicine()

    if medicine is None:
        return

    st.info(
        f"موجودی فعلی: "
        f"{medicine['stock']} "
        f"{medicine['unit']}"
    )

    amount = st.number_input(
        "مقدار ورود",
        min_value=0.01,
        value=1.0
    )

    if st.button(
        "ثبت ورود",
        use_container_width=True
    ):

        c = conn()

        try:

            with c.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                # قفل ردیف تا دو کاربر همزمان
                # موجودی را اشتباه تغییر ندهند
                cur.execute("""
                    SELECT *
                    FROM medicines
                    WHERE id = %s
                    FOR UPDATE
                """, (medicine["id"],))

                locked = cur.fetchone()

                if locked is None:

                    st.error(
                        "دارو پیدا نشد."
                    )

                    c.rollback()
                    return

                new_stock = (
                    float(locked["stock"])
                    + amount
                )

                t = now()

                cur.execute("""
                    UPDATE medicines
                    SET stock = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    new_stock,
                    t,
                    locked["id"]
                ))

                cur.execute("""
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    locked["id"],
                    locked["name_fa"],
                    amount,
                    locked["unit"],
                    st.session_state.username,
                    t,
                    "synced"
                ))

            c.commit()

            st.success(
                "ورود دارو ثبت شد."
            )

        except Exception as e:

            c.rollback()

            st.error(
                f"خطا در ثبت ورود دارو: {e}"
            )

        finally:
            c.close()


# =========================================================
# مصرف دارو
# =========================================================

def usage():

    st.title("📤 مصرف دارو")

    medicine = choose_medicine()

    if medicine is None:
        return

    st.info(
        f"موجودی فعلی: "
        f"{medicine['stock']} "
        f"{medicine['unit']}"
    )

    amount = st.number_input(
        "مقدار مصرف",
        min_value=0.01,
        value=1.0
    )

    if st.button(
        "ثبت مصرف",
        use_container_width=True
    ):

        c = conn()

        try:

            with c.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                cur.execute("""
                    SELECT *
                    FROM medicines
                    WHERE id = %s
                    FOR UPDATE
                """, (medicine["id"],))

                locked = cur.fetchone()

                if locked is None:

                    st.error(
                        "دارو پیدا نشد."
                    )

                    c.rollback()
                    return

                current_stock = float(
                    locked["stock"]
                )

                if amount > current_stock:

                    st.error(
                        "موجودی کافی نیست."
                    )

                    c.rollback()
                    return

                new_stock = (
                    current_stock
                    - amount
                )

                t = now()

                cur.execute("""
                    UPDATE medicines
                    SET stock = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    new_stock,
                    t,
                    locked["id"]
                ))

                cur.execute("""
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    locked["id"],
                    locked["name_fa"],
                    amount,
                    locked["unit"],
                    st.session_state.username,
                    t,
                    "synced"
                ))

            c.commit()

            st.success(
                "مصرف دارو ثبت شد."
            )

        except Exception as e:

            c.rollback()

            st.error(
                f"خطا در ثبت مصرف: {e}"
            )

        finally:
            c.close()


# =========================================================
# اصلاح موجودی
# =========================================================

def correction():

    st.title("🔧 اصلاح موجودی")

    medicine = choose_medicine()

    if medicine is None:
        return

    new_stock = st.number_input(
        "موجودی صحیح",
        min_value=0.0,
        value=float(medicine["stock"])
    )

    if st.button(
        "ثبت اصلاح",
        use_container_width=True
    ):

        c = conn()

        try:

            with c.cursor(
                cursor_factory=RealDictCursor
            ) as cur:

                cur.execute("""
                    SELECT *
                    FROM medicines
                    WHERE id = %s
                    FOR UPDATE
                """, (medicine["id"],))

                locked = cur.fetchone()

                if locked is None:

                    st.error(
                        "دارو پیدا نشد."
                    )

                    c.rollback()
                    return

                old_stock = float(
                    locked["stock"]
                )

                difference = (
                    new_stock
                    - old_stock
                )

                t = now()

                cur.execute("""
                    UPDATE medicines
                    SET stock = %s,
                        updated_at = %s
                    WHERE id = %s
                """, (
                    new_stock,
                    t,
                    locked["id"]
                ))

                cur.execute("""
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    locked["id"],
                    locked["name_fa"],
                    old_stock,
                    new_stock,
                    difference,
                    st.session_state.username,
                    t,
                    "synced"
                ))

            c.commit()

            st.success(
                "اصلاح موجودی ثبت شد."
            )

        except Exception as e:

            c.rollback()

            st.error(
                f"خطا در اصلاح موجودی: {e}"
            )

        finally:
            c.close()


# =========================================================
# تاریخچه
# =========================================================

def history(table):

    if table == "usage_history":

        st.title(
            "📜 تاریخچه مصرف"
        )

    else:

        st.title(
            "📜 تاریخچه ورود"
        )

    if table == "usage_history":

        df = fetch_dataframe("""
            SELECT
                medicine_name AS "دارو",
                amount AS "مقدار",
                unit AS "واحد",
                username AS "کاربر",
                created_at AS "تاریخ و ساعت",
                sync_status AS "وضعیت"
            FROM usage_history
            ORDER BY id DESC
        """)

    elif table == "stock_entries":

        df = fetch_dataframe("""
            SELECT
                medicine_name AS "دارو",
                amount AS "مقدار",
                unit AS "واحد",
                username AS "کاربر",
                created_at AS "تاریخ و ساعت",
                sync_status AS "وضعیت"
            FROM stock_entries
            ORDER BY id DESC
        """)

    else:

        st.error(
            "جدول نامعتبر است."
        )

        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# گزارش روزانه
# =========================================================

def daily_report():

    st.title("📅 گزارش روزانه")

    selected_date = st.date_input(
        "تاریخ",
        date.today()
    )

    df = fetch_dataframe("""
        SELECT
            medicine_name AS "دارو",
            SUM(amount) AS "مقدار"
        FROM usage_history
        WHERE created_at::date = %s
        GROUP BY medicine_id, medicine_name
        ORDER BY "مقدار" DESC
    """, (selected_date,))

    if df.empty:

        st.info(
            "مصرفی برای این روز ثبت نشده است."
        )

        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        df.set_index("دارو")["مقدار"]
    )


# =========================================================
# ورود Excel
# =========================================================

def import_excel():

    st.title("📥 ورود داروها از Excel")

    template = pd.DataFrame(
        columns=[
            "نام دارو (فارسی)",
            "نام دارو (لاتین)",
            "موجودی",
            "واحد",
            "حداقل موجودی"
        ]
    )

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        template.to_excel(
            writer,
            index=False
        )

    st.download_button(
        "📄 دانلود قالب Excel",
        buffer.getvalue(),
        "قالب_داروها.xlsx",
        use_container_width=True
    )

    uploaded = st.file_uploader(
        "فایل Excel را انتخاب کنید",
        type=["xlsx"]
    )

    if not uploaded:
        return

    try:

        df = pd.read_excel(
            uploaded
        )

        required = list(
            template.columns
        )

        missing = [
            x
            for x in required
            if x not in df.columns
        ]

        if missing:

            st.error(
                "ستون‌های لازم وجود ندارند: "
                + ", ".join(missing)
            )

            return

        st.dataframe(
            df.head(20),
            use_container_width=True,
            hide_index=True
        )

        if st.button(
            "📥 وارد کردن اطلاعات",
            use_container_width=True
        ):

            c = conn()

            added = 0
            skipped = 0

            try:

                with c.cursor(
                    cursor_factory=RealDictCursor
                ) as cur:

                    for _, row in df.iterrows():

                        name_fa = str(
                            row["نام دارو (فارسی)"]
                        ).strip()

                        if (
                            not name_fa
                            or name_fa.lower() == "nan"
                        ):
                            continue

                        cur.execute("""
                            SELECT id
                            FROM medicines
                            WHERE name_fa = %s
                        """, (name_fa,))

                        exists = cur.fetchone()

                        if exists:

                            skipped += 1
                            continue

                        stock = pd.to_numeric(
                            row["موجودی"],
                            errors="coerce"
                        )

                        min_stock = pd.to_numeric(
                            row["حداقل موجودی"],
                            errors="coerce"
                        )

                        if pd.isna(stock):
                            stock = 0

                        if pd.isna(min_stock):
                            min_stock = 0

                        unit = str(
                            row["واحد"]
                        ).strip()

                        if (
                            not unit
                            or unit.lower() == "nan"
                        ):
                            unit = "عدد"

                        name_en = str(
                            row["نام دارو (لاتین)"]
                        ).strip()

                        if name_en.lower() == "nan":
                            name_en = ""

                        t = now()

                        cur.execute("""
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
                            VALUES
                            (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            name_fa,
                            name_en,
                            float(stock),
                            unit,
                            float(min_stock),
                            t,
                            t
                        ))

                        added += 1

                c.commit()

                st.success(
                    f"{added} دارو وارد شد."
                )

                if skipped:

                    st.warning(
                        f"{skipped} دارو تکراری بود."
                    )

            except Exception as e:

                c.rollback()

                st.error(
                    f"خطا در وارد کردن اطلاعات: {e}"
                )

            finally:
                c.close()

    except Exception as e:

        st.error(
            f"خطا در خواندن فایل: {e}"
        )


# =========================================================
# حذف دارو
# =========================================================

def delete_medicine():

    st.title("🗑️ حذف دارو")

    if st.session_state.role != "مدیر":

        st.error(
            "فقط مدیر اجازه حذف دارد."
        )

        return

    medicine = choose_medicine()

    if medicine is None:
        return

    confirm = st.checkbox(
        "حذف این دارو را تأیید می‌کنم."
    )

    if st.button(
        "🗑️ حذف",
        use_container_width=True
    ):

        if not confirm:

            st.warning(
                "ابتدا حذف را تأیید کنید."
            )

            return

        c = conn()

        try:

            with c.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM medicines
                    WHERE id = %s
                    """,
                    (medicine["id"],)
                )

            c.commit()

            st.success(
                "دارو حذف شد."
            )

        except Exception as e:

            c.rollback()

            st.error(
                f"خطا در حذف دارو: {e}"
            )

        finally:
            c.close()


# =========================================================
# مدیریت کاربران
# =========================================================

def users():

    st.title("👥 مدیریت کاربران")

    if st.session_state.role != "مدیر":

        st.error(
            "فقط مدیر اجازه مدیریت کاربران را دارد."
        )

        return

    with st.form("new_user"):

        username = st.text_input(
            "نام کاربری"
        )

        password = st.text_input(
            "رمز عبور",
            type="password"
        )

        role = st.selectbox(
            "نقش",
            ["کاربر", "مدیر"]
        )

        submitted = st.form_submit_button(
            "ایجاد کاربر",
            use_container_width=True
        )

    if submitted:

        if (
            not username.strip()
            or not password
        ):

            st.error(
                "نام کاربری و رمز عبور را وارد کنید."
            )

        else:

            c = conn()

            try:

                with c.cursor() as cur:

                    cur.execute("""
                        INSERT INTO users
                        (
                            username,
                            password,
                            role,
                            active,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        username.strip(),
                        pwd(password),
                        role,
                        True,
                        now()
                    ))

                c.commit()

                st.success(
                    "کاربر ایجاد شد."
                )

            except psycopg2.errors.UniqueViolation:

                c.rollback()

                st.error(
                    "این نام کاربری قبلاً وجود دارد."
                )

            except Exception as e:

                c.rollback()

                st.error(
                    f"خطا در ایجاد کاربر: {e}"
                )

            finally:
                c.close()

    df = fetch_dataframe("""
        SELECT
            id AS "کد",
            username AS "نام کاربری",
            role AS "نقش",
            active AS "فعال",
            created_at AS "تاریخ ایجاد"
        FROM users
        ORDER BY id
    """)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# خروجی Excel
# =========================================================

def export_excel():

    st.title("📤 خروجی Excel")

    inventory = fetch_dataframe("""
        SELECT *
        FROM medicines
        ORDER BY id
    """)

    usage_data = fetch_dataframe("""
        SELECT *
        FROM usage_history
        ORDER BY id
    """)

    stock_data = fetch_dataframe("""
        SELECT *
        FROM stock_entries
        ORDER BY id
    """)

    corrections = fetch_dataframe("""
        SELECT *
        FROM stock_corrections
        ORDER BY id
    """)

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        inventory.to_excel(
            writer,
            index=False,
            sheet_name="موجودی"
        )

        usage_data.to_excel(
            writer,
            index=False,
            sheet_name="تاریخچه مصرف"
        )

        stock_data.to_excel(
            writer,
            index=False,
            sheet_name="تاریخچه ورود"
        )

        corrections.to_excel(
            writer,
            index=False,
            sheet_name="اصلاحات"
        )

    st.download_button(
        "📥 دانلود Excel",
        buffer.getvalue(),
        f"گزارش_{date.today().isoformat()}.xlsx",
        use_container_width=True
    )


# =========================================================
# برنامه اصلی
# =========================================================

def main():

    # اطمینان از وجود مدیر
    try:

        init_db()

    except Exception as e:

        st.error(
            "اتصال به دیتابیس مرکزی برقرار نشد."
        )

        st.code(
            str(e)
        )

        return

    if "logged" not in st.session_state:
        st.session_state.logged = False

    if not st.session_state.logged:

        login()

        return

    page = sidebar()

    actions = {

        "داشبورد":
            dashboard,

        "موجودی داروها":
            inventory,

        "ثبت داروی جدید":
            add_medicine,

        "ورود دارو":
            stock_entry,

        "مصرف دارو":
            usage,

        "اصلاح موجودی":
            correction,

        "تاریخچه مصرف":
            lambda:
                history("usage_history"),

        "تاریخچه ورود":
            lambda:
                history("stock_entries"),

        "گزارش روزانه":
            daily_report,

        "ورود داروها از Excel":
            import_excel,

        "خروجی Excel":
            export_excel,

        "حذف دارو":
            delete_medicine,

        "مدیریت کاربران":
            users
    }

    actions[page]()


if __name__ == "__main__":
    main()