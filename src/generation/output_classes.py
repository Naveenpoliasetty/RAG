from pydantic import BaseModel, Field
from typing import List, Dict, Optional


# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------

class SummaryOutput(BaseModel):
    summaries: List[str]


class TechnicalSkillsOutput(BaseModel):
    skills: Dict[str, List[str]] = Field(default_factory=dict)

class ExperienceSection(BaseModel):
    responsibilities: List[str]
    environment: Optional[str]


class ExperienceOutput(BaseModel):
    experience: List[ExperienceSection]