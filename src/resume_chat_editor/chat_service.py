import os
import asyncio
import json
from typing import Optional
from src.resume_chat_editor.resume_decoder import download_resume_from_gcs, parse_resume, Resume
from src.generation.call_llm import llm_json
from src.generation.resume_writer import generate_and_upload_resume
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ResumeChatService:
    def __init__(self, retry_attempts: int = 3):
        self.retry_attempts = retry_attempts

    async def process_resume_edit(self, gcs_url: str, user_instruction: str) -> dict:
        """
        Process a resume edit request.
        1. Download resume from GCS.
        2. Parse .docx to JSON (Resume Pydantic model).
        3. Use LLM to edit the JSON based on user instructions.
        4. Validate and retry if necessary.
        5. Write back to .docx and upload to GCS.
        """
        temp_dir = "temp_resumes"
        os.makedirs(temp_dir, exist_ok=True)
        local_path = None
        
        try:
            # 1. Download
            logger.info(f"Downloading resume from {gcs_url}")
            local_path = download_resume_from_gcs(gcs_url, save_dir=temp_dir)
            
            # 2. Parse
            logger.info(f"Parsing resume at {local_path}")
            resume_obj = parse_resume(local_path)
            resume_json = resume_obj.model_dump_json()
            
            # 3. LLM Edit with Retry Loop
            system_prompt = (
                "You are an expert resume editor. You will be provided with a resume in JSON format "
                "and a set of instructions from the user on how to fix or rewrite specific parts of the resume. "
                "Your task is to realign and correct the resume JSON according to these instructions. "
                "Ensure the output strictly follows the Resume Pydantic model schema."
            )
            
            user_prompt = (
                f"Original Resume JSON:\n{resume_json}\n\n"
                f"User Instructions:\n{user_instruction}\n\n"
                "Please return the updated resume JSON."
            )
            
            updated_resume = None
            for attempt in range(self.retry_attempts):
                try:
                    logger.info(f"LLM call attempt {attempt + 1}/{self.retry_attempts}")
                    updated_resume = await llm_json(
                        output_model=Resume,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt
                    )
                    break
                except Exception as e:
                    logger.error(f"LLM call or validation failed on attempt {attempt + 1}: {e}")
                    if attempt == self.retry_attempts - 1:
                        raise Exception(f"Failed to get valid resume JSON from LLM after {self.retry_attempts} attempts.")
            
            # 4. Generate and Upload
            logger.info("Generating updated .docx and uploading to GCS")
            # resume_writer expects a dict, llm_json returns a Pydantic model
            resume_data = updated_resume.model_dump()
            result = generate_and_upload_resume(resume_data)
            
            logger.info(f"Successfully processed resume. New URL: {result.get('gcs_url')}")
            return result

        finally:
            # Cleanup
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Cleaned up temporary file: {local_path}")
            
            # Use the local_file returned by generate_and_upload_resume for cleanup
            if result and "local_file" in result:
                generated_docx = result["local_file"]
                if os.path.exists(generated_docx):
                    os.remove(generated_docx)
                    logger.info(f"Cleaned up generated file: {generated_docx}")

if __name__ == "__main__":
    # Quick test logic
    async def main():
        service = ResumeChatService()
        # Example usage (placeholders)
        # res = await service.process_resume_edit("https://storage.googleapis.com/.../resume.docx", "Fix the professional summary to highlight my Python skills.")
        # print(res)
        pass

    # asyncio.run(main())
