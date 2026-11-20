type ModulePlaceholderProps = {
  num: string;
  title: string;
  folder: string;
  summary: string;
};

export function ModulePlaceholder({
  num,
  title,
  folder,
  summary,
}: ModulePlaceholderProps) {
  return (
    <section className="placeholder">
      <p className="eyebrow">
        {num} · {title}
      </p>
      <h1>{title}</h1>
      <p className="lede">{summary}</p>
      <div className="stub-box">
        <p className="stub-label">Team folder</p>
        <code>{folder}</code>
        <p>Stub page — implement this area without touching other modules.</p>
      </div>
    </section>
  );
}
