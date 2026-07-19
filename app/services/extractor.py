import os
import base64
from fastapi import UploadFile, HTTPException
from openai import OpenAI
from app.schemas import ThaiIDExtraction, MedicalReceiptExtraction
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
# Initialize the OpenAI client natively
# It automatically reads OPENAI_API_KEY from your .env if loaded via python-dotenv
client = OpenAI()

def encode_file_to_base64(file_bytes: bytes) -> str:
    """Encodes raw file bytes into a base64 string for the Vision API."""
    return base64.b64encode(file_bytes).decode('utf-8')

async def extract_document_data(file: UploadFile, doc_type: str):
    """
    Reads an uploaded file, converts it to base64, and prompts a Vision LLM
    to pull structured JSON fields directly using native Pydantic validation.
    """
    # Read the file contents into memory
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file stream: {str(e)}")
    
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Convert binary file to visual format base64
    base64_image = encode_file_to_base64(file_bytes)
    
    # 1. Map endpoint selections to their targeted strict Pydantic schemas
    if doc_type == "thai_id":
        target_schema = ThaiIDExtraction
        system_instruction = (
            "You are a core security compliance agent for a Neobank. "
            "Analyze the image of the Thai National ID Card and precisely extract the requested fields. "
            "Convert dates carefully into YYYY-MM-DD format."
        )
    elif doc_type == "medical_receipt":
        target_schema = MedicalReceiptExtraction
        system_instruction = (
            "You are an automated insurance claims auditing agent. "
            "Extract the hospital details, dates, and every single itemized line-item from this receipt. "
            "Ensure the itemized costs match exactly what is listed on the page."
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported classification category mapping.")

    # 2. Invoke OpenAI's native Parsing Engine with a visual image payload
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini", # Highly efficient for structured vision tasks
            messages=[
                {
                    "requirement": "system",
                    "content": system_instruction
                },
                {
                    "requirement": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Extract all data from this document accurately according to the schema boundaries."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            response_format=target_schema, # The Pydantic model enforces structural safety
            temperature=0.0 # Force maximum determinism
        )
        
        # 3. Retrieve the validated, typed Pydantic object
        extracted_object = response.choices[0].message.parsed
        
        if response.choices[0].message.refusal:
            # Handle cases where the LLM flags the prompt as a safety violation
            raise HTTPException(status_code=422, detail=f"Extraction refused: {response.choices[0].message.refusal}")
            
        return extracted_object

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Visual Parsing Engine failure: {str(e)}")