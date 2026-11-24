import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import {
  applyTheme,
  type ThemePreference,
} from "../lib/theme";

type Units = "us" | "metric";

type ProfileState = {
  display_name: string;
  theme: ThemePreference;
  units: Units;
  default_servings: number;
  always_exclude_ingredients: string[];
};

const empty: ProfileState = {
  display_name: "",
  theme: "system",
  units: "us",
  default_servings: 4,
  always_exclude_ingredients: [],
};

export function Profile() {
  const { email } = useAuth();
  const [profile, setProfile] = useState<ProfileState>(empty);
  const [alwaysExclude, setAlwaysExclude] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await apiFetch("/api/settings");
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const next: ProfileState = {
      display_name: data.display_name || "",
      theme: data.theme || "system",
      units: data.units || "us",
      default_servings: data.default_servings || 4,
      always_exclude_ingredients: data.always_exclude_ingredients || [],
    };
    setProfile(next);
    setAlwaysExclude(next.always_exclude_ingredients.join(", "));
    applyTheme(next.theme);
  }

  useEffect(() => {
    load().catch((err: Error) => setStatus(err.message));
  }, []);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const res = await apiFetch("/api/settings", {
        method: "PUT",
        body: JSON.stringify({
          display_name: profile.display_name,
          theme: profile.theme,
          units: profile.units,
          default_servings: profile.default_servings,
          always_exclude_ingredients: alwaysExclude
            .split(/[,;\n]+/)
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const next: ProfileState = {
        display_name: data.display_name || "",
        theme: data.theme || "system",
        units: data.units || "us",
        default_servings: data.default_servings || 4,
        always_exclude_ingredients: data.always_exclude_ingredients || [],
      };
      setProfile(next);
      setAlwaysExclude(next.always_exclude_ingredients.join(", "));
      applyTheme(next.theme);
      setStatus("Saved.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="home">
      <p className="eyebrow">Account</p>
      <h1>Profile</h1>
      <p className="lede">
        Personal preferences for cooking and the app. Model keys and per-task
        AI routing are under <Link to="/ai-settings">AI settings</Link>.
      </p>

      <form className="settings-form" onSubmit={onSave}>
        <label>
          Display name
          <input
            value={profile.display_name}
            onChange={(e) =>
              setProfile({ ...profile, display_name: e.target.value })
            }
            placeholder={email || "Your name"}
            autoComplete="nickname"
          />
          <span className="field-hint">
            Shown in the sidebar when set. Sign-in email stays separate.
          </span>
        </label>

        <label>
          Theme
          <select
            value={profile.theme}
            onChange={(e) => {
              const theme = e.target.value as ThemePreference;
              setProfile({ ...profile, theme });
              applyTheme(theme);
            }}
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>

        <label>
          Measurement units
          <select
            value={profile.units}
            onChange={(e) =>
              setProfile({ ...profile, units: e.target.value as Units })
            }
          >
            <option value="us">US (cups, °F)</option>
            <option value="metric">Metric (g, ml, °C)</option>
          </select>
          <span className="field-hint">
            Preference for future scaling and display helpers.
          </span>
        </label>

        <label>
          Default servings
          <input
            type="number"
            min={1}
            max={48}
            value={profile.default_servings}
            onChange={(e) =>
              setProfile({
                ...profile,
                default_servings: Math.max(
                  1,
                  Math.min(48, Number(e.target.value) || 1),
                ),
              })
            }
          />
          <span className="field-hint">
            Starting point when a recipe has no servings listed.
          </span>
        </label>

        <label>
          Always exclude (allergies)
          <input
            value={alwaysExclude}
            onChange={(e) => setAlwaysExclude(e.target.value)}
            placeholder="peanuts, shellfish, dairy"
          />
          <span className="field-hint">
            Applied on every recipe search for this account. Comma-separated.
          </span>
        </label>

        <div className="settings-actions">
          <button type="submit" disabled={busy}>
            Save
          </button>
        </div>
      </form>

      {status ? <p className="settings-status">{status}</p> : null}
    </section>
  );
}
