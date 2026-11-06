import json

from backend.tools.job_enricher import (
    extract_from_container,
    extract_from_json_ld,
)


def test_json_ld_description_is_extracted_and_nav_ignored():
    desc = "<p>Build Python APIs.</p><ul><li>FastAPI</li><li>Docker</li></ul>"
    page = (
        "<nav>Java Kubernetes</nav>"
        '<script type="application/ld+json">'
        + json.dumps({"@type": "JobPosting", "description": desc})
        + "</script>"
    )
    text = extract_from_json_ld(page)
    assert "Python" in text and "Docker" in text
    assert "Kubernetes" not in text


def test_container_extraction_skips_scripts_and_siblings():
    page = (
        "<nav>Terraform</nav>"
        '<div class="adp-body"><p>Build <b>Python</b> APIs.</p>'
        "<ul><li>SQL</li></ul><script>var x='Rust'</script></div>"
        '<div class="similar">Go Java</div>'
    )
    text = extract_from_container(page)
    assert "Python" in text and "SQL" in text
    assert "Rust" not in text and "Java" not in text and "Terraform" not in text
