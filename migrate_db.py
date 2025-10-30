"""Create/update database tables"""
from app.database import Base, engine
from app.models import SavedSearch  # Import to ensure it's registered

# Create all tables
Base.metadata.create_all(bind=engine)
print("✓ Database tables created/updated successfully!")
print("✓ SavedSearch table is now available")
