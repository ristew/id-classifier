from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func # for server_default=func.now()
from database import Base

class DocumentRecord(Base):
    __tablename__ = "document_records"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String, index=True)
    image_base64 = Column(Text)  # Base64 can be very long
    document_type = Column(String, index=True)
    features = Column(JSON)      # Store the features dictionary as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<DocumentRecord(id={self.id}, name='{self.original_filename}', type='{self.document_type}')>"
