from pydantic import BaseModel, Field


# Description sources that contain the complete listing text.
FULL_TEXT_SOURCES = ("full_page", "pasted")


class JobRequirements(BaseModel):
    job_title: str
    company: str = ""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    experience_level: str = "Not specified"
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)

    # "good" | "limited" | "insufficient"
    description_quality: str = "limited"
    missing_information: list[str] = Field(default_factory=list)

    # How much text the analysis was based on, and where it came from:
    # "full_page" (complete listing) or "snippet" (short API preview).
    word_count: int = 0
    description_source: str = "snippet"
