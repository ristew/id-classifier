import os
import base64
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from dotenv import load_dotenv
from PIL import Image
import io
import logging
from typing import List
from sqlalchemy.orm import Session
import crud
import models
import schemas
from database import SessionLocal, engine, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
models.Base.metadata.create_all(bind=engine)

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:8000")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "ID Classifier App")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = "google/gemini-2.5-flash-preview"

NOT_FOUND_PLACEHOLDER = "VALUE_NOT_FOUND"

app = FastAPI(
    title="ID Document Classifier and Extractor",
    description="Upload an image to classify, extract features, and save edits.",
    version="1.2.0" # Version bump
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }
)

VALID_DOCUMENT_TYPES = ["passport", "drivers_license", "ead_card"]
FEATURE_EXTRACTION_CONFIG = {
    "passport": {
        "fields": ["full_name", "date_of_birth", "country", "issue_date", "expiration_date"],
        "display_names": {
            "full_name": "full name (given name then surname)",
            "date_of_birth": "date of birth (in YYYY-MM-DD format)",
            "country": "issuing country (short code)",
            "issue_date": "issue date (in YYYY-MM-DD format)",
            "expiration_date": "expiration date (in YYYY-MM-DD format)"
        }
    },
    "drivers_license": {
        "fields": ["license_number", "date_of_birth", "issue_date", "expiration_date", "first_name", "last_name"],
        "display_names": {
            "license_number": "license number",
            "date_of_birth": "date of birth (in YYYY-MM-DD format)",
            "issue_date": "issue date (in YYYY-MM-DD format)",
            "expiration_date": "expiration date (in YYYY-MM-DD format)",
            "first_name": "first name (on own line, without middle initial)",
            "last_name": "last name (on own line)"
        }
    },
    "ead_card": {
        "fields": ["card_number", "category", "card_expires_date", "last_name", "first_name"],
        "display_names": {
            "card_number": "card number (under Card#)",
            "category": "category (e.g., C09)",
            "card_expires_date": "card expiration date (in YYYY-MM-DD format)",
            "last_name": "last name",
            "first_name": "first name (without middle initial)"
        }
    }
}
async def get_image_content(image_file: UploadFile):
    contents = await image_file.read()
    try:
        Image.open(io.BytesIO(contents)).verify()
    except Exception as e:
        logger.error(f"Invalid image file: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    if image_file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        logger.warning(f"Unsupported image type: {image_file.content_type}. Proceeding...")

    base64_image = base64.b64encode(contents).decode("utf-8")
    return f"data:{image_file.content_type};base64,{base64_image}"


def get_single_feature_prompt(document_type_display: str, feature_name_key: str, feature_display_name: str) -> str:
    return (
        f"The image provided is a {document_type_display}. "
        f"What is the {feature_display_name}? "
        f"Respond with ONLY the value for {feature_display_name}. "
        f"Do not include any explanatory text or labels in your response. "
        f"If the {feature_display_name} is not visible, unreadable, or cannot be found, "
        f"respond with the exact string: {NOT_FOUND_PLACEHOLDER}"
    )

async def call_gemini_vision_api(prompt: str, base64_image_data_url: str):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": base64_image_data_url}}
            ]
        }
    ]
    completion_params = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": 250,
        "temperature": 0.1,
    }
    logger.info(f"Sending request to Gemini. Prompt: '{prompt[:150]}...'")
    try:
        completion = await client.chat.completions.create(**completion_params)
        response_content = completion.choices[0].message.content.strip()
        logger.info(f"Received response from Gemini: '{response_content}'")
        return response_content
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=503, detail=f"Error communicating with AI model: {str(e)}")

@app.post("/classify", response_model=schemas.DocumentRecordResponse)
async def classify_and_extract_and_save(
    request: Request,
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Received request for /classify from {request.client.host}")

    if not OPENROUTER_API_KEY:
        logger.error("OpenRouter API key not configured.")
        raise HTTPException(status_code=500, detail="Server configuration error: API key missing.")

    original_filename = image.filename if image.filename else "uploaded_image.png" # Ensure a default
    base64_image_data_url = await get_image_content(image)

    # --- Step 1: Classify Document Type ---
    classification_prompt = (
        "Analyze the provided image. Is it a passport, a driver's license, or an EAD card (Employment Authorization Document)? "
        "Respond with ONLY one of the following lowercase snake_case strings: 'passport', 'drivers_license', or 'ead_card'. "
        "Do not include any other text, explanation, or punctuation."
    )
    raw_doc_type = await call_gemini_vision_api(classification_prompt, base64_image_data_url)
    document_type = raw_doc_type.strip().lower().replace(" ", "_")

    if document_type not in VALID_DOCUMENT_TYPES:
        logger.warning(f"Classification failed or returned unexpected type: '{document_type}' from raw: '{raw_doc_type}'")
        # Try to save with an 'unknown' type or a default? Or fail? For now, fail.
        raise HTTPException(
            status_code=422,
            detail=f"Could not classify or unsupported document type: '{document_type}'. Expected one of {VALID_DOCUMENT_TYPES}."
        )
    logger.info(f"Classified document as: {document_type}")

    # --- Step 2: Extract Features Individually ---
    config = FEATURE_EXTRACTION_CONFIG[document_type]
    fields_to_extract = config["fields"]
    display_names_map = config["display_names"]
    document_type_display_for_prompt = document_type.replace("_", " ")
    extracted_features = {}

    for field_key in fields_to_extract:
        feature_display_name = display_names_map.get(field_key, field_key.replace("_", " "))
        extraction_prompt = get_single_feature_prompt(
            document_type_display_for_prompt,
            field_key,
            feature_display_name
        )
        raw_feature_value = await call_gemini_vision_api(extraction_prompt, base64_image_data_url)
        cleaned_value = raw_feature_value.strip('"').strip("'").strip()

        if cleaned_value == NOT_FOUND_PLACEHOLDER or not cleaned_value:
            extracted_features[field_key] = None
        else:
            extracted_features[field_key] = cleaned_value
    logger.info(f"Successfully extracted features for {document_type}")

    # --- Step 3: Save to Database ---
    document_to_create = schemas.DocumentRecordCreate(
        original_filename=original_filename,
        image_base64=base64_image_data_url, # This includes the data:mime;base64 prefix
        document_type=document_type,
        features=extracted_features
    )
    db_document_record = crud.create_document_record(db=db, record=document_to_create)
    logger.info(f"Saved document record with ID: {db_document_record.id}")
    
    return db_document_record # response_model handles conversion to DocumentRecordResponse


@app.put("/documents/{document_id}", response_model=schemas.DocumentRecordResponse)
async def update_document_features(
    document_id: int,
    document_update: schemas.DocumentRecordUpdate, # This will contain 'features' and/or 'document_type'
    db: Session = Depends(get_db)
):
    logger.info(f"Received request to update document ID: {document_id} with data: {document_update.model_dump()}")
    db_document_record = crud.get_document_record(db, record_id=document_id)
    if not db_document_record:
        logger.warning(f"Document ID {document_id} not found for update.")
        raise HTTPException(status_code=404, detail="Document not found")

    updated_record = crud.update_document_record(db=db, record_id=document_id, record_update=document_update)
    if not updated_record: # Should ideally not happen if get_document_record found it
        logger.error(f"Failed to update document ID {document_id} despite it being found.")
        raise HTTPException(status_code=500, detail="Error updating document")
    
    logger.info(f"Successfully updated document ID: {document_id}")
    return updated_record


@app.get("/documents/", response_model=List[schemas.DocumentRecordResponse])
async def read_all_documents(
    skip: int = 0,
    limit: int = 10, # Default to fetching 10 most recent
    db: Session = Depends(get_db)
):
    logger.info(f"Received request to list documents. Skip: {skip}, Limit: {limit}")
    documents = crud.get_document_records(db, skip=skip, limit=limit)
    return documents


@app.get("/documents/{document_id}", response_model=schemas.DocumentRecordResponse)
async def read_single_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    logger.info(f"Received request to fetch document ID: {document_id}")
    db_document = crud.get_document_record(db, record_id=document_id)
    if db_document is None:
        logger.warning(f"Document ID {document_id} not found.")
        raise HTTPException(status_code=404, detail="Document not found")
    return db_document


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down. Closing OpenAI client.")
    await client.close()

if __name__ == "__main__":
    import uvicorn
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY environment variable not set.")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Use "main:app" for uvicorn
