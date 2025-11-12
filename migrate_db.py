"""Create/update database tables"""
from app.database import Base, engine

# Create all tables
Base.metadata.create_all(bind=engine)
print("✓ Database tables created/updated successfully!")

