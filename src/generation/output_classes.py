from pydantic import BaseModel, Field
from typing import List, Dict, Optional


# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------

class SummaryOutput(BaseModel):
    job_title: str = Field(description="The job title extracted from the job description")
    summaries: List[str]


class TechnicalSkillsOutput(BaseModel):
    skills: Dict[str, List[str]] = Field(default_factory=dict)

class ExperienceSection(BaseModel):
    job_role: str = Field(description="The job title/role for this experience")
    responsibilities: List[str]
    environment: Optional[str] = None


class ExperienceOutput(BaseModel):
    experience: List[ExperienceSection]