from pydantic import BaseModel, EmailStr, HttpUrl, ValidationError, Field, field_validator
from typing import List, Optional
import instructor
from dotenv import load_dotenv
import docx2txt
import os
import json
from src.utils.logger import get_logger
from fastapi import APIRouter, File, UploadFile, Form#type: ignore
from fastapi.responses import JSONResponse #type: ignore
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
   - URLs
   - Professional summary - This contains a list of bullet points
   - Technical skills
   - Education details
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
    client_name: str = Field(
        ...,
        description="The company, client, or organization where the candidate worked for this role."
    )
    duration: str = Field(
        None,
        description="Employment period for this role."
    )
    job_role: str = Field(
        None,
        description="The specific job title held during this experience."
    )
    responsibilities: List[str] = Field(
        None,
        description="A list of detailed responsibilities, achievements, or tasks performed in this role."
    )
    environment: Optional[List[str]] = Field(
        ...,
        description="List of technologies, tools, frameworks, or platforms used in this role. Leave null if not provided."
    )


class Resume(BaseModel):
    name: str = Field(
        ...,
        description="The full name of the candidate exactly as written in the resume."
    )
    phone_number: Optional[str] = Field(
        None,
        description="The candidate's phone number. Provide it as a string in any readable format. Leave null if missing."
    )
    email: Optional[EmailStr] = Field(
        None,
        description="The candidate’s email address. Must be a valid email format or null if missing."
    )
    url: Optional[List[HttpUrl]] = Field(
        None,
        description="A list of URLs from the resume."
    )
    designation: str = Field(
        ...,
        description="The primary job title or role the resume represents (e.g., 'Senior Software Engineer')."
    )
    professional_summary: List[str] = Field(
        ...,
        description="A list of bullet points summarizing the candidate’s profile, strengths, or career overview."
    )
    technical_skills: List[str] = Field(
        ...,
        description="A list of technical skills, tools, technologies, programming languages, or platforms mentioned in the resume."
    )
    experiences: List[Experience] = Field(
        ...,
        description="A list of professional experiences the candidate has had, each represented as an Experience object."
    )
    education: Optional[List[str]] = Field(
        None,
        description="A list of educational qualifications in plain text from the resume, merge all the education details into a single list."
    )
    
    @field_validator('url', mode='before')
    @classmethod
    def add_scheme_to_urls(cls, v):
        """Add https:// to URLs that don't have a scheme."""
        if v is None:
            return v
        
        if isinstance(v, str):
            v = [v]
        
        if not isinstance(v, list):
            return v
        
        result = []
        for url in v:
            if isinstance(url, str):
                # Check if URL has a scheme (http://, https://, etc.)
                if not url.startswith(('http://', 'https://', 'ftp://', 'ftps://')):
                    # Add https:// prefix
                    url = f'https://{url}'
                result.append(url)
            else:
                # If it's already an HttpUrl object, keep it as is
                result.append(url)
        
        return result


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

async def get_response(resume_text: str):
    start_time = timeit.default_timer()
    client = instructor.from_openai(
        get_openai_client(),
        mode=instructor.Mode.JSON,
    )
    
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
async def validate_llm_response(
    prompt, data_model, n_retry=5
):
    # Initial LLM call
    response_content = await get_response(prompt)
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
            response_content = await get_response(
                validation_retry_prompt)
            current_prompt = validation_retry_prompt
            continue

        # If you get here, both parsing and validation succeeded
        return validated_data, None

async def parse_resume(file_path):
    text_data = doc_to_text(file_path)
    resume_data = await get_response(text_data)
    return resume_data


@router.post("/parse_resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    try:
        resume_data = await parse_resume(file_path)
        resume_dict = json.loads(resume_data)

        resume_dict['experience_count'] = len(resume_dict["experiences"])
        
        return JSONResponse(content=resume_dict)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
