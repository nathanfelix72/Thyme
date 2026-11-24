import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

type Provider = "ollama" | "openai" | "anthropic";

type LlmTask =
  | "web_clean"
  | "summarize"
  | "suggest_side"
  | "scale"
  | "segment";

type TaskProviders = Record<LlmTask, Provider | null>;

type AiSettingsState = {
  provider: Provider;
  ollama_model: string;
  task_providers: TaskProviders;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  openai_key_hint: string | null;
  anthropic_key_hint: string | null;
};

const TASK_LABELS: { task: LlmTask; label: string; hint: string }[] = [
  {
    task: "web_clean",
    label: "Web recipe cleanup",
    hint: "Turns Tavily search hits into clean ingredient/step previews.",
  },
  {
    task: "summarize",
    label: "Summarize",
    hint: "Short recipe summary on the recipe detail tools.",
  },
  {
    task: "suggest_side",
    label: "Suggest sides",
    hint: "Side-dish ideas for a main recipe.",
  },
  {
    task: "scale",
    label: "Scale servings",
    hint: "Rescales ingredient quantities.",
  },
  {
    task: "segment",
    label: "Upload segmentation",
    hint: "Finds recipe titles when uploading multi-recipe documents.",
  },
];

const emptyTasks = (): TaskProviders => ({
  web_clean: null,
  summarize: null,
  suggest_side: null,
  scale: null,
  segment: null,
});

const empty: AiSettingsState = {
  provider: "ollama",
  ollama_model: "qwen2.5:7b",
  task_providers: emptyTasks(),
  has_openai_key: false,
  has_anthropic_key: false,
  openai_key_hint: null,
  anthropic_key_hint: null,
};

function normalize(data: Partial<AiSettingsState>): AiSettingsState {
  return {
    ...empty,
    ...data,
    task_providers: { ...emptyTasks(), ...(data.task_providers || {}) },
  };
}

export function AiSettings() {
  const [settings, setSettings] = useState<AiSettingsState>(empty);
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [testProvider, setTestProvider] = useState<Provider | "">("");
  const [status, setStatus] = useState<string | null>(null);
  const [testReply, setTestReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await apiFetch("/api/settings");
    if (!res.ok) throw new Error(await res.text());
    const data = (await res.json()) as AiSettingsState;
    setSettings(normalize(data));
  }

  useEffect(() => {
    load().catch((err: Error) => setStatus(err.message));
  }, []);

  function setTaskProvider(task: LlmTask, value: string) {
    setSettings({
      ...settings,
      task_providers: {
        ...settings.task_providers,
        [task]: value === "" ? null : (value as Provider),
      },
    });
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const body: Record<string, unknown> = {
        provider: settings.provider,
        ollama_model: settings.ollama_model,
        task_providers: settings.task_providers,
      };
      if (openaiKey.trim()) body.openai_api_key = openaiKey.trim();
      if (anthropicKey.trim()) body.anthropic_api_key = anthropicKey.trim();

      const res = await apiFetch("/api/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as AiSettingsState;
      setSettings(normalize(data));
      setOpenaiKey("");
      setAnthropicKey("");
      setStatus("Saved.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onTest() {
    setBusy(true);
    setTestReply(null);
    setStatus(null);
    try {
      const payload: Record<string, unknown> = {
        message: "Say hello in one short sentence as Thyme.",
      };
      if (testProvider) payload.provider = testProvider;

      const res = await apiFetch("/api/settings/test-chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Test failed");
      setTestReply(`${data.provider}: ${data.reply}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Test failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="home">
      <p className="eyebrow">Account · BYOK</p>
      <h1>AI settings</h1>
      <p className="lede">
        Choose Ollama locally or paste your own OpenAI / Anthropic key. Pick a
        default, then override individual LLM tasks. Allergy excludes and theme
        live on <Link to="/profile">Profile</Link>.
      </p>

      <form className="settings-form" onSubmit={onSave}>
        <label>
          Default provider
          <select
            value={settings.provider}
            onChange={(e) =>
              setSettings({
                ...settings,
                provider: e.target.value as Provider,
              })
            }
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI (BYOK)</option>
            <option value="anthropic">Anthropic (BYOK)</option>
          </select>
          <span className="field-hint">
            Used for Test chat and any task left on “Use default”.
          </span>
        </label>

        <label>
          Ollama model
          <input
            value={settings.ollama_model}
            onChange={(e) =>
              setSettings({ ...settings, ollama_model: e.target.value })
            }
            placeholder="qwen2.5:7b"
          />
        </label>

        <fieldset className="settings-fieldset">
          <legend>Per-task models</legend>
          <p className="field-hint settings-fieldset-lede">
            Example: summarize with Ollama, suggest sides with Anthropic.
          </p>
          {TASK_LABELS.map(({ task, label, hint }) => (
            <label key={task}>
              {label}
              <select
                value={settings.task_providers[task] ?? ""}
                onChange={(e) => setTaskProvider(task, e.target.value)}
              >
                <option value="">Use default ({settings.provider})</option>
                <option value="ollama">Ollama (local)</option>
                <option value="openai">OpenAI (BYOK)</option>
                <option value="anthropic">Anthropic (BYOK)</option>
              </select>
              <span className="field-hint">{hint}</span>
            </label>
          ))}
        </fieldset>

        <label>
          OpenAI API key
          <input
            type="password"
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
            placeholder={
              settings.has_openai_key
                ? `Saved ${settings.openai_key_hint}`
                : "sk-…"
            }
            autoComplete="off"
          />
        </label>

        <label>
          Anthropic API key
          <input
            type="password"
            value={anthropicKey}
            onChange={(e) => setAnthropicKey(e.target.value)}
            placeholder={
              settings.has_anthropic_key
                ? `Saved ${settings.anthropic_key_hint}`
                : "sk-ant-…"
            }
            autoComplete="off"
          />
        </label>

        <div className="settings-actions">
          <button type="submit" disabled={busy}>
            Save
          </button>
          <label className="settings-test-provider">
            Test as
            <select
              value={testProvider}
              onChange={(e) =>
                setTestProvider(e.target.value as Provider | "")
              }
            >
              <option value="">Default ({settings.provider})</option>
              <option value="ollama">Ollama</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </label>
          <button type="button" disabled={busy} onClick={onTest}>
            Test chat
          </button>
        </div>
      </form>

      {status ? <p className="settings-status">{status}</p> : null}
      {testReply ? (
        <div className="stub-box">
          <p className="stub-label">Test reply</p>
          <p>{testReply}</p>
        </div>
      ) : null}
    </section>
  );
}
