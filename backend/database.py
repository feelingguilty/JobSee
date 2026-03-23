from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
from pathlib import Path

# Get the absolute path to the directory of the current script
script_dir = Path(__file__).parent.resolve()
db_path = script_dir / "jobsee.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String, nullable=True)
    url = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Qualification scoring
    match_score = Column(Integer, nullable=True)
    match_reason = Column(Text, nullable=True)

    source = Column(String, nullable=True) # e.g. "LinkedIn", "Naukri", "DuckDuckGo"
    status = Column(String, default="NEW") # "NEW", "APPLIED", "IGNORED"
    discovery_date = Column(DateTime, default=datetime.utcnow)
    cover_letter = Column(Text, nullable=True)
    tailored_resume_path = Column(String, nullable=True)

# Create all tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
