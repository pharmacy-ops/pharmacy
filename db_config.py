import os
import psycopg2
from dotenv import load_dotenv

# خواندن اطلاعات از فایل .env
load_dotenv()

DB_HOST = os.getenv(
    "DB_HOST",
    "aws-0-ap-southeast-2.pooler.supabase.com"
)

DB_PORT = os.getenv(
    "DB_PORT",
    "5432"
)

DB_NAME = os.getenv(
    "DB_NAME",
    "postgres"
)

DB_USER = os.getenv(
    "DB_USER",
    "postgres.xilwmvdzliczcmjgbabr"
)

DB_PASSWORD = os.getenv(
    "DB_PASSWORD",
    ""
)


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )