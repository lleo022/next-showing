"use client";

import { useState } from "react";

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

export default function TestPage() {
  const [watchedFile, setWatchedFile] = useState<File | null>(null);
  const [ratingsFile, setRatingsFile] = useState<File | null>(null);
  const [parseStatus, setParseStatus] = useState<string>("");
  const [parseError, setParseError] = useState<string>("");
  const [watched, setWatched] = useState<unknown[] | null>(null);

  const [request, setRequest] = useState("");
  const [loading, setLoading] = useState(false);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recommendError, setRecommendError] = useState<string>("");

  async function handleParse() {
    if (!watchedFile) return;
    setParseError("");
    setParseStatus("");

    const form = new FormData();
    form.append("watched_file", watchedFile);
    if (ratingsFile) form.append("ratings_file", ratingsFile);

    try {
      const res = await fetch("http://localhost:8000/parse", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setWatched(data.watched);
      setParseStatus(`Loaded ${data.total_watched} watched, ${data.total_rated} rated`);
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
      const res = await fetch("http://localhost:8000/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: request.trim(), watched }),
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

  return (
    <main className="max-w-2xl mx-auto p-8 space-y-10">

      {/* Section 1 — CSV Upload */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold border-b pb-2">1. CSV Upload</h2>
        <div className="space-y-2">
          <label className="block text-sm font-medium">
            watched.csv <span className="text-red-500">*</span>
          </label>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setWatchedFile(e.target.files?.[0] ?? null)}
            className="block"
          />
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium">ratings.csv (optional)</label>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setRatingsFile(e.target.files?.[0] ?? null)}
            className="block"
          />
        </div>
        <button
          onClick={handleParse}
          disabled={!watchedFile}
          className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-40"
        >
          Parse CSV
        </button>
        {parseStatus && <p className="text-green-700">{parseStatus}</p>}
        {parseError && <p className="text-red-600">{parseError}</p>}
      </section>

      {/* Section 2 — Movie Request */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold border-b pb-2">2. Movie Request</h2>
        <textarea
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          placeholder="Describe what you want to watch..."
          rows={4}
          className="w-full border rounded p-2 text-sm"
        />
        <button
          onClick={handleRecommend}
          disabled={!watched || !request.trim() || loading}
          className="px-4 py-2 bg-green-600 text-white rounded disabled:opacity-40 flex items-center gap-2"
        >
          {loading && (
            <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          Get Recommendation
        </button>
        {recommendError && <p className="text-red-600">{recommendError}</p>}
      </section>

      {/* Section 3 — Result */}
      {recommendation && (
        <section className="space-y-4">
          <h2 className="text-xl font-bold border-b pb-2">3. Result</h2>
          <h1 className="text-3xl font-bold">
            {recommendation.title}{" "}
            <span className="text-gray-500 text-2xl">({recommendation.year})</span>
          </h1>
          {recommendation.poster_url && (
            <img
              src={recommendation.poster_url}
              alt={recommendation.title}
              style={{ maxWidth: 200 }}
              className="rounded"
            />
          )}
          <div className="flex gap-6 text-sm">
            <span>
              <span className="font-medium">IMDb</span> {recommendation.imdb_score}
            </span>
            <span>
              <span className="font-medium">Metascore</span> {recommendation.metascore}
            </span>
            <span>
              <span className="font-medium">RT</span> {recommendation.rotten_tomatoes}
            </span>
          </div>
          <p>{recommendation.explanation}</p>
          <p className="text-sm text-gray-500">{recommendation.overview}</p>
        </section>
      )}
    </main>
  );
}
