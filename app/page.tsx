"use client";

import { useState } from "react";
import { Header } from "./components/Header";
import { Poster } from "./components/Poster";
import { RatingsStrip } from "./components/RatingCell";
import { AgentStatus } from "./components/AgentStatus";

interface Recommendation {
  title: string;
  year: number;
  poster_url: string;
  imdb_score: string | number;
  metascore: string | number;
  rotten_tomatoes: string | number;
  explanation: string;
  overview: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function Page() {
  // — same state shape as before —
  const [watchedFile, setWatchedFile] = useState<File | null>(null);
  const [ratingsFile, setRatingsFile] = useState<File | null>(null);
  const [parseStatus, setParseStatus] = useState<{
    total_watched: number;
    total_rated: number;
  } | null>(null);
  const [parseError, setParseError] = useState<string>("");
  const [watched, setWatched] = useState<unknown[] | null>(null);
  const [rated, setRated] = useState<unknown[] | null>(null);

  const [request, setRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recommendError, setRecommendError] = useState<string>("");

  // visual phase: "import" → "ready" → "result"
  const phase: "import" | "ready" | "result" = recommendation
    ? "result"
    : watched
    ? "ready"
    : "import";

  async function handleParse() {
    if (!watchedFile) return;
    setParseError("");
    setParseStatus(null);

    const form = new FormData();
    form.append("watched_file", watchedFile);
    if (ratingsFile) form.append("ratings_file", ratingsFile);

    try {
      const res = await fetch(`${API_BASE}/parse`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setWatched(data.watched);
      setRated(data.rated ?? []);
      setParseStatus({
        total_watched: data.total_watched,
        total_rated: data.total_rated,
      });
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Parse failed");
    }
  }

  async function handleRecommend() {
    if (!watched || !request.trim()) return;
    setRecommendError("");
    setRecommendation(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: request.trim(), watched, rated: rated ?? [] }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setRecommendation(data);
    } catch (e) {
      setRecommendError(e instanceof Error ? e.message : "Recommendation failed");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setRecommendation(null);
    setRecommendError("");
    setRequest("");
  }

  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* atmospheric backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            phase === "result"
              ? `radial-gradient(50% 70% at 70% 40%, rgba(196,122,44,0.45) 0%, transparent 60%),
                 radial-gradient(60% 80% at 20% 80%, rgba(40,20,30,0.6) 0%, transparent 65%),
                 linear-gradient(180deg, #1a0f06 0%, #050302 100%)`
              : `radial-gradient(40% 60% at 15% 30%, rgba(196,122,44,0.22) 0%, transparent 60%),
                 radial-gradient(50% 70% at 85% 80%, rgba(70,40,80,0.28) 0%, transparent 65%),
                 var(--ns-bg)`,
        }}
      />
      <div className="ns-grain" />

      {/* nav */}
      <header className="relative z-10 flex items-center justify-between px-8 py-5">
        <Header />
        <div className="flex gap-3 items-center">
          {phase === "result" && (
            <>
              <button className="ns-btn ns-btn-ghost" style={{ height: 34, fontSize: 12 }} onClick={handleRecommend} disabled={loading}>
                ↻ another
              </button>
              <button className="ns-btn ns-btn-ghost" style={{ height: 34, fontSize: 12 }} onClick={reset}>
                ← new search
              </button>
            </>
          )}
          {phase === "ready" && parseStatus && (
            <span className="ns-mono text-[10.5px]" style={{ color: "var(--ns-fg-mute)", letterSpacing: "0.14em" }}>
              {parseStatus.total_watched} WATCHED · {parseStatus.total_rated} RATED
            </span>
          )}
        </div>
      </header>

      {/* body */}
      <div className="relative z-[1]">
        {phase === "import" && (
          <ImportScreen
            watchedFile={watchedFile}
            setWatchedFile={setWatchedFile}
            ratingsFile={ratingsFile}
            setRatingsFile={setRatingsFile}
            onParse={handleParse}
            error={parseError}
            parseStatus={parseStatus}
          />
        )}

        {phase === "ready" && (
          <PromptScreen
            request={request}
            setRequest={setRequest}
            onSubmit={handleRecommend}
            loading={loading}
            error={recommendError}
            parseStatus={parseStatus}
          />
        )}

        {phase === "result" && recommendation && (
          <ResultScreen rec={recommendation} request={request} />
        )}
      </div>
    </main>
  );
}

// ── Import screen (CSV upload) ────────────────────────────────
function ImportScreen({
  watchedFile,
  setWatchedFile,
  ratingsFile,
  setRatingsFile,
  onParse,
  error,
  parseStatus,
}: {
  watchedFile: File | null;
  setWatchedFile: (f: File | null) => void;
  ratingsFile: File | null;
  setRatingsFile: (f: File | null) => void;
  onParse: () => void;
  error: string;
  parseStatus: { total_watched: number; total_rated: number } | null;
}) {
  return (
    <section className="ns-fade-in grid grid-cols-1 md:grid-cols-[1.05fr_1fr] items-center gap-12 px-20 pt-8 pb-20 max-w-[1280px] mx-auto">
      {/* left — pitch */}
      <div>
        <div className="ns-eyebrow mb-6">⟶ &nbsp; Calibrate</div>
        <h1
          className="ns-display m-0"
          style={{
            fontSize: 76,
            color: "var(--ns-fg)",
            lineHeight: 0.98,
            letterSpacing: "-0.02em",
          }}
        >
          Bring your<br />
          <span style={{ fontStyle: "italic", color: "var(--ns-accent)" }}>
            watch history.
          </span>
        </h1>
        <p
          className="mt-7"
          style={{
            fontSize: 17,
            lineHeight: 1.55,
            color: "var(--ns-fg-dim)",
            maxWidth: 460,
          }}
        >
          Drop in your Letterboxd export. We&rsquo;ll learn what you&rsquo;ve seen,
          what you loved, and what your ratings really mean — privately, on-device,
          before suggesting anything.
        </p>

        <div className="mt-10 flex flex-col gap-5">
          {[
            ["01", "Export from Letterboxd", "Settings → Data → Export your data"],
            ["02", "Drop watched.csv & ratings.csv here", "We deduplicate by TMDB ID"],
            ["03", "Stay in this tab while we read it", "Parsed locally · zero upload to us"],
          ].map(([n, t, s]) => (
            <div key={n} className="flex gap-3.5 items-start">
              <span
                className="ns-mono shrink-0"
                style={{
                  color: "var(--ns-accent)",
                  fontSize: 11,
                  letterSpacing: "0.1em",
                  lineHeight: 1.5,
                }}
              >
                {n}
              </span>
              <div className="min-w-0">
                <div style={{ color: "var(--ns-fg)", fontSize: 14, lineHeight: 1.4 }}>{t}</div>
                <div
                  style={{
                    color: "var(--ns-fg-mute)",
                    fontSize: 12.5,
                    lineHeight: 1.4,
                    marginTop: 4,
                  }}
                >
                  {s}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* right — drop zones */}
      <div
        className="ns-glass p-7"
        style={{ boxShadow: "var(--ns-shadow-2)" }}
      >
        <div className="ns-eyebrow mb-4">Letterboxd Import</div>

        <DropSlot
          required
          file={watchedFile}
          label="watched.csv"
          sub="drag here or click to browse"
          onFile={setWatchedFile}
        />
        <div className="h-3" />
        <DropSlot
          file={ratingsFile}
          label="ratings.csv"
          sub="optional · improves ranking quality"
          onFile={setRatingsFile}
        />

        {parseStatus && (
          <div
            className="mt-5 flex gap-6"
            style={{
              padding: "14px 16px",
              borderRadius: 10,
              background: "rgba(232,165,92,0.06)",
              border: "1px solid rgba(232,165,92,0.18)",
            }}
          >
            <Stat n={String(parseStatus.total_watched)} l="watched" />
            <Stat n={String(parseStatus.total_rated)} l="rated" />
          </div>
        )}

        {error && (
          <div
            className="mt-3 ns-mono"
            style={{ color: "var(--ns-accent)", fontSize: 11.5 }}
          >
            ✗ {error}
          </div>
        )}

        <div className="h-5" />
        <button
          className="ns-btn ns-btn-primary w-full"
          disabled={!watchedFile}
          onClick={onParse}
        >
          {parseStatus ? "✓ Parsed · continue →" : "Parse & continue →"}
        </button>
      </div>
    </section>
  );
}

function DropSlot({
  label,
  sub,
  required,
  file,
  onFile,
}: {
  label: string;
  sub: string;
  required?: boolean;
  file: File | null;
  onFile: (f: File | null) => void;
}) {
  const filled = !!file;
  const [drag, setDrag] = useState(false);

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f && f.name.endsWith(".csv")) onFile(f);
      }}
      className="block cursor-pointer"
      style={{
        padding: "18px 20px",
        borderRadius: 12,
        border: `1.5px dashed ${
          drag || filled ? "var(--ns-accent)" : "var(--ns-border-strong)"
        }`,
        background: filled || drag ? "var(--ns-accent-glow)" : "rgba(0,0,0,0.2)",
        transition: "all 0.15s",
      }}
    >
      <input
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
      <div className="flex items-center gap-3.5">
        <div
          className="flex items-center justify-center shrink-0 ns-mono"
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: filled ? "var(--ns-accent)" : "rgba(255,240,220,0.06)",
            color: filled ? "#1a0f00" : "var(--ns-fg-mute)",
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {filled ? "✓" : "CSV"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="ns-mono" style={{ fontSize: 13, color: "var(--ns-fg)" }}>
              {label}
            </span>
            {required && (
              <span
                className="ns-mono"
                style={{ fontSize: 10, color: "var(--ns-accent)", letterSpacing: "0.12em" }}
              >
                REQUIRED
              </span>
            )}
          </div>
          <div
            className="truncate"
            style={{ fontSize: 12.5, color: "var(--ns-fg-mute)", marginTop: 2 }}
          >
            {file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : sub}
          </div>
        </div>
      </div>
    </label>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div>
      <div
        className="ns-display"
        style={{ fontSize: 22, color: "var(--ns-fg)", lineHeight: 1 }}
      >
        {n}
      </div>
      <div
        className="ns-mono"
        style={{
          fontSize: 9.5,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--ns-fg-mute)",
          marginTop: 4,
        }}
      >
        {l}
      </div>
    </div>
  );
}

// ── Prompt screen (between import and result) ──────────────────
function PromptScreen({
  request,
  setRequest,
  onSubmit,
  loading,
  error,
  parseStatus,
}: {
  request: string;
  setRequest: (s: string) => void;
  onSubmit: () => void;
  loading: boolean;
  error: string;
  parseStatus: { total_watched: number; total_rated: number } | null;
}) {
  return (
    <section className="ns-fade-in flex flex-col items-center justify-center px-16 pt-4 pb-16 max-w-[880px] mx-auto min-h-[calc(100vh-120px)]">
      <div className="text-center mb-9">
        <div className="ns-eyebrow mb-3.5">✦ &nbsp; History loaded</div>
        <h1
          className="ns-display m-0"
          style={{
            fontSize: 64,
            color: "var(--ns-fg)",
            lineHeight: 1,
            letterSpacing: "-0.02em",
          }}
        >
          What are we watching{" "}
          <span style={{ fontStyle: "italic", color: "var(--ns-accent)" }}>tonight?</span>
        </h1>
        {parseStatus && (
          <div className="mt-3" style={{ fontSize: 14, color: "var(--ns-fg-dim)" }}>
            {parseStatus.total_watched} watched · {parseStatus.total_rated} rated
          </div>
        )}
      </div>

      <div
        className="ns-glass w-full p-6"
        style={{ boxShadow: "var(--ns-shadow-2)" }}
      >
        <div className="flex gap-3.5 items-start">
          <div
            className="flex items-center justify-center shrink-0"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "var(--ns-accent-glow)",
              border: "1px solid var(--ns-accent)",
              color: "var(--ns-accent)",
              fontSize: 14,
            }}
          >
            ✦
          </div>
          <textarea
            className="ns-input pt-1"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="Describe what you want to watch — a mood, a feeling, a craving."
            rows={3}
            style={{ fontSize: 17, lineHeight: 1.5 }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />
        </div>

        <div className="mt-4 flex items-center justify-between gap-4">
          <span
            className="ns-mono"
            style={{ fontSize: 10.5, color: "var(--ns-fg-mute)", letterSpacing: "0.12em" }}
          >
            ⌘ ⏎ to send
          </span>
          <button
            className="ns-btn ns-btn-primary"
            onClick={onSubmit}
            disabled={!request.trim() || loading}
          >
            {loading ? (
              <>
                <span className="ns-pulse-dot" /> recommending…
              </>
            ) : (
              <>
                Recommend &nbsp;
                <span style={{ opacity: 0.5, fontSize: 11 }}>⏎</span>
              </>
            )}
          </button>
        </div>

        {loading && (
          <div className="mt-4">
            {/* unknown stepIdx in production — pin near rank step (3) for vibe */}
            <AgentStatus stepIdx={3} />
          </div>
        )}
        {error && (
          <div
            className="mt-3 ns-mono"
            style={{ color: "var(--ns-accent)", fontSize: 11.5 }}
          >
            ✗ {error}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Result screen ──────────────────────────────────────────────
function ResultScreen({ rec, request }: { rec: Recommendation; request: string }) {
  return (
    <section
      className="ns-fade-in grid items-center gap-14 px-20 pt-2 pb-9 max-w-[1280px] mx-auto"
      style={{ gridTemplateColumns: "320px 1fr" }}
    >
      {/* poster */}
      <div
        className="overflow-hidden"
        style={{
          aspectRatio: "2/3",
          width: 320,
          borderRadius: 8,
          boxShadow: "0 30px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(232,165,92,0.15)",
          transform: "rotate(-1.5deg)",
          position: "relative",
        }}
      >
        <Poster title={rec.title} year={rec.year} posterUrl={rec.poster_url} />
      </div>

      {/* details */}
      <div style={{ maxWidth: 640 }}>
        <div
          className="ns-eyebrow mb-3.5"
          style={{ color: "var(--ns-accent)" }}
        >
          ✦ &nbsp; TONIGHT&rsquo;S PICK
        </div>

        <h1
          className="ns-display m-0"
          style={{
            fontSize: 64,
            color: "var(--ns-fg)",
            lineHeight: 0.95,
            letterSpacing: "-0.02em",
          }}
        >
          {rec.title}
        </h1>

        <div
          className="ns-mono mt-4 flex gap-3.5 flex-wrap"
          style={{
            fontSize: 12,
            color: "var(--ns-fg-dim)",
            letterSpacing: "0.06em",
          }}
        >
          <span>{rec.year}</span>
        </div>

        {/* explanation — Claude's "why this" */}
        {rec.explanation && (
          <p
            className="mt-4"
            style={{
              fontSize: 19,
              lineHeight: 1.45,
              color: "var(--ns-fg)",
              fontFamily: "var(--ns-font-display)",
              fontStyle: "italic",
              maxWidth: 560,
            }}
          >
            &ldquo;{rec.explanation}&rdquo;
          </p>
        )}

        <div className="mt-6">
          <RatingsStrip
            imdb={rec.imdb_score}
            metascore={rec.metascore}
            rt={rec.rotten_tomatoes}
          />
        </div>

        {/* overview */}
        {rec.overview && (
          <div className="mt-6" style={{ maxWidth: 560 }}>
            <div className="ns-eyebrow mb-2">⟶ &nbsp; Overview</div>
            <p
              className="m-0"
              style={{
                fontSize: 14.5,
                lineHeight: 1.6,
                color: "var(--ns-fg-dim)",
              }}
            >
              {rec.overview}
            </p>
          </div>
        )}

        {/* request echo */}
        {request && (
          <div
            className="mt-6 ns-mono"
            style={{
              fontSize: 11,
              color: "var(--ns-fg-mute)",
              letterSpacing: "0.06em",
              maxWidth: 560,
            }}
          >
            ⟶ in response to: <span style={{ color: "var(--ns-fg-dim)" }}>&ldquo;{request}&rdquo;</span>
          </div>
        )}

        <div className="mt-7">
          <AgentStatus done />
        </div>
      </div>
    </section>
  );
}
