from database import Base, engine
from models import Patient, Screening

print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Tables created successfully!")