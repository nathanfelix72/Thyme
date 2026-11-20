import { Link } from "react-router-dom";

const areas = [
  {
    to: "/understand",
    num: "01",
    title: "Understand",
    blurb: "RAG recipe chat — next sprint: upload your own recipes.",
  },
  {
    to: "/plan",
    num: "02",
    title: "Plan",
    blurb: "Spread meals across the week with recipe links.",
  },
  {
    to: "/shop",
    num: "03",
    title: "Shop",
    blurb: "Build the grocery list and order from major stores.",
  },
  {
    to: "/budget",
    num: "04",
    title: "Budget",
    blurb: "Keep meals and groceries within a Plaid-backed budget.",
  },
];

export function Home() {
  return (
    <section className="home">
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
