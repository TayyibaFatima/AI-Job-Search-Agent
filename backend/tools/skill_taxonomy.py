"""
Deterministic skill taxonomy.

Why this exists
---------------
Job listings and CVs were previously analysed only by an LLM, which is
non-deterministic: the same job could yield 0 skills on one run and 1-2
skills on the next. A fixed taxonomy gives the same answer every time and
lets the LLM act only as an optional, grounded supplement.

Each canonical skill maps to a list of aliases. Matching is done on whole
tokens (so "java" never matches inside "javascript", and "sql" never
matches inside "postgresql").
"""

from __future__ import annotations

import re

SKILLS: dict[str, list[str]] = {
    # ---- Languages -------------------------------------------------------
    "python": ["python", "python3"],
    "java": ["java"],
    "javascript": ["javascript", "js", "ecmascript", "es6"],
    "typescript": ["typescript"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp"],
    "go": ["golang"],
    "rust": ["rust"],
    "sql": ["sql", "t-sql", "pl/sql"],
    "scala": ["scala"],
    "kotlin": ["kotlin"],
    "swift": ["swiftui", "swift programming"],
    "php": ["php"],
    "ruby": ["ruby"],
    "bash": ["bash", "shell scripting", "shell script"],
    "matlab": ["matlab"],
    "r": ["r programming", "r language", "rstudio"],
    # ---- AI / ML ---------------------------------------------------------
    "ai": ["ai", "artificial intelligence"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "natural language processing": ["natural language processing", "nlp"],
    "computer vision": ["computer vision"],
    "generative ai": ["generative ai", "gen ai", "genai"],
    "large language models": ["large language model", "llm", "llms"],
    "rag": ["rag", "retrieval augmented generation",
            "retrieval-augmented generation"],
    "prompt engineering": ["prompt engineering"],
    "reinforcement learning": ["reinforcement learning"],
    "mlops": ["mlops", "ml ops"],
    "langchain": ["langchain"],
    "langgraph": ["langgraph"],
    "hugging face": ["hugging face", "huggingface", "transformers library"],
    "openai api": ["openai api", "openai"],
    "pytorch": ["pytorch", "torch"],
    "tensorflow": ["tensorflow"],
    "keras": ["keras"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "xgboost": ["xgboost", "lightgbm", "gradient boosting"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "scipy": ["scipy"],
    "matplotlib": ["matplotlib", "seaborn"],
    "opencv": ["opencv"],
    "spacy": ["spacy"],
    "nltk": ["nltk"],
    "neural networks": ["neural network", "neural networks", "cnn", "rnn",
                        "lstm"],
    "data science": ["data science", "data scientist"],
    "data analysis": ["data analysis", "data analytics", "data analyst"],
    "statistics": ["statistics", "statistical analysis", "statistical modelling",
                   "statistical modeling"],
    "feature engineering": ["feature engineering"],
    "vector databases": ["vector database", "vector databases", "pinecone",
                         "faiss", "chroma", "chromadb", "weaviate", "milvus"],
    "model deployment": ["model deployment", "model serving", "model deploy"],
    # ---- Data engineering / BI ------------------------------------------
    "spark": ["pyspark", "apache spark", "spark streaming"],
    "hadoop": ["hadoop"],
    "airflow": ["airflow", "apache airflow"],
    "kafka": ["kafka", "apache kafka"],
    "etl": ["etl", "elt", "data pipeline", "data pipelines"],
    "dbt": ["dbt"],
    "snowflake": ["snowflake"],
    "databricks": ["databricks"],
    "bigquery": ["bigquery"],
    "data warehousing": ["data warehouse", "data warehousing"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "excel": ["=Excel", "ms excel", "microsoft excel", "advanced excel"],
    # ---- Backend / web ---------------------------------------------------
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "node.js": ["node.js", "nodejs", "node js"],
    "express": ["express.js", "expressjs"],
    "react": ["=React", "react.js", "reactjs", "react native"],
    "angular": ["angular"],
    "vue": ["vue", "vue.js", "vuejs"],
    "next.js": ["next.js", "nextjs"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "rest apis": ["rest api", "restful api", "restful", "restful services"],
    "graphql": ["graphql"],
    "microservices": ["microservice", "microservices"],
    "grpc": ["grpc"],
    "api integration": ["api integration", "api integrations",
                        "third-party api", "third party api"],
    # ---- Databases -------------------------------------------------------
    "postgresql": ["postgresql", "postgres"],
    "mysql": ["mysql", "mariadb"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "sqlite": ["sqlite"],
    "elasticsearch": ["elasticsearch", "opensearch"],
    "nosql": ["nosql"],
    # ---- Cloud / DevOps --------------------------------------------------
    "aws": ["aws", "amazon web services", "sagemaker"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud", "vertex ai"],
    "docker": ["docker", "containerisation", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "terraform": ["terraform"],
    "ci/cd": ["ci/cd", "ci cd", "continuous integration",
              "continuous delivery", "continuous deployment"],
    "jenkins": ["jenkins"],
    "github actions": ["github actions"],
    "linux": ["linux", "unix"],
    "git": ["git", "github", "gitlab", "version control"],
    "ansible": ["ansible"],
    # ---- Automation / tooling -------------------------------------------
    "n8n": ["n8n"],
    "zapier": ["zapier", "make.com"],
    "automation": ["workflow automation", "process automation", "automation"],
    "web scraping": ["web scraping", "scraping", "beautifulsoup", "scrapy"],
    "selenium": ["selenium", "playwright"],
    "unit testing": ["unit testing", "unit tests", "pytest", "test automation"],
    "agile": ["agile", "scrum", "kanban"],
    "jira": ["jira"],
    "whatsapp api": ["whatsapp api", "whatsapp business api"],
}


def _alias_pattern(alias: str) -> str:
    """
    Regex for one alias: whole-token, tolerant of space/hyphen and plurals.

    An alias starting with "=" is case-sensitive (e.g. "=React" will not
    match the verb "react"); all other aliases are case-insensitive.
    """
    case_sensitive = alias.startswith("=")
    alias = alias.lstrip("=")

    escaped = re.escape(alias if case_sensitive else alias.lower())
    # Treat escaped spaces and hyphens as interchangeable separators.
    # (Single pass: chained replace() calls would corrupt each other.)
    escaped = re.sub(r"(?:\\ |\\-)+", lambda _m: r"[\s\-]+", escaped)
    plural = "s?" if alias[-1].isalpha() else ""

    body = (
        r"(?<![A-Za-z0-9+#.])"
        + escaped
        + plural
        + r"(?![A-Za-z0-9+#])"
    )
    return f"(?-i:{body})" if case_sensitive else f"(?i:{body})"


_SKILL_PATTERNS: dict[str, re.Pattern] = {
    canonical: re.compile("|".join(_alias_pattern(a) for a in aliases))
    for canonical, aliases in SKILLS.items()
}

# alias (cleaned) -> canonical, used by normalize_skill()
_ALIAS_INDEX: dict[str, str] = {}
for _canonical, _aliases in SKILLS.items():
    _ALIAS_INDEX[_canonical] = _canonical
    for _alias in _aliases:
        _ALIAS_INDEX.setdefault(_alias.lstrip("=").lower(), _canonical)


def clean_label(value: str) -> str:
    """Lower-case a skill label and strip decoration."""
    text = (value or "").lower().strip().replace("_", " ")
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9+#./\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_skill(value: str) -> str:
    """Map any alias to its canonical name; unknown skills stay as cleaned text."""
    cleaned = clean_label(value)
    return _ALIAS_INDEX.get(cleaned, cleaned)


def find_skills(text: str) -> list[str]:
    """
    Return canonical skills literally present in `text`,
    ordered by first appearance. Deterministic.
    """
    if not text:
        return []

    hits: list[tuple[int, str]] = []
    for canonical, pattern in _SKILL_PATTERNS.items():
        match = pattern.search(text)
        if match:
            hits.append((match.start(), canonical))

    hits.sort()
    return [canonical for _, canonical in hits]


def skills_in_sentence(sentence: str) -> set[str]:
    return set(find_skills(sentence))


def contains_phrase(text: str, phrase: str) -> bool:
    """Whole-token, case-insensitive phrase search."""
    if not text or not phrase:
        return False

    pattern = (
        r"(?<![a-z0-9+#.])"
        + re.escape(phrase.lower())
        + r"(?![a-z0-9+#])"
    )
    return bool(re.search(pattern, text.lower()))


def strip_skills(text: str) -> str:
    """Return `text` with every recognised skill phrase removed."""
    result = text or ""
    for canonical in find_skills(result):
        result = _SKILL_PATTERNS[canonical].sub(" ", result)
    return result
