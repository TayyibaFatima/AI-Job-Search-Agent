import os

# Keep unit tests offline and deterministic.
os.environ["USE_LLM_JOB_ANALYSIS"] = "false"
os.environ["ENRICH_DESCRIPTIONS"] = "false"
os.environ.setdefault("GROQ_API_KEY", "test-key")
