// app/components/AgentStatus.tsx
"use client";

import { useState } from "react";

export const AGENT_STEPS = [
  { id: "decompose", agent: "Claude", label: "decomposing request" },
  { id: "search", agent: "Gemini Flash", label: "searching TMDB · 50 candidates" },
  { id: "filter", agent: "local", label: "filtering watched" },
  { id: "rank", agent: "Ollama", label: "ranking against history" },
  { id: "explain", agent: "Claude", label: "writing explanation" },
];

interface Props {
  /** which step the pipeline is currently on (0..AGENT_STEPS.length) */
  stepIdx?: number;
  /** finished? if true, shows green dot + ready summary */
  done?: boolean;
}

export function AgentStatus({ stepIdx = AGENT_STEPS.length, done = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const current = AGENT_STEPS[Math.min(stepIdx, AGENT_STEPS.length - 1)];

  return (
    <div className="w-full">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2.5 ns-mono cursor-pointer transition-colors"
        style={{
          background: "transparent",
          border: "1px solid var(--ns-border)",
          borderRadius: 999,
          padding: "10px 16px",
          color: "var(--ns-fg-dim)",
          fontSize: 11.5,
          letterSpacing: "0.04em",
        }}
      >
        {done ? (
          <span
            className="block rounded-full"
            style={{ width: 6, height: 6, background: "var(--ns-good)" }}
          />
        ) : (
          <span className="ns-pulse-dot" />
        )}
        <span style={{ color: "var(--ns-accent)" }}>{current.agent}</span>
        <span>·</span>
        <span className="flex-1 text-left">
          {done ? "ready · 5 agents" : current.label}
        </span>
        <span style={{ opacity: 0.5, fontSize: 10 }}>{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div
          className="ns-mono mt-2"
          style={{
            padding: "12px 16px",
            background: "rgba(0,0,0,0.3)",
            border: "1px solid var(--ns-border)",
            borderRadius: 12,
            fontSize: 11,
            lineHeight: 1.8,
          }}
        >
          {AGENT_STEPS.map((s, i) => {
            const state = i < stepIdx ? "done" : i === stepIdx && !done ? "active" : i < stepIdx || done ? "done" : "pending";
            return (
              <div
                key={s.id}
                className="flex gap-2.5"
                style={{
                  color:
                    state === "pending"
                      ? "var(--ns-fg-mute)"
                      : state === "active"
                      ? "var(--ns-fg)"
                      : "var(--ns-fg-dim)",
                }}
              >
                <span style={{ width: 16, textAlign: "right" }}>
                  {state === "done" ? "✓" : state === "active" ? "▸" : "·"}
                </span>
                <span
                  style={{
                    width: 110,
                    color: "var(--ns-accent)",
                    opacity: state === "pending" ? 0.4 : 0.85,
                  }}
                >
                  {s.agent}
                </span>
                <span className="flex-1">{s.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
