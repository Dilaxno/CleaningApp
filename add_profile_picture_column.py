"""
Migration script to add profile_picture_url column to users table.
Run this once to update the database schema.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")


def migrate():
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    """
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS profile_picture_url VARCHAR(500)
            """
                )
            )
            print("✅ Added column: profile_picture_url")
        except Exception as e:
            print(f"⚠️ Column might already exist: {e}")

        conn.commit()
        print("✅ Migration completed!")


if __name__ == "__main__":
    migrate()
