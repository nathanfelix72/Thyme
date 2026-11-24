import { useCallback, useEffect, useState } from "react";
import type { FormEvent, MouseEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../lib/api";
import { ActivityStatus } from "./ActivityStatus";
import { AuthGate } from "./AuthGate";
import {
  errorDetail,
  nextActivityId,
  parseTags,
  previewText,
} from "./helpers";
import { KeywordBadges } from "./KeywordBadges";
import { RecipeDrawer } from "./RecipeDrawer";
import type {
  ActivityEvent,
  Notice,
  Recipe,
  SearchHit,
  SearchResponse,
} from "./types";

export function UploadPage() {
  const { email } = useAuth();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [lastCount, setLastCount] = useState<number | null>(null);

  const [includeIngredients, setIncludeIngredients] = useState("");
  const [excludeIngredients, setExcludeIngredients] = useState("");
  const [maxTime, setMaxTime] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [cuisine, setCuisine] = useState("");
  const [query, setQuery] = useState("");
  const [alwaysExclude, setAlwaysExclude] = useState<string[]>([]);
  const [webSearching, setWebSearching] = useState(false);
  const [webHits, setWebHits] = useState<SearchHit[]>([]);
  const [webSearched, setWebSearched] = useState(false);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());

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

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setNotice({ kind: "error", text: "Choose a PDF or TXT file first." });
      return;
    }
    setUploading(true);
    setUploadPercent(1);
    setLastCount(null);
    setNotice({
      kind: "progress",
      text: `Starting upload of ${file.name}…`,
    });
    pushActivity({
      stage: "start",
      message: `Upload started: ${file.name}`,
      percent: 1,
    });
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await apiFetch("/api/recipes/upload-progress", {
        method: "POST",
        body,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(errorDetail(data, "Upload failed"));
      }
      if (!res.body) throw new Error("No progress stream from server");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalCount = 0;
      let sawError: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let evt: Record<string, unknown>;
          try {
            evt = JSON.parse(line);
          } catch {
            continue;
          }
          const percent =
            typeof evt.percent === "number" ? evt.percent : undefined;
          if (typeof percent === "number") {
            setUploadPercent(Math.max(0, Math.min(100, percent)));
          }
          const message =
            typeof evt.message === "string" ? evt.message : "Working…";
          const stage =
            typeof evt.stage === "string" ? evt.stage : undefined;
          const prompt_preview =
            typeof evt.prompt_preview === "string"
              ? evt.prompt_preview
              : undefined;

          if (stage === "error") {
            sawError = message || "Upload failed";
            setNotice({ kind: "error", text: sawError });
            pushActivity({ stage: "error", message: sawError });
            continue;
          }
          if (stage === "done") {
            finalCount = Number(evt.uploaded ?? evt.found ?? 0);
            setUploadPercent(100);
            pushActivity({
              stage: "done",
              message: message || `Done — ${finalCount} recipes`,
              percent: 100,
            });
            continue;
          }
          pushActivity({
            stage,
            message,
            prompt_preview,
            percent,
          });
          setNotice({ kind: "progress", text: message });
        }
      }

      if (sawError) throw new Error(sawError);
      setLastCount(finalCount);
      setNotice({
        kind: "success",
        text:
          finalCount > 0
            ? `Done — saved ${finalCount} recipe${finalCount === 1 ? "" : "s"} from ${file.name}.`
            : `Finished parsing ${file.name}, but no recipes were found.`,
      });
      setFile(null);
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Upload failed",
      });
    } finally {
      setUploading(false);
      setUploadPercent(0);
    }
  }

  async function onWebSearch(event: FormEvent) {
    event.preventDefault();
    const includes = parseTags(includeIngredients);
    const q = query.trim();
    if (
      !q &&
      includes.length === 0 &&
      !cuisine.trim() &&
      !difficulty &&
      !maxTime.trim()
    ) {
      setNotice({
        kind: "error",
        text: "Set at least one filter or a semantic hint before searching the web.",
      });
      return;
    }
    setWebSearching(true);
    setWebSearched(false);
    setWebHits([]);
    setSelected(null);
    setSavedIds(new Set());
    setNotice({ kind: "progress", text: "Searching the web…" });
    pushActivity({
      stage: "web",
      message: `Web search with filters (${q || includes.join(", ") || "filters only"})`,
    });
    try {
      const res = await apiFetch("/api/rag/search", {
        method: "POST",
        body: JSON.stringify({
          include_ingredients: includes,
          exclude_ingredients: parseTags(excludeIngredients),
          max_time_minutes: maxTime.trim() ? Number(maxTime) : null,
          difficulty: difficulty || null,
          cuisine: cuisine.trim() || null,
          query: q || null,
          include_library: false,
          include_web: true,
          limit: 8,
        }),
      });
      const data = (await res.json()) as SearchResponse;
      if (!res.ok) throw new Error(errorDetail(data, "Web search failed"));
      const hits = (data.results || []).filter((h) => h.origin === "web");
      setWebHits(hits);
      setWebSearched(true);
      const searchEvents: ActivityEvent[] = (data.activity || []).map(
        (item) => ({
          id: nextActivityId(),
          at: Date.now(),
          stage: typeof item.stage === "string" ? item.stage : "web",
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
      const previewCount = data.web_previews ?? hits.length;
      setNotice({
        kind: hits.length ? "success" : "info",
        text:
          hits.length > 0
            ? `${previewCount} web preview${previewCount === 1 ? "" : "s"} — add the ones you want.`
            : data.web_queried
              ? `Web query “${data.web_query || "—"}” returned nothing that matched your filters.`
              : "No web recipes matched. Try different filters.",
      });
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Web search failed",
      });
    } finally {
      setWebSearching(false);
    }
  }

  async function onSave(recipe: Recipe) {
    if (savedIds.has(recipe.recipe_id)) return;
    setSavingId(recipe.recipe_id);
    setNotice({ kind: "progress", text: `Adding “${recipe.title}”…` });
    try {
      const res = await apiFetch("/api/recipes/import", {
        method: "POST",
        body: JSON.stringify(recipe),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(errorDetail(data, "Could not save recipe"));
      setSavedIds((prev) => new Set(prev).add(recipe.recipe_id));
      setNotice({
        kind: "success",
        text: `“${recipe.title}” added to your library.`,
      });
      pushActivity({
        stage: "library",
        message: `Saved “${recipe.title}” to library`,
      });
    } catch (err) {
      setNotice({
        kind: "error",
        text: err instanceof Error ? err.message : "Could not save recipe",
      });
    } finally {
      setSavingId(null);
    }
  }

  const busy = uploading || webSearching || Boolean(savingId);

  return (
    <AuthGate eyebrow="Upload" title="Add recipes">
      <section className="page-panel">
        <div className="page-header-row">
          <div>
            <p className="eyebrow">Upload</p>
            <h1>Add recipes</h1>
            <p className="lede">
              Signed in as {email || "you"}. Build your library from a file or a
              filtered web search — Find only searches what you save here.
            </p>
          </div>
          <div className="page-header-links">
            <Link to="/find" className="text-btn">
              Find
            </Link>
            <Link to="/library" className="text-btn">
              Library
            </Link>
          </div>
        </div>

        <div className="upload-split">
          <form
            className="settings-form tool-panel upload-panel"
            onSubmit={onUpload}
          >
            <h2>From a file</h2>
            <p className="panel-hint">
              PDF, TXT, or Markdown. After parsing, recipes appear in your
              library.
            </p>
            <label>
              Choose file
              <input
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain"
                disabled={busy}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {file ? (
              <p className="file-chip">
                Selected: <strong>{file.name}</strong> (
                {(file.size / 1024).toFixed(1)} KB)
              </p>
            ) : (
              <p className="file-chip muted">No file selected yet.</p>
            )}
            <div className="settings-actions">
              <button type="submit" disabled={busy || !file}>
                {uploading ? "Segmenting…" : "Upload & parse"}
              </button>
            </div>
          </form>

          <form
            className="settings-form tool-panel upload-panel"
            onSubmit={onWebSearch}
          >
            <h2>From the web</h2>
            <p className="panel-hint">
              One web lookup using the same filters as Find. Previews stay out of
              your library until you add them.
            </p>
            <label>
              Include ingredients
              <input
                value={includeIngredients}
                onChange={(e) => setIncludeIngredients(e.target.value)}
                placeholder="chicken, rice"
                disabled={busy}
              />
            </label>
            <label>
              Exclude ingredients (this search)
              <input
                value={excludeIngredients}
                onChange={(e) => setExcludeIngredients(e.target.value)}
                placeholder="optional — e.g. cilantro"
                disabled={busy}
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
                  disabled={busy}
                />
              </label>
              <label>
                Difficulty
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  disabled={busy}
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
                disabled={busy}
              />
            </label>
            <label>
              Semantic hint (optional)
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="weeknight comfort food"
                disabled={busy}
              />
            </label>
            <div className="settings-actions">
              <button type="submit" disabled={busy}>
                {webSearching ? "Searching…" : "Search the web"}
              </button>
            </div>
          </form>
        </div>

        <ActivityStatus
          notice={notice}
          activity={activity}
          progressPercent={uploading ? uploadPercent : null}
          idleText="Upload a file or search the web with filters."
          onClear={() => setActivity([])}
        />

        {lastCount != null && lastCount > 0 ? (
          <div className="stub-box" style={{ marginTop: "1.25rem" }}>
            <p className="stub-label">Ready</p>
            <p>
              {lastCount} recipe{lastCount === 1 ? "" : "s"} saved.{" "}
              <Link to="/library">Open your library</Link> or{" "}
              <Link to="/find">search on Find</Link>.
            </p>
          </div>
        ) : null}

        {webSearched && webHits.length === 0 && !webSearching ? (
          <div className="stub-box empty-results">
            <p className="stub-label">No web matches</p>
            <p>Nothing matched those filters. Try loosening them.</p>
          </div>
        ) : null}

        {webHits.length > 0 ? (
          <div className="results-block">
            <h2>Web previews</h2>
            <ul className="recipe-card-list">
              {webHits.map((hit) => {
                const isSaved = savedIds.has(hit.recipe.recipe_id);
                return (
                  <li key={hit.recipe.recipe_id}>
                    <div className="recipe-card-wrap">
                      <button
                        type="button"
                        className="recipe-card"
                        disabled={busy}
                        onClick={() => setSelected(hit.recipe)}
                      >
                        <span className="recipe-card-top">
                          <strong>{hit.recipe.title}</strong>
                          <span className="source-badge source-web">
                            {isSaved ? "saved" : "preview"}
                          </span>
                        </span>
                        <span className="recipe-meta">
                          {hit.recipe.difficulty || "medium"} ·{" "}
                          {hit.recipe.total_time_minutes != null
                            ? `${hit.recipe.total_time_minutes} min`
                            : "30 min"}
                          {hit.recipe.cuisine
                            ? ` · ${hit.recipe.cuisine}`
                            : ""}{" "}
                          · {(hit.score * 100).toFixed(0)}%
                        </span>
                        <KeywordBadges
                          keywords={hit.recipe.ingredient_keywords}
                        />
                        <span className="recipe-preview">
                          {previewText(hit.recipe)}
                        </span>
                        <span className="recipe-reason">{hit.reason}</span>
                      </button>
                      <button
                        type="button"
                        className="recipe-card-add"
                        disabled={busy || isSaved}
                        onClick={(e: MouseEvent) => {
                          e.stopPropagation();
                          void onSave(hit.recipe);
                        }}
                      >
                        {isSaved
                          ? "In library"
                          : savingId === hit.recipe.recipe_id
                            ? "Saving…"
                            : "Add to library"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </section>

      <RecipeDrawer
        recipe={selected}
        onClose={() => setSelected(null)}
        onSave={
          selected && !savedIds.has(selected.recipe_id)
            ? (recipe) => {
                void onSave(recipe);
              }
            : undefined
        }
        saving={Boolean(savingId)}
        saved={selected ? savedIds.has(selected.recipe_id) : false}
        persistEdits={selected ? savedIds.has(selected.recipe_id) : false}
        onUpdated={(next) => {
          setSelected(next);
          setWebHits((prev) =>
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
