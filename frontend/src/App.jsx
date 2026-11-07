import { useEffect, useState } from "react";
import { COUNTRIES } from "./countries";
import { currencyFor } from "./currency";
import "./index.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const SOURCES = [
  ["all", "All sources"],
  ["adzuna", "Adzuna"],
  ["jooble", "Jooble"],
  ["remotive", "Remotive (remote jobs)"],
];

const CONFIDENCE = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

const FULL_TEXT = ["full_page", "pasted"];

function hasFullText(job) {
  return FULL_TEXT.includes(job.description_source);
}

function jobId(job) {
  return `${job.company}|${job.job_title}|${job.redirect_url || ""}`;
}

function statusLabel(decision) {
  if (decision === "approved") return "Materials ready";
  if (decision === "rejected") return "Rejected";
  return "Searched";
}

function ScoreBlock({ job }) {
  const score = job.skill_match_score;

  if (score == null || job.score_status === "insufficient_data") {
    return (
      <div className="score">
        <span className="score-value none">n/a</span>
        <span className="score-note">Too little detail in the listing to score it</span>
      </div>
    );
  }

  if (!hasFullText(job)) {
    return (
      <div className="score">
        <span className="score-value none small">Preview only</span>
        <span className="score-note">
          {job.total_matched_required_skills ?? 0} of {job.total_required_skills ?? 0} skills seen
          in a short preview. Paste the full description for a real score.
        </span>
      </div>
    );
  }

  const tentative = job.score_status === "low_confidence";
  const level = tentative ? "tentative" : score >= 75 ? "high" : score >= 45 ? "mid" : "low";

  return (
    <div className="score">
      <span className={`score-value ${level}`}>
        {tentative ? "~" : ""}
        {Math.round(score)}%
      </span>
      <div className="bar"><div className={`bar-fill ${level}`} style={{ width: `${Math.min(100, score)}%` }} /></div>
      <span className="score-note">
        {job.total_matched_required_skills ?? 0} of {job.total_required_skills ?? 0} skills on your CV
        {job.confidence ? ` · ${CONFIDENCE[job.confidence] || job.confidence}` : ""}
      </span>
    </div>
  );
}

function SkillRow({ label, skills, kind }) {
  if (!skills?.length) return null;
  return (
    <div className="skill-row">
      <span className="skill-label">{label}</span>
      <span className="skill-list">
        {skills.map((skill) => (
          <span key={skill} className={`skill ${kind}`}>{skill}</span>
        ))}
      </span>
    </div>
  );
}

function levelOf(job) {
  const score = job.skill_match_score;
  if (score == null || job.score_status === "insufficient_data" || !hasFullText(job)) return "none";
  if (job.score_status === "low_confidence") return "tentative";
  return score >= 75 ? "high" : score >= 45 ? "mid" : "low";
}

function JobCard({ job, hasDraft, busy, anyBusy, onGenerate, onView, onRescore }) {
  const [pasting, setPasting] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const tooShort = pastedText.trim().length < 80;

  async function submitPaste() {
    const done = await onRescore(job, pastedText);
    if (done) {
      setPasting(false);
      setPastedText("");
    }
  }

  const meta = [
    job.location,
    job.experience_level && job.experience_level !== "Not specified" && job.experience_level,
    job.source_label && `via ${job.source_label}`,
    job.description_source === "full_page" && "full listing read",
    job.description_source === "pasted" && "your pasted description",
    !hasFullText(job) && "short preview only",
  ].filter(Boolean);

  const initial = (job.company || "?").trim().charAt(0).toUpperCase();

  return (
    <article className={`job lvl-${levelOf(job)}`}>
      <div className="job-head">
        <div className="avatar" aria-hidden="true">{initial}</div>
        <div className="job-title-block">
          <h3>{job.job_title || "Untitled role"}</h3>
          <p className="job-company">{job.company || "Company not provided"}</p>
          <p className="job-meta">{meta.join(" · ")}</p>
        </div>
        <ScoreBlock job={job} />
      </div>

      <SkillRow label="You have" skills={job.matched_required_skills} kind="matched" />
      <SkillRow label="Partly covered" skills={job.partial_required_skills} kind="partial" />
      <SkillRow label="Still to learn" skills={job.missing_required_skills} kind="missing" />

      {job.warning && <p className="job-warning">{job.warning}</p>}
      {job.interpretation && <p className="job-note">{job.interpretation}</p>}

      {pasting && (
        <div className="paste">
          <label htmlFor={`paste-${jobId(job)}`}>
            Paste the full job description from the listing
          </label>
          <textarea
            id={`paste-${jobId(job)}`}
            rows={8}
            value={pastedText}
            onChange={(e) => setPastedText(e.target.value)}
            placeholder="Copy the whole description from the listing page and paste it here."
          />
          <div className="paste-actions">
            <button className="btn primary small" disabled={anyBusy || tooShort} onClick={submitPaste}>
              {busy ? "Re-scoring..." : "Re-score this job"}
            </button>
            <button className="btn small" disabled={busy} onClick={() => setPasting(false)}>Cancel</button>
            {tooShort && <span className="hint">Paste at least a few sentences.</span>}
          </div>
        </div>
      )}

      <div className="job-actions">
        {hasDraft ? (
          <button className="btn" onClick={() => onView(job)}>View materials</button>
        ) : (
          <button className="btn primary" disabled={anyBusy} onClick={() => onGenerate(job)}>
            {busy && !pasting ? "Writing your drafts..." : "Generate application materials"}
          </button>
        )}
        {!hasFullText(job) && !pasting && (
          <button className="btn" disabled={anyBusy} onClick={() => setPasting(true)}>
            Paste full description
          </button>
        )}
        {job.redirect_url && (
          <a className="link" href={job.redirect_url} target="_blank" rel="noopener noreferrer">
            Open listing{job.source_label ? ` on ${job.source_label}` : ""} ↗
          </a>
        )}
      </div>
    </article>
  );
}

function Material({ title, content, onCopy }) {
  if (!content || (Array.isArray(content) && !content.length)) return null;

  const text = typeof content === "string" ? content.replace(/\\n/g, "\n") : content;

  return (
    <section className="material">
      <div className="material-head">
        <h3>{title}</h3>
        <button className="btn small" onClick={() => onCopy(text)}>Copy</button>
      </div>
      {Array.isArray(text) ? (
        <ul>
          {text.map((item, i) => <li key={`${i}-${item}`}>{item}</li>)}
        </ul>
      ) : (
        <p className="material-text">{text}</p>
      )}
    </section>
  );
}

export default function App() {
  const [cv, setCv] = useState(null);
  const [keyword, setKeyword] = useState("AI machine learning");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("gb");
  const [source, setSource] = useState("all");
  const [count, setCount] = useState("5");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [minSalary, setMinSalary] = useState("");
  const [excluded, setExcluded] = useState("senior,lead,principal");

  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [run, setRun] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [activeDraft, setActiveDraft] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [tab, setTab] = useState("search");

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string" ? data.detail : `Request failed (${response.status})`
      );
    }
    return data;
  }

  function friendly(err) {
    return err instanceof TypeError
      ? "Can't reach the server. Make sure the backend is running."
      : err.message;
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const data = await requestJson(`${API}/api/history?limit=10`);
      setHistory(data.history || []);
    } catch (err) {
      setError(`Couldn't load history. ${friendly(err)}`);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function searchJobs(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setRun(null);
    setDrafts({});
    setActiveDraft(null);

    if (!cv) {
      setError("Choose your CV (PDF) first.");
      return;
    }

    const form = new FormData();
    form.append("cv_file", cv);
    form.append("keyword", keyword.trim());
    form.append("location", location.trim());
    form.append("country", country);
    form.append("source", source);
    form.append("results_per_page", count);
    form.append("remote_only", String(remoteOnly));
    form.append("excluded_keywords", excluded);
    if (minSalary.trim()) form.append("min_salary", minSalary);

    setLoading(true);
    try {
      const data = await requestJson(`${API}/api/search`, { method: "POST", body: form });
      setRun(data);
      setTab("search");
      const labels = [...new Set((data.ranked_jobs || []).map((j) => j.source_label).filter(Boolean))];
      setNotice(
        data.ranked_jobs?.length
          ? `Found ${data.ranked_jobs.length} jobs${labels.length ? ` from ${labels.join(", ")}` : ""}.`
          : data.message || "No suitable jobs found. Try different keywords."
      );
      await loadHistory();
    } catch (err) {
      setError(friendly(err));
    } finally {
      setLoading(false);
    }
  }

  async function generateMaterials(job) {
    const index = (run?.ranked_jobs || []).findIndex((item) => jobId(item) === jobId(job));
    if (!run?.thread_id || index < 0) return;

    setError("");
    setNotice("");
    setBusyId(jobId(job));

    try {
      const data = await requestJson(
        `${API}/api/runs/${encodeURIComponent(run.thread_id)}/materials`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_index: index }),
        }
      );
      const id = jobId(data.job);
      setDrafts((previous) => ({
        ...previous,
        [id]: { job: data.job, materials: data.application_materials },
      }));
      setActiveDraft(id);
      setTab("materials");
      await loadHistory();
    } catch (err) {
      setError(friendly(err));
    } finally {
      setBusyId(null);
    }
  }

  async function rescoreJob(job, description) {
    const index = (run?.ranked_jobs || []).findIndex((item) => jobId(item) === jobId(job));
    if (!run?.thread_id || index < 0) return false;

    setError("");
    setNotice("");
    setBusyId(jobId(job));

    try {
      const data = await requestJson(
        `${API}/api/runs/${encodeURIComponent(run.thread_id)}/rescore`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_index: index, description }),
        }
      );
      // The list is re-ranked, so replace it as a whole.
      setRun((previous) => ({ ...previous, ranked_jobs: data.ranked_jobs }));
      setNotice("Score updated from your description.");
      return true;
    } catch (err) {
      setError(friendly(err));
      return false;
    } finally {
      setBusyId(null);
    }
  }

  function viewMaterials(job) {
    setActiveDraft(jobId(job));
    setTab("materials");
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(
        Array.isArray(value) ? value.join("\n\n") : String(value)
      );
      setNotice("Copied to clipboard.");
    } catch {
      setError("Couldn't copy automatically. Select the text and copy it by hand.");
    }
  }

  const jobs = run?.ranked_jobs || [];
  const draftIds = Object.keys(drafts);
  const current = activeDraft != null ? drafts[activeDraft] : null;
  const materials = current?.materials;
  const currency = currencyFor(country);

  return (
    <div className="page">
      <header className="header">
        <div className="header-inner">
          <span className="brand">Job Search Agent</span>
          <nav className="tabs">
            <button className={tab === "search" ? "on" : ""} onClick={() => setTab("search")}>
              Search
            </button>
            <button className={tab === "materials" ? "on" : ""} onClick={() => setTab("materials")}>
              Materials{draftIds.length ? ` (${draftIds.length})` : ""}
            </button>
            <button
              className={tab === "history" ? "on" : ""}
              onClick={() => {
                setTab("history");
                loadHistory();
              }}
            >
              History
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
        {notice && (
          <div className="banner ok" role="status">
            <span>{notice}</span>
            <button onClick={() => setNotice("")} aria-label="Dismiss">×</button>
          </div>
        )}

        {tab === "search" && (
          <>
            <section className="intro">
              <h1>Let&rsquo;s find you a good fit.</h1>
              <p>
                Upload your CV and tell us what you&rsquo;re after. We&rsquo;ll line up real openings
                by how well your skills match, and you can draft a cover letter for any of them.
              </p>
            </section>

            <form className="panel" onSubmit={searchJobs}>
              <div className="field">
                <label htmlFor="cv">Your CV (PDF, up to 10 MB)</label>
                <input
                  id="cv"
                  className="file"
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={(e) => setCv(e.target.files?.[0] || null)}
                />
              </div>

              <div className="grid">
                <div className="field">
                  <label htmlFor="kw">Job title or keywords</label>
                  <input
                    id="kw"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="e.g. Machine learning engineer"
                    required
                  />
                </div>

                <div className="field">
                  <label htmlFor="loc">City (optional)</label>
                  <input
                    id="loc"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. London"
                  />
                </div>

                <div className="field">
                  <label htmlFor="country">Country</label>
                  <select id="country" value={country} onChange={(e) => setCountry(e.target.value)}>
                    {COUNTRIES.map(([code, name]) => (
                      <option key={code} value={code}>{name}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="source">Job source</label>
                  <select id="source" value={source} onChange={(e) => setSource(e.target.value)}>
                    {SOURCES.map(([value, name]) => (
                      <option key={value} value={value}>{name}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="count">Results per source</label>
                  <select id="count" value={count} onChange={(e) => setCount(e.target.value)}>
                    {[5, 10, 15, 20].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor="sal">
                    Minimum yearly salary ({currency || "local currency"}, optional)
                  </label>
                  <div className="prefixed">
                    {currency && <span className="prefix">{currency}</span>}
                    <input
                      id="sal"
                      type="number"
                      min="1"
                      value={minSalary}
                      onChange={(e) => setMinSalary(e.target.value)}
                      placeholder="e.g. 30000"
                    />
                  </div>
                </div>

                <div className="field wide">
                  <label htmlFor="exc">Leave out titles containing</label>
                  <input id="exc" value={excluded} onChange={(e) => setExcluded(e.target.value)} />
                  <span className="hint">Separate words with commas.</span>
                </div>
              </div>

              <label className="check">
                <input
                  type="checkbox"
                  checked={remoteOnly}
                  onChange={(e) => setRemoteOnly(e.target.checked)}
                />
                Remote positions only
              </label>

              <div className="form-end">
                <button className="btn primary big" type="submit" disabled={loading}>
                  {loading ? "Searching..." : "Find jobs"}
                </button>
                {loading && <span className="hint">Reading listings, this can take a minute.</span>}
              </div>
            </form>

            {run && (
              <section className="results">
                <div className="results-head">
                  <h2>{jobs.length ? `${jobs.length} ${jobs.length === 1 ? "job" : "jobs"} for you` : "Results"}</h2>
                  <p className="hint">Best skill match first. You can write application materials for any of them.</p>
                </div>

                {jobs.length ? (
                  jobs.map((job, index) => (
                    <JobCard
                      key={`${jobId(job)}-${index}`}
                      job={job}
                      hasDraft={jobId(job) in drafts}
                      busy={busyId === jobId(job)}
                      anyBusy={busyId !== null}
                      onGenerate={generateMaterials}
                      onView={viewMaterials}
                      onRescore={rescoreJob}
                    />
                  ))
                ) : (
                  <p className="empty">Nothing matched. Try broader keywords or a different location.</p>
                )}
              </section>
            )}
          </>
        )}

        {tab === "materials" && (
          <section className="panel">
            <h2>Application materials</h2>

            {draftIds.length > 0 && (
              <div className="draft-picker">
                {draftIds.map((id) => (
                  <button
                    key={id}
                    className={`btn small ${id === activeDraft ? "primary" : ""}`}
                    onClick={() => setActiveDraft(id)}
                  >
                    {drafts[id].job?.job_title || "Job"}
                    {drafts[id].job?.company ? `, ${drafts[id].job.company}` : ""}
                  </button>
                ))}
              </div>
            )}

            {materials ? (
              <>
                <div className="material-top">
                  <p className="job-warning">
                    These drafts were written by an AI. Check every claim against your real experience before you use them.
                  </p>
                  <button
                    className="btn small"
                    onClick={() =>
                      copyText(
                        [
                          "COVER LETTER",
                          materials.cover_letter || "",
                          "\nTAILORED SUMMARY",
                          materials.tailored_summary || "",
                          "\nCV BULLET SUGGESTIONS",
                          ...(materials.cv_bullet_suggestions || []),
                        ].join("\n")
                      )
                    }
                  >
                    Copy all
                  </button>
                </div>
                <Material title="Cover letter" content={materials.cover_letter} onCopy={copyText} />
                <Material title="Tailored summary" content={materials.tailored_summary} onCopy={copyText} />
                <Material title="CV bullet suggestions" content={materials.cv_bullet_suggestions} onCopy={copyText} />
                <Material title="Skill-gap guidance" content={materials.skill_gap_guidance} onCopy={copyText} />
                <Material title="Notes" content={materials.personalization_notes} onCopy={copyText} />
              </>
            ) : (
              <p className="empty">
                Nothing here yet. Run a search, then pick &ldquo;Generate application materials&rdquo; on any job.
              </p>
            )}
          </section>
        )}

        {tab === "history" && (
          <section className="panel">
            <div className="panel-head">
              <h2>Recent searches</h2>
              <button className="btn small" onClick={loadHistory} disabled={historyLoading}>
                {historyLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {history.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Search</th>
                    <th>Location</th>
                    <th>Jobs</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.run_id}>
                      <td>{item.keyword || "Job search"}</td>
                      <td>{item.location || "Anywhere"}</td>
                      <td>{item.ranked_jobs?.length || 0}</td>
                      <td>{statusLabel(item.decision)}</td>
                      <td>{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty">{historyLoading ? "Loading..." : "No saved searches yet."}</p>
            )}
          </section>
        )}
      </main>

      {error && (
        <div className="overlay" onClick={() => setError("")}>
          <div className="modal" role="alertdialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>That didn&rsquo;t work</h3>
            <p>{error}</p>
            <button className="btn primary" autoFocus onClick={() => setError("")}>OK</button>
          </div>
        </div>
      )}
    </div>
  );
}
