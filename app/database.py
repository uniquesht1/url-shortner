import os
from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database connection URL
# Format: postgresql://<username>:<password>@<host>:<port>/<database_name>
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root@localhost:5432/url_shortener",
)

# Normalize URLs from cloud providers like Neon/Supabase/Render (e.g. postgres:// -> postgresql+psycopg2://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# pool_pre_ping=True prevents connection drops on serverless/free cloud databases that pause on idle
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

# SessionLocal is a factory for creating new database sessions for queries/transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class that our ORM models (tables) inherit from
Base = declarative_base()


def get_db():
    """
    Dependency/helper to get a database session and ensure it is properly closed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
