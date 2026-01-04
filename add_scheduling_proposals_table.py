"""
Add scheduling_proposals table for schedule negotiation flow
"""
import os
import sys
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import DATABASE_URL

def add_scheduling_proposals_table():
    """Create scheduling_proposals table for provider-client scheduling negotiation"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Creating scheduling_proposals table...")
        
        try:
            # Create scheduling_proposals table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS scheduling_proposals (
                    id SERIAL PRIMARY KEY,
                    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    
                    -- Proposal details
                    status VARCHAR(50) DEFAULT 'pending',  -- pending, accepted, rejected, countered, expired
                    proposal_round INTEGER DEFAULT 1,  -- Max 3 rounds
                    proposed_by VARCHAR(50) NOT NULL,  -- provider or client
                    
                    -- Time slots (JSON array of proposed times)
                    time_slots JSONB NOT NULL,  -- [{"date": "2026-01-08", "start_time": "19:00", "end_time": "21:00", "recommended": true}]
                    
                    -- Selected slot (when accepted)
                    selected_slot_date DATE,
                    selected_slot_start_time VARCHAR(10),
                    selected_slot_end_time VARCHAR(10),
                    
                    -- Client preferences (for counter-proposals)
                    preferred_days VARCHAR(50),  -- "M,T,W,Th,F" comma-separated
                    preferred_time_window VARCHAR(50),  -- "18:00-20:00"
                    client_notes TEXT,
                    
                    -- Timestamps
                    expires_at TIMESTAMP,
                    responded_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """))
            
            # Create indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scheduling_proposals_contract 
                ON scheduling_proposals(contract_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scheduling_proposals_client 
                ON scheduling_proposals(client_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_scheduling_proposals_status 
                ON scheduling_proposals(status);
            """))
            
            conn.commit()
            print("✅ Successfully created scheduling_proposals table")
            
        except Exception as e:
            print(f"❌ Error creating scheduling_proposals table: {e}")
            conn.rollback()
            raise
    
    print("Migration complete!")

if __name__ == "__main__":
    add_scheduling_proposals_table()
