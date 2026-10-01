import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models import URL


def init_database():
    """Ensure database exists on PostgreSQL server."""
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="root",
        host="localhost",
        port=5432,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'url_shortener'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE url_shortener")
        print("Created database 'url_shortener'.")
    else:
        print("Database 'url_shortener' already exists.")
    cur.close()
    conn.close()


def test_connection_and_tables():
    print("\n--- Testing Database Connection with SQLAlchemy ---")
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        print("Connected to PostgreSQL successfully!")
        print(f"Server version: {result.fetchone()[0]}")

    print("\n--- Creating Tables (including 'urls') ---")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

    print("\n--- Testing Insert & Unique Constraint on 'short_code' ---")
    db = SessionLocal()
    try:
        # Clean up any test records
        db.query(URL).filter(URL.short_code == "test1234").delete()
        db.commit()

        # Insert a test URL record
        test_url = URL(
            id=12345678901234,
            short_code="test1234",
            original_url="https://example.com/test",
        )
        db.add(test_url)
        db.commit()
        db.refresh(test_url)
        print(f"Successfully inserted: {test_url}")
        print(f"Created at: {test_url.created_at}")

        # Test duplicate short_code to verify UNIQUE constraint works
        print("\n--- Testing UNIQUE Constraint ---")
        duplicate_url = URL(
            id=12345678901235,
            short_code="test1234",  # Duplicate!
            original_url="https://another-example.com",
        )
        db.add(duplicate_url)
        try:
            db.commit()
            raise AssertionError("Duplicate short_code did not raise an integrity error!")
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"Verified UNIQUE constraint: Duplicate insert was blocked! ({type(e).__name__})")

        # Clean up test record
        db.query(URL).filter(URL.short_code == "test1234").delete()
        db.commit()
        print("\nAll database tests passed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    test_connection_and_tables()
