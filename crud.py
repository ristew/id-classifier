from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas

def get_document_record(db: Session, record_id: int) -> Optional[models.DocumentRecord]:
    return db.query(models.DocumentRecord).filter(models.DocumentRecord.id == record_id).first()

def get_document_records(db: Session, skip: int = 0, limit: int = 10) -> List[models.DocumentRecord]:
    return db.query(models.DocumentRecord).order_by(models.DocumentRecord.updated_at.desc()).offset(skip).limit(limit).all()

def create_document_record(db: Session, record: schemas.DocumentRecordCreate) -> models.DocumentRecord:
    db_record = models.DocumentRecord(
        original_filename=record.original_filename,
        image_base64=record.image_base64,
        document_type=record.document_type,
        features=record.features
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

def update_document_record(
    db: Session, record_id: int, record_update: schemas.DocumentRecordUpdate
) -> Optional[models.DocumentRecord]:
    db_record = get_document_record(db, record_id)
    if db_record:
        update_data = record_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_record, key, value)
        db.commit()
        db.refresh(db_record)
    return db_record
