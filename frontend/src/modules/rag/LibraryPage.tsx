import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import { AuthGate } from "./AuthGate";
import { errorDetail } from "./helpers";
import { KeywordBadges } from "./KeywordBadges";
import { RecipeDrawer } from "./RecipeDrawer";
import type { Notice, Recipe, RecipeSummary } from "./types";

type SourceFilter = "all" | "upload" | "web";

function letterKey(title: string): string {
  const ch = (title || "").trim().charAt(0).toUpperCase();
  return ch >= "A" && ch <= "Z" ? ch : "#";
}

const LETTERS = [
  "All",
  "#",
  ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ".split(""),
] as const;

export function LibraryPage() {
  const { ready, signedIn, email } = useAuth();
  const [library, setLibrary] = useState<RecipeSummary[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [loadingRecipe, setLoadingRecipe] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [letterTab, setLetterTab] = useState<string>("All");
  const [checkedIds, setCheckedIds] = useState<Set<string>>(() => new Set());

  const loadLibrary = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await apiFetch("/api/recipes/list");
      if (res.status === 401) {
        throw new Error("Sign in required to use your recipe library.");
      }
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { recipes: RecipeSummary[] };
      setLibrary(data.recipes);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    if (!ready || !signedIn) return;
    loadLibrary().catch((err: Error) =>
      setNotice({ kind: "error", text: err.message }),
    );
  }, [loadLibrary, ready, signedIn]);

  const sourceScoped = useMemo(() => {
    const q = query.trim().toLowerCase();
    return library.filter((r) => {
      if (sourceFilter !== "all" && r.source !== sourceFilter) return false;
      if (!q) return true;
      const hay = [
        r.title,
        r.cuisine || "",
        r.difficulty || "",
        r.source_doc || "",
        r.preview || "",
        ...(r.ingredient_keywords || []),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [library, query, sourceFilter]);

  const letterCounts = useMemo(() => {
    const counts: Record<string, number> = { All: sourceScoped.length };
    for (const r of sourceScoped) {
      const key = letterKey(r.title);
      counts[key] = (counts[key] || 0) + 1;
    }
    return counts;
  }, [sourceScoped]);

  const filtered = useMemo(() => {
    if (letterTab === "All") return sourceScoped;
    return sourceScoped.filter((r) => letterKey(r.title) === letterTab);
  }, [sourceScoped, letterTab]);

  useEffect(() => {
    if (letterTab === "All") return;
    if ((letterCounts[letterTab] || 0) === 0) setLetterTab("All");
  }, [letterCounts, letterTab]);

  const allFilteredSelected =
    filtered.length > 0 && filtered.every((r) => checkedIds.has(r.recipe_id));

  function toggleOne(recipeId: string) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(recipeId)) next.delete(recipeId);
      else next.add(recipeId);
      return next;
    });
  }

  function toggleAllFiltered() {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        for (const r of filtered) next.delete(r.recipe_id);
      } else {
        for (const r of filtered) next.add(r.recipe_id);
      }
      return next;
    });
  }

  async function openRecipe(recipeId: string) {
    setLoadingRecipe(true);
    setNotice({ kind: "progress", text: "Loading recipe…" });
    try {
      const res = await apiFetch(`/api/recipes/${recipeId}`);
      const data = await res.json();
      if (!res.ok) throw new Error(errorDetail(data, "Could not load recipe"));
      setSelected(data as Recipe);
      setNotice(null);
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Could not load recipe",
      });
    } finally {
      setLoadingRecipe(false);
    }
  }

  async function deleteIds(ids: string[], label: string) {
    if (!ids.length) return;
    if (
      !window.confirm(
        ids.length === 1
          ? `Delete “${label}” from your library? This cannot be undone.`
          : `Delete ${ids.length} recipes from your library? This cannot be undone.`,
      )
    ) {
      return;
    }
    setDeleting(true);
    setNotice({
      kind: "progress",
      text:
        ids.length === 1
          ? `Deleting “${label}”…`
          : `Deleting ${ids.length} recipes…`,
    });
    const failed: string[] = [];
    let ok = 0;
    for (const recipeId of ids) {
      try {
        const res = await apiFetch(`/api/recipes/${recipeId}`, {
          method: "DELETE",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(errorDetail(data, "Delete failed"));
        ok += 1;
      } catch {
        failed.push(recipeId);
      }
    }
    setLibrary((prev) =>
      prev.filter((r) => !ids.includes(r.recipe_id) || failed.includes(r.recipe_id)),
    );
    setCheckedIds((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (!failed.includes(id)) next.delete(id);
      }
      return next;
    });
    if (
      selected &&
      ids.includes(selected.recipe_id) &&
      !failed.includes(selected.recipe_id)
    ) {
      setSelected(null);
    }
    if (failed.length && ok === 0) {
      setNotice({ kind: "error", text: "Delete failed." });
    } else if (failed.length) {
      setNotice({
        kind: "error",
        text: `Deleted ${ok}; ${failed.length} failed.`,
      });
    } else {
      setNotice({
        kind: "success",
        text: ok === 1 ? `Deleted “${label}”.` : `Deleted ${ok} recipes.`,
      });
    }
    setDeleting(false);
  }

  async function onDelete(recipeId: string, title: string) {
    await deleteIds([recipeId], title);
  }

  async function onBulkDelete() {
    const ids = [...checkedIds];
    const first = library.find((r) => r.recipe_id === ids[0]);
    await deleteIds(ids, first?.title || "recipes");
  }

  const busy = loadingRecipe || deleting;
  const selectedCount = checkedIds.size;
  const drawerLabel =
    letterTab === "All" ? "All cards" : `Drawer ${letterTab}`;

  return (
    <AuthGate eyebrow="Library" title="Recipe box">
      <section className="page-panel library-page">
        <div className="page-header-row">
          <div>
            <p className="eyebrow">Library</p>
            <h1>Recipe box</h1>
            <p className="lede">
              {email ? `${email} · ` : ""}
              {library.length} cards
              {filtered.length !== library.length
                ? ` · ${filtered.length} in this drawer`
                : ""}
              {loadingList ? " · refreshing…" : ""}
            </p>
          </div>
          <div className="page-header-links">
            <Link to="/find" className="text-btn">
              Find
            </Link>
            <Link to="/upload" className="primary-link-btn">
              Upload
            </Link>
          </div>
        </div>

        {notice ? (
          <p
            className={`inline-notice kind-${notice.kind}`}
            role="status"
            aria-live="polite"
          >
            {notice.text}
          </p>
        ) : null}

        {library.length === 0 && !loadingList ? (
          <div className="stub-box empty-results">
            <p className="stub-label">Empty box</p>
            <p>
              No recipe cards yet.{" "}
              <Link to="/upload">Upload a PDF or text file</Link>, or pull some
              in from <Link to="/find">Find</Link>.
            </p>
          </div>
        ) : (
          <div className="recipe-box">
            <div className="recipe-box-lid">
              <div className="recipe-box-lid-label">
                <span>Thyme</span>
                <strong>Recipe Box</strong>
              </div>
              <input
                className="library-search recipe-box-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Find a card…"
                aria-label="Search library"
              />
              <div
                className="recipe-box-source"
                role="group"
                aria-label="Source drawer"
              >
                {(
                  [
                    ["all", "All"],
                    ["upload", "Uploads"],
                    ["web", "Web"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={
                      sourceFilter === value
                        ? "recipe-box-source-btn is-active"
                        : "recipe-box-source-btn"
                    }
                    onClick={() => setSourceFilter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div
              className="recipe-box-tabs"
              role="tablist"
              aria-label="Letter drawers"
            >
              {LETTERS.map((letter) => {
                const count = letterCounts[letter] || 0;
                const disabled = letter !== "All" && count === 0;
                return (
                  <button
                    key={letter}
                    type="button"
                    role="tab"
                    aria-selected={letterTab === letter}
                    disabled={disabled}
                    className={
                      letterTab === letter
                        ? "recipe-box-tab is-active"
                        : "recipe-box-tab"
                    }
                    onClick={() => setLetterTab(letter)}
                    title={
                      disabled
                        ? `No cards for ${letter}`
                        : `${letter} (${count})`
                    }
                  >
                    <span>{letter === "All" ? "∗" : letter}</span>
                  </button>
                );
              })}
            </div>

            <div className="recipe-box-drawer" role="tabpanel">
              <div className="recipe-box-drawer-rail">
                <span className="recipe-box-drawer-tag">{drawerLabel}</span>
                <div className="library-bulk-bar recipe-box-bulk">
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={allFilteredSelected}
                      onChange={toggleAllFiltered}
                      disabled={filtered.length === 0 || busy}
                    />
                    Select drawer
                  </label>
                  <span>
                    {selectedCount
                      ? `${selectedCount} selected`
                      : `${filtered.length} card${filtered.length === 1 ? "" : "s"}`}
                  </span>
                  <button
                    type="button"
                    className="text-btn danger"
                    disabled={selectedCount === 0 || busy}
                    onClick={() => void onBulkDelete()}
                  >
                    {deleting
                      ? "Deleting…"
                      : `Delete selected (${selectedCount})`}
                  </button>
                </div>
              </div>

              {filtered.length === 0 ? (
                <div className="recipe-box-empty">
                  <p>This drawer is empty.</p>
                  <p>Try another tab, clear search, or upload more cards.</p>
                </div>
              ) : (
                <ul className="recipe-card-deck">
                  {filtered.map((r, idx) => {
                    const isChecked = checkedIds.has(r.recipe_id);
                    return (
                      <li
                        key={r.recipe_id}
                        className={
                          isChecked
                            ? "index-card is-selected"
                            : "index-card"
                        }
                        style={{ animationDelay: `${Math.min(idx, 12) * 35}ms` }}
                      >
                        <div className="index-card-tab" aria-hidden="true">
                          {letterKey(r.title)}
                        </div>
                        <label className="index-card-check">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            disabled={busy}
                            onChange={() => toggleOne(r.recipe_id)}
                            aria-label={`Select ${r.title}`}
                          />
                        </label>
                        <button
                          type="button"
                          className="index-card-body"
                          disabled={busy}
                          onClick={() => openRecipe(r.recipe_id)}
                        >
                          <strong>{r.title}</strong>
                          <span className="index-card-meta">
                            <span
                              className={`source-badge source-${r.source === "web" ? "web" : "local"}`}
                            >
                              {r.source}
                            </span>
                            {r.difficulty ? ` · ${r.difficulty}` : ""}
                            {r.total_time_minutes != null
                              ? ` · ${r.total_time_minutes} min`
                              : ""}
                            {r.cuisine ? ` · ${r.cuisine}` : ""}
                          </span>
                          <KeywordBadges
                            keywords={r.ingredient_keywords}
                            limit={5}
                          />
                          {r.preview ? (
                            <span className="index-card-preview">
                              {r.preview}
                            </span>
                          ) : null}
                        </button>
                        <button
                          type="button"
                          className="text-btn danger index-card-delete"
                          disabled={busy}
                          onClick={() => onDelete(r.recipe_id, r.title)}
                        >
                          Remove
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      <RecipeDrawer
        recipe={selected}
        onClose={() => setSelected(null)}
        onDelete={onDelete}
        deleting={deleting}
        persistEdits
        onUpdated={(next) => {
          setSelected(next);
          setLibrary((prev) =>
            prev.map((r) =>
              r.recipe_id === next.recipe_id
                ? {
                    ...r,
                    title: next.title,
                    difficulty: next.difficulty,
                    total_time_minutes: next.total_time_minutes,
                    cuisine: next.cuisine,
                    ingredient_keywords: next.ingredient_keywords,
                    preview: (next.raw_text || "")
                      .trim()
                      .replace(/\n/g, " ")
                      .slice(0, 160),
                    source_url: next.source_url,
                    source_doc: next.source_doc,
                  }
                : r,
            ),
          );
        }}
      />
    </AuthGate>
  );
}
