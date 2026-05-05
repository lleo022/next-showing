// app/components/RatingCell.tsx
interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  divider?: boolean;
}

export function RatingCell({ label, value, sub, accent, divider }: Props) {
  return (
    <div
      style={{
        padding: "12px 20px",
        borderLeft: divider ? "1px solid var(--ns-border)" : "none",
        minWidth: 96,
      }}
    >
      <div
        className="ns-mono"
        style={{
          fontSize: 9.5,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: "var(--ns-fg-mute)",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-[3px]">
        <span
          className="ns-display"
          style={{
            fontSize: 26,
            color: accent ? "var(--ns-accent)" : "var(--ns-fg)",
          }}
        >
          {value}
        </span>
        {sub && (
          <span
            className="ns-mono"
            style={{ fontSize: 11, color: "var(--ns-fg-mute)" }}
          >
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

export function RatingsStrip({
  imdb,
  metascore,
  rt,
  predicted,
}: {
  imdb?: string | number;
  metascore?: string | number;
  rt?: string | number;
  predicted?: string | number;
}) {
  const fmt = (v: string | number | undefined) =>
    v === undefined || v === null || v === "" || v === "N/A" ? "—" : String(v);
  return (
    <div
      className="flex w-fit overflow-hidden"
      style={{
        background: "rgba(0,0,0,0.4)",
        backdropFilter: "blur(20px)",
        border: "1px solid var(--ns-border)",
        borderRadius: 12,
      }}
    >
      <RatingCell label="IMDb" value={fmt(imdb)} sub="/10" />
      <RatingCell label="Metacritic" value={fmt(metascore)} sub="/100" divider />
      <RatingCell label="RT" value={fmt(rt)} divider />
      {predicted !== undefined && (
        <RatingCell label="Predicted" value={fmt(predicted)} sub="/5" accent divider />
      )}
    </div>
  );
}
