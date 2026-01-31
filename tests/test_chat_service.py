import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock
from src.resume_chat_editor.chat_service import ResumeChatService
from src.resume_chat_editor.resume_decoder import Resume, Experience

class TestResumeChatService(unittest.IsolatedAsyncioTestCase):

    @patch('src.resume_chat_editor.chat_service.download_resume_from_gcs')
    @patch('src.resume_chat_editor.chat_service.parse_resume')
    @patch('src.resume_chat_editor.chat_service.llm_json')
    @patch('src.resume_chat_editor.chat_service.generate_and_upload_resume')
    async def test_process_resume_edit_success(self, mock_upload, mock_llm, mock_parse, mock_download):
        # Setup mocks
        mock_download.return_value = "temp_resumes/test.docx"
        
        mock_resume = Resume(
            name="John Doe",
            designation="Software Engineer",
            professional_summary=["Summary 1"],
            technical_skills={"Languages": ["Python"]},
            experiences=[
                Experience(client_name="Client A", duration="1 year", job_role="Dev", responsibilities=["Task 1"])
            ],
            education=["Degree X"]
        )
        mock_parse.return_value = mock_resume
        
        mock_updated_resume = mock_resume.model_copy()
        mock_updated_resume.professional_summary = ["Updated Summary"]
        mock_llm.return_value = mock_updated_resume
        
        mock_upload.return_value = {"gcs_url": "https://gcs.com/new_resume.docx"}

        # Run service
        service = ResumeChatService()
        result = await service.process_resume_edit("https://gcs.com/old_resume.docx", "Update summary")

        # Assertions
        self.assertEqual(result["gcs_url"], "https://gcs.com/new_resume.docx")
        mock_download.assert_called_once()
        mock_parse.assert_called_once()
        mock_llm.assert_called_once()
        mock_upload.assert_called_once()

    @patch('src.resume_chat_editor.chat_service.download_resume_from_gcs')
    @patch('src.resume_chat_editor.chat_service.parse_resume')
    @patch('src.resume_chat_editor.chat_service.llm_json')
    async def test_process_resume_edit_retry_loop(self, mock_llm, mock_parse, mock_download):
        # Setup mocks
        mock_download.return_value = "temp_resumes/test.docx"
        mock_parse.return_value = MagicMock(spec=Resume)
        mock_parse.return_value.model_dump_json.return_value = "{}"
        
        # Simulate failure then success
        mock_updated = MagicMock(spec=Resume)
        mock_updated.model_dump.return_value = {}
        mock_updated.name = "John Doe"
        mock_llm.side_effect = [Exception("Validation Error"), mock_updated]

        with patch('src.resume_chat_editor.chat_service.generate_and_upload_resume') as mock_upload:
            mock_upload.return_value = {"gcs_url": "url"}
            
            service = ResumeChatService(retry_attempts=2)
            await service.process_resume_edit("url", "edit")
            
            self.assertEqual(mock_llm.call_count, 2)

if __name__ == "__main__":
    unittest.main()
