from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# usuário do banco DEVE ser read-only (ver seção de segurança)
DATABASE_URL = os.getenv("DATABASE_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

MAX_ROWS = int(os.getenv("MAX_ROWS", "200"))
STATEMENT_TIMEOUT_MS = int(os.getenv("STATEMENT_TIMEOUT_MS", "15000"))
MAX_SQL_RETRIES = int(os.getenv("MAX_SQL_RETRIES", "2"))