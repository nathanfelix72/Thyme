export function KeywordBadges({
  keywords,
  limit = 6,
}: {
  keywords: string[] | undefined;
  limit?: number;
}) {
  const list = (keywords || []).filter(Boolean).slice(0, limit);
  if (!list.length) return null;
  return (
    <span className="keyword-row">
      {list.map((k) => (
        <span key={k} className="keyword-badge">
          {k}
        </span>
      ))}
      {(keywords || []).length > limit ? (
        <span className="keyword-badge more">+</span>
      ) : null}
    </span>
  );
}
