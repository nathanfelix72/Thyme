import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import {
  downloadRecipeText,
  formatIngredientLine,
  recipePlainText,
} from "./helpers";
import { KeywordBadges } from "./KeywordBadges";
import type { Recipe } from "./types";

type IngredientDraft = {
  name: string;
  quantity: string;
  unit: string;
};

type EditDraft = {
  title: string;
  difficulty: "" | "easy" | "medium" | "hard";
  total_time_minutes: string;
  servings: string;
  cuisine: string;
  tags: string;
  ingredients: IngredientDraft[];
  steps: string[];
  raw_text: string;
};

type Props = {
  recipe: Recipe | null;
  onClose: () => void;
  onDelete?: (recipeId: string, title: string) => void;
  onSave?: (recipe: Recipe) => void;
  onUpdated?: (recipe: Recipe) => void;
  /** Persist edits via PUT + reindex (library recipes). */
  persistEdits?: boolean;
  deleting?: boolean;
  saving?: boolean;
  saved?: boolean;
};

type AssistKind = "summarize" | "side" | "scale" | null;

function ingredientLines(recipe: Recipe): string[] {
  if (recipe.ingredients.length > 0) {
    return recipe.ingredients.map(formatIngredientLine);
  }
  return (recipe.ingredient_keywords || []).filter(Boolean);
}

function assistPayload(recipe: Recipe) {
  return {
    title: recipe.title,
    raw_text: recipe.raw_text || "",
    ingredients: recipe.ingredients || [],
    steps: recipe.steps || [],
    servings: recipe.servings,
    cuisine: recipe.cuisine,
    difficulty: recipe.difficulty,
  };
}

function toDraft(recipe: Recipe): EditDraft {
  return {
    title: recipe.title || "",
    difficulty: recipe.difficulty || "",
    total_time_minutes:
      recipe.total_time_minutes != null ? String(recipe.total_time_minutes) : "",
    servings: recipe.servings != null ? String(recipe.servings) : "",
    cuisine: recipe.cuisine || "",
    tags: (recipe.tags || []).join(", "),
    ingredients:
      recipe.ingredients.length > 0
        ? recipe.ingredients.map((ing) => ({
            name: ing.name || "",
            quantity: ing.quantity || "",
            unit: ing.unit || "",
          }))
        : (recipe.ingredient_keywords || []).map((name) => ({
            name,
            quantity: "",
            unit: "",
          })),
    steps: recipe.steps.length > 0 ? [...recipe.steps] : [""],
    raw_text: recipe.raw_text || "",
  };
}

function parseOptionalInt(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return null;
  return Math.round(n);
}

export function RecipeDrawer({
  recipe,
  onClose,
  onDelete,
  onSave,
  onUpdated,
  persistEdits,
  deleting = false,
  saving = false,
  saved = false,
}: Props) {
  const canPersist = persistEdits ?? Boolean(onDelete);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [sourceOpen, setSourceOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [assistBusy, setAssistBusy] = useState<AssistKind>(null);
  const [assistError, setAssistError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [sides, setSides] = useState<{ items: string[]; notes: string } | null>(
    null,
  );
  const [scaled, setScaled] = useState<{
    servings: number;
    lines: string[];
    notes: string;
  } | null>(null);
  const [scaleTo, setScaleTo] = useState(4);

  useEffect(() => {
    setChecked({});
    setSourceOpen(true);
    setCopied(false);
    setEditing(false);
    setDraft(recipe ? toDraft(recipe) : null);
    setEditBusy(false);
    setEditError(null);
    setAssistBusy(null);
    setAssistError(null);
    setSummary(null);
    setSides(null);
    setScaled(null);
    setScaleTo(recipe?.servings && recipe.servings > 0 ? recipe.servings : 4);
  }, [recipe?.recipe_id, recipe?.servings, recipe?.updated_at]);

  useEffect(() => {
    if (!recipe) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (editing) {
          setEditing(false);
          setDraft(toDraft(recipe));
          setEditError(null);
        } else {
          onClose();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [recipe, onClose, editing]);

  const lines = useMemo(
    () => (recipe ? ingredientLines(recipe) : []),
    [recipe],
  );

  if (!recipe || !draft) return null;
  const active = recipe;

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(recipePlainText(active));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  async function runAssist(kind: Exclude<AssistKind, null>) {
    setAssistBusy(kind);
    setAssistError(null);
    try {
      if (kind === "summarize") {
        const res = await apiFetch("/api/recipes/assist/summarize", {
          method: "POST",
          body: JSON.stringify(assistPayload(active)),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Summarize failed");
        setSummary(String(data.summary || "").trim());
      } else if (kind === "side") {
        const res = await apiFetch("/api/recipes/assist/suggest-side", {
          method: "POST",
          body: JSON.stringify(assistPayload(active)),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Side suggestions failed");
        setSides({
          items: Array.isArray(data.sides) ? data.sides.map(String) : [],
          notes: String(data.notes || ""),
        });
      } else {
        const target = Math.min(48, Math.max(1, Number(scaleTo) || 4));
        const res = await apiFetch("/api/recipes/assist/scale", {
          method: "POST",
          body: JSON.stringify({
            ...assistPayload(active),
            target_servings: target,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Scale failed");
        const ings = Array.isArray(data.ingredients) ? data.ingredients : [];
        setScaled({
          servings: Number(data.target_servings) || target,
          lines: ings.map(
            (ing: {
              name?: string;
              quantity?: string | null;
              unit?: string | null;
            }) =>
              formatIngredientLine({
                name: String(ing.name || ""),
                quantity: ing.quantity ?? null,
                unit: ing.unit ?? null,
              }),
          ),
          notes: String(data.notes || ""),
        });
      }
    } catch (err) {
      setAssistError(err instanceof Error ? err.message : String(err));
    } finally {
      setAssistBusy(null);
    }
  }

  function startEdit() {
    setDraft(toDraft(active));
    setEditError(null);
    setEditing(true);
  }

  function cancelEdit() {
    setDraft(toDraft(active));
    setEditError(null);
    setEditing(false);
  }

  async function saveEdit() {
    if (!draft.title.trim()) {
      setEditError("Title is required.");
      return;
    }
    setEditBusy(true);
    setEditError(null);
    const ingredients = draft.ingredients
      .map((ing) => ({
        name: ing.name.trim(),
        quantity: ing.quantity.trim() || null,
        unit: ing.unit.trim() || null,
      }))
      .filter((ing) => ing.name);
    const steps = draft.steps.map((s) => s.trim()).filter(Boolean);
    const tags = draft.tags
      .split(/[,;\n]+/)
      .map((t) => t.trim())
      .filter(Boolean);
    const payload = {
      title: draft.title.trim(),
      difficulty: draft.difficulty || null,
      total_time_minutes: parseOptionalInt(draft.total_time_minutes),
      servings: parseOptionalInt(draft.servings),
      cuisine: draft.cuisine.trim() || null,
      tags,
      ingredients,
      steps,
      raw_text: draft.raw_text,
    };

    try {
      let next: Recipe = {
        ...active,
        ...payload,
        difficulty: payload.difficulty,
        total_time_minutes: payload.total_time_minutes,
        servings: payload.servings,
        cuisine: payload.cuisine,
        ingredient_keywords: ingredients.map((i) => i.name),
      };

      if (canPersist) {
        const res = await apiFetch(`/api/recipes/${active.recipe_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Save failed");
        next = data as Recipe;
      }

      onUpdated?.(next);
      setDraft(toDraft(next));
      setEditing(false);
      setScaleTo(next.servings && next.servings > 0 ? next.servings : 4);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setEditBusy(false);
    }
  }

  const meta = [
    active.difficulty,
    active.total_time_minutes != null
      ? `${active.total_time_minutes} min`
      : null,
    active.cuisine,
    active.servings != null ? `serves ${active.servings}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="drawer-root" role="presentation">
      <button
        type="button"
        className="drawer-backdrop"
        aria-label="Close recipe"
        onClick={onClose}
      />
      <aside
        className="recipe-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="recipe-drawer-title"
      >
        <header className="recipe-drawer-header">
          <div className="recipe-drawer-header-top">
            <p className="eyebrow">{editing ? "Edit" : "Cook"}</p>
            <button type="button" className="text-btn" onClick={onClose}>
              Close
            </button>
          </div>

          {editing ? (
            <label className="recipe-edit-field">
              Title
              <input
                value={draft.title}
                onChange={(e) =>
                  setDraft({ ...draft, title: e.target.value })
                }
                autoFocus
              />
            </label>
          ) : (
            <h2 id="recipe-drawer-title">{active.title}</h2>
          )}

          {!editing ? (
            <>
              <p className="recipe-meta">
                {active.source}
                {active.source_url ? (
                  <>
                    {" "}
                    ·{" "}
                    <a href={active.source_url} target="_blank" rel="noreferrer">
                      source
                    </a>
                  </>
                ) : null}
                {meta ? ` · ${meta}` : ""}
              </p>
              <KeywordBadges keywords={active.ingredient_keywords} limit={12} />
            </>
          ) : null}

          <div className="recipe-drawer-actions">
            {editing ? (
              <>
                <button
                  type="button"
                  className="drawer-action-btn"
                  disabled={editBusy}
                  onClick={() => void saveEdit()}
                >
                  {editBusy
                    ? "Saving…"
                    : canPersist
                      ? "Save & reindex"
                      : "Save draft"}
                </button>
                <button
                  type="button"
                  className="drawer-action-btn"
                  disabled={editBusy}
                  onClick={cancelEdit}
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="drawer-action-btn"
                  onClick={startEdit}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="drawer-action-btn"
                  onClick={onCopy}
                >
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  type="button"
                  className="drawer-action-btn"
                  onClick={() => downloadRecipeText(active)}
                >
                  Download
                </button>
                {onSave ? (
                  <button
                    type="button"
                    className="drawer-action-btn"
                    disabled={saving || saved}
                    onClick={() => onSave(active)}
                  >
                    {saved ? "In library" : saving ? "Saving…" : "Add to library"}
                  </button>
                ) : null}
                {onDelete ? (
                  <button
                    type="button"
                    className="drawer-action-btn danger"
                    disabled={deleting}
                    onClick={() => onDelete(active.recipe_id, active.title)}
                  >
                    {deleting ? "Deleting…" : "Delete"}
                  </button>
                ) : null}
              </>
            )}
          </div>
          {editError ? <p className="assist-error">{editError}</p> : null}
        </header>

        <div className="recipe-drawer-body">
          {editing ? (
            <>
              <section className="cook-section">
                <h3>Details</h3>
                <div className="recipe-edit-grid">
                  <label className="recipe-edit-field">
                    Difficulty
                    <select
                      value={draft.difficulty}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          difficulty: e.target.value as EditDraft["difficulty"],
                        })
                      }
                    >
                      <option value="">—</option>
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </label>
                  <label className="recipe-edit-field">
                    Time (minutes)
                    <input
                      type="number"
                      min={0}
                      max={1440}
                      value={draft.total_time_minutes}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          total_time_minutes: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="recipe-edit-field">
                    Servings
                    <input
                      type="number"
                      min={1}
                      max={48}
                      value={draft.servings}
                      onChange={(e) =>
                        setDraft({ ...draft, servings: e.target.value })
                      }
                    />
                  </label>
                  <label className="recipe-edit-field">
                    Cuisine
                    <input
                      value={draft.cuisine}
                      onChange={(e) =>
                        setDraft({ ...draft, cuisine: e.target.value })
                      }
                      placeholder="italian"
                    />
                  </label>
                </div>
                <label className="recipe-edit-field">
                  Tags
                  <input
                    value={draft.tags}
                    onChange={(e) =>
                      setDraft({ ...draft, tags: e.target.value })
                    }
                    placeholder="weeknight, pasta"
                  />
                </label>
              </section>

              <section className="cook-section">
                <div className="recipe-edit-section-head">
                  <h3>Ingredients</h3>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        ingredients: [
                          ...draft.ingredients,
                          { name: "", quantity: "", unit: "" },
                        ],
                      })
                    }
                  >
                    Add
                  </button>
                </div>
                <ul className="recipe-edit-list">
                  {draft.ingredients.map((ing, idx) => (
                    <li key={`ing-${idx}`} className="recipe-edit-ingredient">
                      <input
                        className="recipe-edit-qty"
                        placeholder="Qty"
                        value={ing.quantity}
                        onChange={(e) => {
                          const ingredients = [...draft.ingredients];
                          ingredients[idx] = {
                            ...ing,
                            quantity: e.target.value,
                          };
                          setDraft({ ...draft, ingredients });
                        }}
                      />
                      <input
                        className="recipe-edit-unit"
                        placeholder="Unit"
                        value={ing.unit}
                        onChange={(e) => {
                          const ingredients = [...draft.ingredients];
                          ingredients[idx] = { ...ing, unit: e.target.value };
                          setDraft({ ...draft, ingredients });
                        }}
                      />
                      <input
                        className="recipe-edit-name"
                        placeholder="Ingredient"
                        value={ing.name}
                        onChange={(e) => {
                          const ingredients = [...draft.ingredients];
                          ingredients[idx] = { ...ing, name: e.target.value };
                          setDraft({ ...draft, ingredients });
                        }}
                      />
                      <button
                        type="button"
                        className="text-btn danger"
                        aria-label="Remove ingredient"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            ingredients: draft.ingredients.filter(
                              (_, i) => i !== idx,
                            ),
                          })
                        }
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="cook-section">
                <div className="recipe-edit-section-head">
                  <h3>Steps</h3>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() =>
                      setDraft({ ...draft, steps: [...draft.steps, ""] })
                    }
                  >
                    Add
                  </button>
                </div>
                <ol className="recipe-edit-steps">
                  {draft.steps.map((step, idx) => (
                    <li key={`step-${idx}`}>
                      <textarea
                        rows={2}
                        value={step}
                        onChange={(e) => {
                          const steps = [...draft.steps];
                          steps[idx] = e.target.value;
                          setDraft({ ...draft, steps });
                        }}
                      />
                      <button
                        type="button"
                        className="text-btn danger"
                        aria-label="Remove step"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            steps: draft.steps.filter((_, i) => i !== idx),
                          })
                        }
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="cook-section">
                <h3>Source text</h3>
                <textarea
                  className="recipe-edit-raw"
                  rows={8}
                  value={draft.raw_text}
                  onChange={(e) =>
                    setDraft({ ...draft, raw_text: e.target.value })
                  }
                />
              </section>
            </>
          ) : (
            <>
              <section className="cook-section assist-section">
                <h3>Quick help</h3>
                <div className="assist-actions">
                  <button
                    type="button"
                    className="drawer-action-btn"
                    disabled={assistBusy !== null}
                    onClick={() => void runAssist("summarize")}
                  >
                    {assistBusy === "summarize" ? "Summarizing…" : "Summarize"}
                  </button>
                  <button
                    type="button"
                    className="drawer-action-btn"
                    disabled={assistBusy !== null}
                    onClick={() => void runAssist("side")}
                  >
                    {assistBusy === "side" ? "Suggesting…" : "Suggest sides"}
                  </button>
                  <div className="assist-scale-row">
                    <label className="assist-scale-label">
                      Scale to
                      <input
                        type="number"
                        min={1}
                        max={48}
                        value={scaleTo}
                        disabled={assistBusy !== null}
                        onChange={(e) => setScaleTo(Number(e.target.value))}
                      />
                    </label>
                    <button
                      type="button"
                      className="drawer-action-btn"
                      disabled={assistBusy !== null}
                      onClick={() => void runAssist("scale")}
                    >
                      {assistBusy === "scale" ? "Scaling…" : "Scale"}
                    </button>
                  </div>
                </div>
                {assistError ? (
                  <p className="assist-error">{assistError}</p>
                ) : null}
                {summary ? (
                  <div className="assist-result">
                    <p className="assist-result-label">Summary</p>
                    <p>{summary}</p>
                  </div>
                ) : null}
                {sides ? (
                  <div className="assist-result">
                    <p className="assist-result-label">Sides</p>
                    <ul>
                      {sides.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    {sides.notes ? (
                      <p className="assist-notes">{sides.notes}</p>
                    ) : null}
                  </div>
                ) : null}
                {scaled ? (
                  <div className="assist-result">
                    <p className="assist-result-label">
                      Scaled to {scaled.servings}
                    </p>
                    <ul>
                      {scaled.lines.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                    {scaled.notes ? (
                      <p className="assist-notes">{scaled.notes}</p>
                    ) : null}
                  </div>
                ) : null}
              </section>

              {lines.length > 0 ? (
                <section className="cook-section">
                  <h3>Ingredients</h3>
                  <ul className="cook-checklist">
                    {lines.map((line, idx) => {
                      const key = `${idx}-${line}`;
                      return (
                        <li key={key}>
                          <label className="cook-check">
                            <input
                              type="checkbox"
                              checked={Boolean(checked[key])}
                              onChange={(e) =>
                                setChecked((prev) => ({
                                  ...prev,
                                  [key]: e.target.checked,
                                }))
                              }
                            />
                            <span
                              className={checked[key] ? "is-done" : undefined}
                            >
                              {line}
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}

              {active.steps.length > 0 ? (
                <section className="cook-section">
                  <h3>Steps</h3>
                  <ol className="cook-steps">
                    {active.steps.map((step, idx) => (
                      <li key={idx}>
                        <span className="cook-step-num">{idx + 1}</span>
                        <p>{step}</p>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}

              {active.raw_text?.trim() ? (
                <section className="cook-section">
                  <button
                    type="button"
                    className="source-toggle"
                    aria-expanded={sourceOpen}
                    onClick={() => setSourceOpen((o) => !o)}
                  >
                    Source text
                    <span aria-hidden="true">{sourceOpen ? "▾" : "▸"}</span>
                  </button>
                  {sourceOpen ? (
                    <pre className="raw-recipe cook-source">
                      {active.raw_text}
                    </pre>
                  ) : null}
                </section>
              ) : null}

              {!lines.length &&
              !active.steps.length &&
              !active.raw_text?.trim() ? (
                <p className="lede">This recipe has no cookable content yet.</p>
              ) : null}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
