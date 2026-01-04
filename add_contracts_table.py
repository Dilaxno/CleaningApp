"""
Migration script to add the contracts table to the database.
Run this script once to create the contracts table.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models import Contract

def migrate():
    print("Creating contracts table...")
    Base.metadata.create_all(bind=engine, tables=[Contract.__table__])
    print("✅ Contracts table created successfully!")

if __name__ == "__main__":
    migrate()
