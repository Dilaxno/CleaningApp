"""
Migration script to add the schedules table to the database.
Run this script once to create the schedules table.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models import Schedule

def migrate():
    print("Creating schedules table...")
    Base.metadata.create_all(bind=engine, tables=[Schedule.__table__])
    print("✅ Schedules table created successfully!")

if __name__ == "__main__":
    migrate()
