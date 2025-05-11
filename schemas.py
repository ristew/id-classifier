from pydantic import BaseModel, ConfigDict
from typing import Dict, Optional, List
from datetime import datetime

# Base schema for features, can be extended if specific feature keys are known/enforced
class FeaturesModel(BaseModel):
    model_config = ConfigDict(extra='allow') # Allows arbitrary key-value pairs

class DocumentRecordBase(BaseModel):
    original_filename: str
    document_type: str
    features: Dict[str, Optional[str]] # Allows any string keys, values are string or null

class DocumentRecordCreate(DocumentRecordBase):
    image_base64: str # Required when creating a new record

class DocumentRecordUpdate(BaseModel): # All fields optional for update
    document_type: Optional[str] = None
    features: Optional[Dict[str, Optional[str]]] = None
    # original_filename and image_base64 are not typically updated directly here.
    # Re-uploading an image would likely create a new record or be a more complex operation.

class DocumentRecordResponse(DocumentRecordBase):
    id: int
    image_base64: str # Return image for frontend history display
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 for ORM mode (formerly orm_mode)
