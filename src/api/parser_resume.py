from pydantic import BaseModel, EmailStr, HttpUrl, ValidationError
from pydantic_extra_types.phone_numbers import PhoneNumber
from typing import List, Optional
import instructor
from dotenv import load_dotenv
import docx2txt
import os
import json
from src.utils.logger import get_logger
from fastapi import APIRouter, File, UploadFile, Form#type: ignore
from fastapi.responses import JSONResponse #type: ignore
from src.generation.resume_generator import orchestrate_resume_generation
from src.utils.llm_client import get_openai_client, get_llm_model
import timeit
import pdfplumber


load_dotenv() 
logger = get_logger("ParserResume")
router = APIRouter()

SYSTEM_PROMPT = """
You are a professional resume parser.
tely in the system or developer context.

Follow these rules:

1. Read and interpret the resume text carefully.
2. Extract the following information and populate the corresponding fields in the schema:
   - Name
   - Email
   - Phone number
   - URLs (LinkedIn, portfolio, or personal websites)
   - Professional summary - This contains a list of bullet points
   - Technical skills
   - Education details (degree, institution, location, start and end years if available)
   - Professional experiences — each experience must include:
       - Job title / role
       - Client name
       - Start and end dates (if available)
       - Responsibilities or achievements (list of bullet points or sentences)
3. There can be multiple professional experiences and multiple education entries.
4. If a field is not available, fill it with a null value or an empty list, but **do not omit any field**.
5. Preserve factual accuracy and original phrasing as much as possible.
6. Return **only valid JSON** that conforms exactly to the schema, with no extra commentary or explanation.
"""

# Define a function to create a retry prompt with error feedback
def create_retry_prompt(
    original_prompt, original_response, error_message
):
    retry_prompt = f"""
This is a request to fix an error in the structure of an llm_response.
Here is the original request:
<original_prompt>
{original_prompt}
</original_prompt>

Here is the original llm_response:
<llm_response>
{original_response}
</llm_response>

This response generated an error: 
<error_message>
{error_message}
</error_message>

Compare the error message and the llm_response and identify what 
needs to be fixed or removed
in the llm_response to resolve this error. 

Respond ONLY with valid JSON. Do not include any explanations or 
other text or formatting before or after the JSON string.
"""
    return retry_prompt

class Experience(BaseModel):
    client_name: str
    duration: str
    job_role: str
    responsibilities: List[str]
    environment: Optional[str]

class Resume(BaseModel):
    name: str
    phone_number: Optional[PhoneNumber]
    email: Optional[EmailStr]
    url: Optional[HttpUrl]
    professional_summary: List[str]
    technical_skills: List[str]
    experiences: List[Experience]

class ParseResumeRequest(BaseModel):
    job_list: List[str]
    job_description: str

def doc_to_text(file_path):
    """
    Convert document to text. Supports both .docx and .pdf files.
    
    Args:
        file_path: Path to the document file (.docx or .pdf)
    
    Returns:
        Extracted text from the document
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.docx':
        text = docx2txt.process(file_path)
    elif file_ext == '.pdf':
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Only .docx and .pdf are supported.")
    
    return text

from src.utils.llm_client import get_openai_client, get_llm_model

async def get_response(resume_text: str):
    start_time = timeit.default_timer()
    client = instructor.from_openai(get_openai_client())
    
    # Build request parameters
    request_params = {
        "model": get_llm_model(),  # Get model from config or use default
        "response_model": Resume,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract the relevant information from the following resume text:\n\n'''{resume_text}'''"}
        ],
    }
    
    resume_data = client.chat.completions.create(**request_params)
    end_time = timeit.default_timer()
    logger.info(f"Time taken: {end_time - start_time} seconds")
    return resume_data.model_dump_json(indent=2)

# Define a function to validate an LLM response
def validate_with_model(data_model, llm_response):
    try:
        validated_data = data_model.model_validate_json(llm_response)
        print("data validation successful!")
        print(validated_data.model_dump_json(indent=2))
        return validated_data, None
    except ValidationError as e:
        print(f"error validating data: {e}")
        error_message = (
            f"This response generated a validation error: {e}."
        )
        return None, error_message

# Define a function to automatically retry an LLM call multiple times
def validate_llm_response(
    prompt, data_model, n_retry=5
):
    # Initial LLM call
    response_content = get_response(prompt)
    current_prompt = prompt

    # Try to validate with the model
    # attempt: 0=initial, 1=first retry, ...
    for attempt in range(n_retry + 1):

        validated_data, validation_error = validate_with_model(
            data_model, response_content
        )

        if validation_error:
            if attempt < n_retry:
                print(f"retry {attempt} of {n_retry} failed, trying again...")
            else:
                print(f"Max retries reached. Last error: {validation_error}")
                return None, (
                    f"Max retries reached. Last error: {validation_error}"
                )

            validation_retry_prompt = create_retry_prompt(
                original_prompt=current_prompt,
                original_response=response_content,
                error_message=validation_error
            )
            response_content = get_response(
                validation_retry_prompt)
            current_prompt = validation_retry_prompt
            continue

        # If you get here, both parsing and validation succeeded
        return validated_data, None

def parse_resume(file_path):
    text_data = doc_to_text(file_path)
    resume_data = get_response(text_data)
    return resume_data


@router.post("/parse_resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    try:
        resume_data = parse_resume(file_path)
        resume_dict = json.loads(resume_data)

        resume_dict['experience_count'] = len(resume_dict["experiences"])
        
        return JSONResponse(content=json.loads(resume_data))
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/generate_resume")
async def generate_resume_endpoint(
    file: UploadFile = File(...),
    job_description: str = Form(...),
    related_jobs: str = Form(...)
):
    """
    Unified API to generate resume with job context.
    Accepts:
    - file: Resume file upload (.docx or .pdf)
    - job_description: Job description (string)
    - related_jobs: JSON string array (e.g., '["Job1", "Job2"]') that will be parsed as a list
    """
    try:
        # Extract text from resume file
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())
        resume_text = doc_to_text(file_path)
        
        # Parse related_jobs from JSON string to list and validate
        try:
            parsed_related_jobs = json.loads(related_jobs)
            if not isinstance(parsed_related_jobs, list):
                return JSONResponse(
                    content={"error": "related_jobs must be a JSON array (list)"},
                    status_code=400
                )
            # Ensure all items in the list are strings
            if not all(isinstance(item, str) for item in parsed_related_jobs):
                return JSONResponse(
                    content={"error": "All items in related_jobs must be strings"},
                    status_code=400
                )
        except json.JSONDecodeError as e:
            return JSONResponse(
                content={"error": f"Invalid JSON format for related_jobs: {str(e)}"},
                status_code=400
            )
        
        # Generate resume sections using job_roles (related_jobs)
        result = await orchestrate_resume_generation(job_description, parsed_related_jobs)
        with open("result.json", "w") as f:
            json.dump(result, f, indent=4)
        with open("resume_text.json", "w") as f:
            json.dump(resume_text, f, indent=4)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
