
from pydantic import BaseModel, Field


class JobRequirements(BaseModel):
    job_title: str
    company: str = ""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    experience_level: str = "Not specified"
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)

    description_quality: str = "limited"
    missing_information: list[str] = Field(default_factory=list)