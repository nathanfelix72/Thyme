import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { apiFetch } from "../lib/api";

type Provider = "ollama" | "openai" | "anthropic";

type Settings = {
  user_id: string;
  provider: Provider;
  ollama_model: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  openai_key_hint: string | null;
  anthropic_key_hint: string | null;
};

const empty: Settings = {
  user_id: "local-dev",
  provider: "ollama",
  ollama_model: "qwen2.5:7b",
  has_openai_key: false,
  has_anthropic_key: false,
  openai_key_hint: null,
  anthropic_key_hint: null,
};

export function Settings() {
  const [settings, setSettings] = useState<Settings>(empty);
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [testReply, setTestReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await apiFetch("/api/settings");
    if (!res.ok) throw new Error(await res.text());
    setSettings(await res.json());
  }

  useEffect(() => {
    load().catch((err: Error) => setStatus(err.message));
  }, []);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const body: Record<string, string> = {
        provider: settings.provider,
        ollama_model: settings.ollama_model,
      };
      if (openaiKey.trim()) body.openai_api_key = openaiKey.trim();
      if (anthropicKey.trim()) body.anthropic_api_key = anthropicKey.trim();

      const res = await apiFetch("/api/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setSettings(await res.json());
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
      const res = await apiFetch("/api/settings/test-chat", {
        method: "POST",
        body: JSON.stringify({
          message: "Say hello in one short sentence as Thyme.",
        }),
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
      <h1>Settings</h1>
      <p className="lede">
        Laptop default is local Ollama (<code>qwen2.5:7b</code>), same as the
        class labs. Optionally paste your own OpenAI or Anthropic key — you get
        billed by that provider, not by Thyme.
      </p>

      <form className="settings-form" onSubmit={onSave}>
        <label>
          Provider
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
