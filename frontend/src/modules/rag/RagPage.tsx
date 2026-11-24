import { useState } from "react";
import type { FormEvent } from "react";
import { apiFetch } from "../../lib/api";

type RecipeSource = {
  id: string;
  title: string;
  description: string;
  prep_minutes: number;
  ingredients: string[];
  instructions: string[];
  tags: string[];
  relevance: number;
};

type ChatResponse = {
  answer: string;
  recipes: RecipeSource[];
};

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  recipes?: RecipeSource[];
};

const suggestions = [
  "What can I make with potatoes?",
  "I need a quick vegetarian dinner",
  "Find something with beans and lots of fiber",
];

export function RagPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(rawMessage: string) {
    const message = rawMessage.trim();
    if (!message || busy) return;

    setMessages((current) => [
      ...current,
      { id: Date.now(), role: "user", content: message },
    ]);
    setDraft("");
    setBusy(true);
    setError(null);

    try {
      const response = await apiFetch("/api/rag/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      const data = (await response.json()) as ChatResponse | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in data && data.detail
            ? data.detail
            : "Thyme couldn't search recipes right now.",
        );
      }

      const result = data as ChatResponse;
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: result.answer,
          recipes: result.recipes,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recipe search failed.");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft);
  }

  return (
    <section className="rag-page">
      <div className="rag-intro">
        <p className="eyebrow">01 · Understand</p>
        <h1>Find a recipe that fits.</h1>
        <p className="lede">
          Tell Thyme what you have, how much time you have, or what sounds good.
          It will search the sample recipes and show what it used.
        </p>
      </div>

      <div className="rag-workspace">
        <section className="rag-conversation" aria-label="Recipe search chat">
          {messages.length === 0 ? (
            <div className="rag-empty">
              <span className="rag-spark" aria-hidden="true">✳</span>
              <h2>What sounds good?</h2>
              <p>Try one of these, or ask in your own words.</p>
              <div className="rag-suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="rag-suggestion"
                    disabled={busy}
                    onClick={() => void sendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="rag-messages" aria-live="polite">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`rag-message rag-message-${message.role}`}
                >
                  <p className="rag-message-label">
                    {message.role === "user" ? "You" : "Thyme"}
                  </p>
                  <p className="rag-message-text">{message.content}</p>
                  {message.recipes?.length ? (
                    <div className="rag-recipe-list">
                      {message.recipes.map((recipe) => (
                        <details className="rag-recipe" key={recipe.id}>
                          <summary>
                            <span>
                              <strong>{recipe.title}</strong>
                              <small>{recipe.prep_minutes} min · {recipe.tags.slice(0, 2).join(" · ")}</small>
                            </span>
                            <span className="rag-recipe-open">Details</span>
                          </summary>
                          <p className="rag-recipe-description">{recipe.description}</p>
                          <h3>Ingredients</h3>
                          <ul>
                            {recipe.ingredients.map((ingredient) => (
                              <li key={ingredient}>{ingredient}</li>
                            ))}
                          </ul>
                          <h3>Steps</h3>
                          <ol>
                            {recipe.instructions.map((instruction) => (
                              <li key={instruction}>{instruction}</li>
                            ))}
                          </ol>
                        </details>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
              {busy ? (
                <p className="rag-loading" role="status">Searching the recipe collection…</p>
              ) : null}
            </div>
          )}

          {error ? <p className="rag-error" role="alert">{error}</p> : null}

          <form className="rag-composer" onSubmit={onSubmit}>
            <label className="rag-sr-only" htmlFor="recipe-query">
              Describe the recipe you want
            </label>
            <textarea
              id="recipe-query"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="I have potatoes and 30 minutes…"
              maxLength={500}
              rows={2}
              disabled={busy}
            />
            <button type="submit" disabled={busy || !draft.trim()}>
              {busy ? "Searching…" : "Find recipes"}
            </button>
          </form>
          <p className="rag-footnote">
            Phase 1 uses a small sample collection. Recipe imports come later.
          </p>
        </section>

        <aside className="rag-side-note">
          <p className="rag-side-kicker">A little more than keywords</p>
          <h2>Search by what you mean.</h2>
          <p>
            Thyme compares your request with recipe meaning and ingredients, then
            keeps its suggestions tied to the recipes it found.
          </p>
          <div className="rag-side-divider" />
          <p className="rag-side-kicker">Phase 1</p>
          <ul>
            <li>Natural language text search</li>
            <li>Recipe matches with source details</li>
            <li>Grounded, concise suggestions</li>
          </ul>
        </aside>
      </div>
    </section>
  );
}
