from pydantic import BaseModel, Field


class Project(BaseModel):
    name: str
    technologies: list[str] = Field(default_factory=list)
    description: str = ""


class Experience(BaseModel):
    role: str
    organization: str = ""
    description: str = ""


class Education(BaseModel):
    degree: str
    institution: str = ""
    field: str = ""


class CandidateProfile(BaseModel):
    name: str
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)