import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_PORT     = int(os.getenv("DB_PORT", 3306))
    DB_USER     = os.getenv("DB_USER", "crida_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "crida_pass")
    DB_NAME     = os.getenv("DB_NAME", "CRID")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

    JWT_SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "fallback-secret-change-this")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))

    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "noreply@crida.pk")
