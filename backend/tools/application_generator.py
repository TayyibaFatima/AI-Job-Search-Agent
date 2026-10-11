import json
import os
import re

from dotenv import load_dotenv
from groq import Groq, BadRequestError

from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements
from backend.models.application_materials import ApplicationMaterials


load_dotenv()

MODEL_NAME = "openai/gpt-oss-20b"


def parse_json_response(content: str) -> dict:
    """Parse JSON returned by the model, including fenced JSON responses."""

    if not content or not content.strip():
        raise ValueError("Groq returned an empty response.")

    content = content.strip()

    # Remove Markdown code fences if the model adds them.
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*```$", "", content)

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Try extracting a JSON object from surrounding text.
        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end <= start:
            raise ValueError("Groq did not return a valid JSON object.")

        result = json.loads(content[start:end + 1])

    if not isinstance(result, dict):
        raise ValueError("Groq response must be a JSON object.")

    return result


def create_cover_letter(
    candidate: CandidateProfile,
    job: JobRequirements,
) -> str:
    """Create a basic cover letter without inventing candidate facts."""

    company_text = f" at {job.company}" if job.company else ""

    return (
        "Dear Hiring Manager,\n\n"
        f"I am writing to express my interest in the "
        f"{job.job_title} position{company_text}. "
        "I would welcome the opportunity to discuss how my "
        "background, projects, and relevant skills align with "
        "the requirements of this role.\n\n"
        "Thank you for your time and consideration.\n\n"
        f"Sincerely,\n{candidate.name}"
    )


def generate_application_materials(
    candidate: CandidateProfile,
    job: JobRequirements,
    match_report: dict,
) -> ApplicationMaterials:
    """
    Generate truthful application materials using Groq.
    Retries without JSON mode if Groq rejects structured output.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to your .env file."
        )

    client = Groq(api_key=api_key)

    candidate_data = candidate.model_dump()
    job_data = job.model_dump()

    prompt = f"""
Create professional job application materials in valid JSON.

CANDIDATE PROFILE:
{json.dumps(candidate_data, ensure_ascii=False)}

JOB REQUIREMENTS:
{json.dumps(job_data, ensure_ascii=False)}

MATCH REPORT:
{json.dumps(match_report, ensure_ascii=False)}

Return one JSON object with exactly these fields:

{{
  "tailored_summary": "Professional summary tailored to this job",
  "cv_bullet_suggestions": ["Truthful CV bullet suggestions"],
  "cover_letter": "Complete professional cover letter",
  "skill_gap_guidance": ["Advice for missing required skills"],
  "personalization_notes": ["Details the candidate should verify"]
}}

RULES:
- Use only facts supported by the candidate profile.
- Never invent employers, degrees, certifications, projects, achievements,
  experience, years of experience, or numerical results.
- Do not claim leadership, management, mentoring, or team coordination
  unless the profile explicitly supports it.
- Do not invent employer culture, company priorities, or responsibilities.
- Do not claim expertise or qualifications unsupported by the profile.
- Do not invent location, remote preference, availability, or work arrangement.
- Distinguish verified skills from missing skills.
- Do not claim that the candidate has a skill merely because the job requires it.
- If job information is incomplete, do not guess missing details.
- Keep all writing professional, relevant, and concise.
- The cover letter must include a greeting, role-specific opening, truthful
  body, closing, and candidate name when available.
- All five fields are required.
- The three list fields must contain JSON arrays, even when empty.
- Return JSON only, without Markdown fences or explanations.
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You write truthful job application materials. "
                "Follow the requested JSON structure. "
                "Never invent candidate facts."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    result = None
    json_mode_error = None

    # First attempt: ask Groq to return a JSON object.
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=3000,
        )

        content = response.choices[0].message.content
        result = parse_json_response(content)

    except (BadRequestError, ValueError, json.JSONDecodeError) as error:
        json_mode_error = error

    # Second attempt: let the model respond normally and parse its JSON.
    if result is None:
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_completion_tokens=3000,
            )

            content = response.choices[0].message.content
            result = parse_json_response(content)

        except Exception as error:
            raise ValueError(
                "Could not generate valid application materials. "
                f"JSON-mode attempt: {json_mode_error}. "
                f"Fallback attempt: {error}"
            ) from error

    # Fill missing fields so incomplete model output can be handled safely.
    if not isinstance(result.get("tailored_summary"), str):
        result["tailored_summary"] = ""

    if not isinstance(result.get("cv_bullet_suggestions"), list):
        result["cv_bullet_suggestions"] = []

    if not isinstance(result.get("skill_gap_guidance"), list):
        result["skill_gap_guidance"] = []

    if not isinstance(result.get("personalization_notes"), list):
        result["personalization_notes"] = []

    # Use a basic fallback rather than leaving the required field missing.
    if (
        not isinstance(result.get("cover_letter"), str)
        or not result["cover_letter"].strip()
    ):
        result["cover_letter"] = create_cover_letter(candidate, job)

    # Keep only non-empty strings in list fields.
    for field in (
        "cv_bullet_suggestions",
        "skill_gap_guidance",
        "personalization_notes",
    ):
        result[field] = [
            item.strip()
            for item in result[field]
            if isinstance(item, str) and item.strip()
        ]

    return ApplicationMaterials.model_validate(result)
