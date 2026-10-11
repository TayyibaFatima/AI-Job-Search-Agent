
from pydantic import BaseModel, Field


class ApplicationMaterials(BaseModel):
    tailored_summary: str
    cv_bullet_suggestions: list[str] = Field(default_factory=list)
    cover_letter: str
    skill_gap_guidance: list[str] = Field(default_factory=list)
    personalization_notes: list[str] = Field(default_factory=list)