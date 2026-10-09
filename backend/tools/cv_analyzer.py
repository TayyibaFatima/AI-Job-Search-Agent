import os

from dotenv import load_dotenv
from groq import Groq
from backend.models.candidate import CandidateProfile


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def analyze_cv(cv_text: str) -> CandidateProfile:

    prompt = f"""
Analyze the following CV and extract the candidate information.

Return information only when it is supported by the CV.
Do not invent skills, experience, projects, education, or technologies.

CV:

{cv_text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": """
You are a CV information extraction system.

Extract:
- candidate name
- technical and relevant skills
- projects
- work experience
- education

Do not invent information.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "candidate_profile",
                "schema": CandidateProfile.model_json_schema()
            }
        }
    )

    return CandidateProfile.model_validate_json(
        response.choices[0].message.content
    )