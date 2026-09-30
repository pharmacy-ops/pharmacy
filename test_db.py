import psycopg2

HOST = "aws-0-ap-southeast-2.pooler.supabase.com"
PORT = 5432
DATABASE = "postgres"
USER = "postgres.xilwmvdzliczcmjgbabr"

PASSWORD = input("Database password: ")

try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        database=DATABASE,
        user=USER,
        password=PASSWORD
    )

    print("\n✅ اتصال به دیتابیس مرکزی موفق بود!")
    conn.close()

except Exception as e:
    print("\n❌ اتصال برقرار نشد.")
    print("خطا:", e)