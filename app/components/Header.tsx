// app/components/Header.tsx
export function Header({ subtle = false }: { subtle?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 whitespace-nowrap">
      <div
        className="w-[22px] h-[22px] rounded-[4px] relative shrink-0"
        style={{ background: "var(--ns-accent)" }}
      >
        <div
          className="absolute rounded-[2px]"
          style={{ inset: 4, background: "var(--ns-bg)" }}
        />
        <div
          className="absolute left-1/2 top-1/2 w-1 h-1 rounded-full -translate-x-1/2 -translate-y-1/2"
          style={{ background: "var(--ns-accent)" }}
        />
      </div>
      <div className="flex items-baseline gap-1.5 whitespace-nowrap">
        <span className="ns-display text-[18px]" style={{ color: "var(--ns-fg)" }}>
          Next Showing
        </span>
        {!subtle && (
          <span
            className="ns-mono text-[10px]"
            style={{ color: "var(--ns-fg-mute)", letterSpacing: "0.12em" }}
          >
            v0.1
          </span>
        )}
      </div>
    </div>
  );
}
