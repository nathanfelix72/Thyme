import { Link } from "react-router-dom";

const areas = [
  {
    to: "/find",
    num: "01",
    title: "Find",
    blurb: "Search your library with filters and similarity.",
  },
  {
    to: "/library",
    num: "02",
    title: "Library",
    blurb: "Browse saved recipes and open them in cook mode.",
  },
  {
    to: "/upload",
    num: "03",
    title: "Upload",
    blurb: "Add recipes from files or a filtered web search.",
  },
  {
    to: "/plan",
    num: "04",
    title: "Plan",
    blurb: "Spread meals across the week with recipe links.",
  },
  {
    to: "/shop",
    num: "05",
    title: "Shop",
    blurb: "Build the grocery list and order from major stores.",
  },
  {
    to: "/budget",
    num: "06",
    title: "Budget",
    blurb: "Keep meals and groceries within a Plaid-backed budget.",
  },
];

export function Home() {
  return (
    <section className="page-panel home">
      <p className="eyebrow">AI meal-planning agent</p>
      <h1>Thyme</h1>
      <p className="lede">
        From “I have no time, I just need to eat out” to a planned, shopped,
        on-budget week.
      </p>
      <div className="home-split">
        <div>
          <h2>The problem</h2>
          <p>
            Choosing meals, grocery shopping, and budgeting are separate
            chores — so time, food, and money get wasted.
          </p>
        </div>
        <div>
          <h2>The solution</h2>
          <p>
            One AI assistant that understands your needs in plain language and
            handles the rest.
          </p>
        </div>
      </div>
      <ul className="area-list">
        {areas.map((area) => (
          <li key={area.to}>
            <Link to={area.to} className="area-card">
              <span className="area-num">{area.num}</span>
              <strong>{area.title}</strong>
              <span>{area.blurb}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
