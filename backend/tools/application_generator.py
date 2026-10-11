
import json
import os

from dotenv import load_dotenv
from groq import Groq

from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements
from backend.models.application_materials import ApplicationMaterials


load_dotenv()

MODEL_NAME = "openai/gpt-oss-20b"


def generate_application_materials(
    candidate: CandidateProfile,
    job: JobRequirements,
    match_report: dict,
) -> ApplicationMaterials:

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from the .env file.")

    client = Groq(api_key=api_key)

    candidate_data = candidate.model_dump()
    job_data = job.model_dump()

    prompt_data = {
        "candidate": candidate_data,
        "job_requirements": job_data,
        "skill_match_report": match_report,
    }

    system_prompt = """
You are an AI job application assistant.

Generate truthful, personalized application materials using only the
provided candidate profile, job requirements, and skill-match report.

Rules:
1. Never invent skills, qualifications, experience, achievements,
   employers, degrees, or projects.
2. Do not claim the candidate has a skill listed as missing.
3. Suggest CV bullet points based on real projects, education,
   experience, and technologies in the candidate profile.
4. You may improve wording and emphasize relevant existing evidence.
5. Do not invent numerical results or achievements.
6. If evidence is insufficient for a particular claim, leave it out.
7. Write a professional, concise, job-specific cover letter.
8. Do not claim that the candidate has experience simply because
   a skill appears in the job description.
9. Mention skill gaps only as honest development suggestions.
10. Return valid JSON with these exact keys:
    - tailored_summary: string
    - cv_bullet_suggestions: array of strings
    - cover_letter: string
    - skill_gap_guidance: array of strings
    - personalization_notes: array of strings

11. Never infer leadership, mentoring, management, or team
    coordination experience unless explicitly supported by the
    candidate profile.
12. Never invent the employer's business focus, company culture,
    team structure, or project responsibilities.
13. Do not state that the candidate has "strong expertise",
    "high precision", "high recall", or other achievement claims
    unless the supplied data explicitly supports them.
14. Do not invent the candidate's location, remote-work preference,
    or preferred work arrangement. Only use information provided
    in the supplied candidate profile.
15. If a job description is incomplete, keep the application
    materials grounded in the available information and avoid
    guessing what the employer values.
16. Tailor the materials by emphasizing verified transferable skills
    rather than adding unsupported qualifications.

The cover letter should be ready for the candidate to review and edit.
Do not include placeholders for information already available in the
candidate profile or job requirements.
If information is unavailable, do not invent it.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(prompt_data, ensure_ascii=False),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Groq returned an empty application-materials response.")

    try:
        result = json.loads(content)
        return ApplicationMaterials.model_validate(result)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(
            f"Could not validate generated application materials: {error}"
        ) from error