import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import { ActivityStatus } from "./ActivityStatus";
import { AuthGate } from "./AuthGate";
import { errorDetail, nextActivityId, parseTags, previewText } from "./helpers";
import { KeywordBadges } from "./KeywordBadges";
import { RecipeDrawer } from "./RecipeDrawer";
import type {
  ActivityEvent,
  Notice,
  Recipe,
  SearchHit,
  SearchResponse,
} from "./types";

export function FindPage() {
  const { email } = useAuth();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [includeIngredients, setIncludeIngredients] = useState("");
  const [excludeIngredients, setExcludeIngredients] = useState("");
  const [maxTime, setMaxTime] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [cuisine, setCuisine] = useState("");
  const [query, setQuery] = useState("");
  const [alwaysExclude, setAlwaysExclude] = useState<string[]>([]);
  const [results, setResults] = useState<SearchHit[]>([]);
  const [searchMeta, setSearchMeta] = useState<string | null>(null);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);

  useEffect(() => {
    apiFetch("/api/settings")
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        setAlwaysExclude(data.always_exclude_ingredients || []);
      })
      .catch(() => {
        /* optional */
      });
  }, []);

  const pushActivity = useCallback(
    (event: Partial<ActivityEvent> & { message: string }) => {
      const entry: ActivityEvent = {
        id: nextActivityId(),
        at: Date.now(),
        stage: event.stage,
        message: event.message,
        prompt_preview: event.prompt_preview,
        rejected: event.rejected,
        web_query: event.web_query,
        percent: event.percent,
      };
      setActivity((prev) => [...prev.slice(-80), entry]);
    },
    [],
  );

  async function onDelete(recipeId: string, title: string) {
    if (
      !window.confirm(
        `Delete “${title}” from your library? This cannot be undone.`,
      )
    ) {
      return;
    }
    setDeletingId(recipeId);
    setNotice({ kind: "progress", text: `Deleting “${title}”…` });
    try {
      const res = await apiFetch(`/api/recipes/${recipeId}`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errorDetail(data, "Delete failed"));
      setResults((prev) => prev.filter((h) => h.recipe.recipe_id !== recipeId));
      if (selected?.recipe_id === recipeId) setSelected(null);
      setNotice({ kind: "success", text: `Deleted “${title}”.` });
      pushActivity({ stage: "library", message: `Deleted “${title}”` });
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Delete failed",
      });
    } finally {
      setDeletingId(null);
    }
  }

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    setSearching(true);
    setSearched(false);
    setSearchMeta(null);
    setSelected(null);
    setResults([]);
    setNotice({ kind: "progress", text: "Searching your library…" });
    pushActivity({ stage: "search", message: "Library search started" });
    try {
      const payload = {
        include_ingredients: parseTags(includeIngredients),
        exclude_ingredients: parseTags(excludeIngredients),
        max_time_minutes: maxTime.trim() ? Number(maxTime) : null,
        difficulty: difficulty || null,
        cuisine: cuisine.trim() || null,
        query: query.trim() || null,
        include_library: true,
        include_web: false,
        limit: 8,
      };
      const res = await apiFetch("/api/rag/search", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = (await res.json()) as SearchResponse;
      if (!res.ok) throw new Error(errorDetail(data, "Search failed"));
      setResults(data.results);
      setSearched(true);
      const searchEvents: ActivityEvent[] = (data.activity || []).map(
        (item) => ({
          id: nextActivityId(),
          at: Date.now(),
          stage: typeof item.stage === "string" ? item.stage : "search",
          message:
            typeof item.message === "string"
              ? item.message
              : JSON.stringify(item),
          prompt_preview:
            typeof item.prompt_preview === "string"
              ? item.prompt_preview
              : undefined,
          rejected: Boolean(item.rejected),
          web_query:
            typeof item.web_query === "string" ? item.web_query : undefined,
        }),
      );
      if (searchEvents.length) {
        setActivity((prev) => [...prev.slice(-80), ...searchEvents].slice(-80));
      }
      setSearchMeta(`${data.results.length} match(es) from your library`);
      setNotice({
        kind: data.results.length ? "success" : "info",
        text:
          data.results.length > 0
            ? `Found ${data.results.length} recipe${data.results.length === 1 ? "" : "s"} by filter + embedding similarity.`
            : "No library matches. Add recipes on Upload, or loosen filters.",
      });
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Search failed",
      });
    } finally {
      setSearching(false);
    }
  }

  const busy = searching || Boolean(deletingId);

  return (
    <AuthGate eyebrow="01 · Find" title="Find recipes">
      <section className="page-panel">
        <div className="page-header-row">
          <div>
            <p className="eyebrow">01 · Find</p>
            <h1>Find recipes</h1>
            <p className="lede">
              Signed in as {email || "you"}. Hard filters plus embedding
              similarity over your library. Add recipes on Upload first.
            </p>
          </div>
          <div className="page-header-links">
            <Link to="/library" className="text-btn">
              Library
            </Link>
            <Link to="/upload" className="primary-link-btn">
              Upload
            </Link>
          </div>
        </div>

        <form className="settings-form tool-panel" onSubmit={onSearch}>
          <h2>Library filters</h2>
          <label>
            Include ingredients
            <input
              value={includeIngredients}
              onChange={(e) => setIncludeIngredients(e.target.value)}
              placeholder="chicken, rice"
              disabled={searching}
            />
          </label>
          <label>
            Exclude ingredients (this search)
            <input
              value={excludeIngredients}
              onChange={(e) => setExcludeIngredients(e.target.value)}
              placeholder="optional — e.g. cilantro"
              disabled={searching}
            />
          </label>
          {alwaysExclude.length > 0 ? (
            <p className="panel-hint">
              Always excluding from Profile: {alwaysExclude.join(", ")}
            </p>
          ) : (
            <p className="panel-hint">
              Tip: set permanent allergy excludes under Profile.
            </p>
          )}
          <div className="filter-row">
            <label>
              Max time (minutes)
              <input
                type="number"
                min={1}
                value={maxTime}
                onChange={(e) => setMaxTime(e.target.value)}
                placeholder="any"
                disabled={searching}
              />
            </label>
            <label>
              Difficulty
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                disabled={searching}
              >
                <option value="">Any</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
          </div>
          <label>
            Cuisine
            <input
              value={cuisine}
              onChange={(e) => setCuisine(e.target.value)}
              placeholder="optional"
              disabled={searching}
            />
          </label>
          <label>
            Semantic hint (optional)
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="weeknight comfort food"
              disabled={searching}
            />
          </label>
          <p className="panel-hint">
            Used as the embedding query for similarity ranking (with your
            filters).
          </p>
          <div className="settings-actions">
            <button type="submit" disabled={searching}>
              {searching ? "Searching…" : "Search library"}
            </button>
          </div>
          <ActivityStatus
            notice={notice}
            activity={activity}
            idleText="Set filters, then search your library."
            onClear={() => setActivity([])}
          />
        </form>

        {searchMeta ? <p className="settings-status">{searchMeta}</p> : null}

        {searched && results.length === 0 && !searching ? (
          <div className="stub-box empty-results">
            <p className="stub-label">No matches</p>
            <p>
              Nothing in your library ranked for those filters.{" "}
              <Link to="/upload">Add recipes</Link> or loosen the filters.
            </p>
          </div>
        ) : null}

        {results.length > 0 ? (
          <div className="results-block">
            <h2>Matches</h2>
            <ul className="recipe-card-list">
              {results.map((hit) => (
                <li key={hit.recipe.recipe_id}>
                  <button
                    type="button"
                    className="recipe-card"
                    disabled={busy}
                    onClick={() => setSelected(hit.recipe)}
                  >
                    <span className="recipe-card-top">
                      <strong>{hit.recipe.title}</strong>
                      <span className="source-badge source-local">
                        {hit.recipe.source}
                      </span>
                    </span>
                    <span className="recipe-meta">
                      {hit.recipe.difficulty || "medium"} ·{" "}
                      {hit.recipe.total_time_minutes != null
                        ? `${hit.recipe.total_time_minutes} min`
                        : "30 min"}
                      {hit.recipe.cuisine ? ` · ${hit.recipe.cuisine}` : ""} ·{" "}
                      {(hit.score * 100).toFixed(0)}%
                    </span>
                    <KeywordBadges keywords={hit.recipe.ingredient_keywords} />
                    <span className="recipe-preview">
                      {previewText(hit.recipe)}
                    </span>
                    <span className="recipe-reason">{hit.reason}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <RecipeDrawer
        recipe={selected}
        onClose={() => setSelected(null)}
        onDelete={onDelete}
        deleting={Boolean(deletingId)}
        persistEdits
        onUpdated={(next) => {
          setSelected(next);
          setResults((prev) =>
            prev.map((hit) =>
              hit.recipe.recipe_id === next.recipe_id
                ? { ...hit, recipe: next }
                : hit,
            ),
          );
        }}
      />
    </AuthGate>
  );
}
