// app/components/Poster.tsx
// Renders TMDB poster_url when present; else stripey placeholder.

interface PosterProps {
  title: string;
  year?: number | string;
  posterUrl?: string;
  small?: boolean;
  className?: string;
}

export function Poster({ title, year, posterUrl, small = false, className = "" }: PosterProps) {
  if (posterUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={posterUrl}
        alt={title}
        className={`w-full h-full object-cover ${className}`}
      />
    );
  }
  return (
    <div className={`ns-poster-ph w-full h-full ${className}`}>
      <div
        className="absolute inset-0 flex flex-col justify-end"
        style={{ padding: small ? 8 : 20 }}
      >
        {!small && (
          <div
            className="ns-mono mb-1.5"
            style={{
              fontSize: 9,
              letterSpacing: "0.2em",
              color: "rgba(232,165,92,0.7)",
            }}
          >
            POSTER {year ? `· ${year}` : ""}
          </div>
        )}
        <div
          className="ns-display"
          style={{
            fontSize: small ? 11 : 22,
            color: "rgba(244,236,224,0.92)",
            lineHeight: 1.05,
            textShadow: "0 2px 12px rgba(0,0,0,0.6)",
          }}
        >
          {title}
        </div>
      </div>
    </div>
  );
}
