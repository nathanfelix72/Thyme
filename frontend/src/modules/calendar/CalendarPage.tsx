import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { apiFetch } from "../../lib/api";
import { AuthGate } from "../rag/AuthGate";

type GoogleStatus = {
  configured: boolean;
  connected: boolean;
  email: string | null;
  redirect_uri: string;
  can_configure: boolean;
};

type CalendarEvent = {
  id: string;
  title: string;
  start: string;
  end: string | null;
  all_day: boolean;
  calendar_id?: string | null;
  calendar_name?: string | null;
  calendar_color?: string | null;
};

type WeekPlan = {
  connected: boolean;
  start: string;
  end: string;
  email: string | null;
  events: CalendarEvent[];
};

const DAY_START_HOUR = 6;
const DAY_END_HOUR = 22;
const PX_PER_HOUR = 56;
const HIDDEN_CALS_KEY = "thyme.plan.hiddenCalendars";

function sundayOf(d: Date): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() - copy.getDay()); // Sun=0
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function readLocalHiddenCalendars(): Set<string> {
  try {
    const raw = localStorage.getItem(HIDDEN_CALS_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function writeLocalHiddenCalendars(hidden: Set<string>) {
  try {
    localStorage.setItem(HIDDEN_CALS_KEY, JSON.stringify([...hidden]));
  } catch {
    /* ignore */
  }
}

async function persistInactiveCalendars(hidden: Set<string>): Promise<void> {
  writeLocalHiddenCalendars(hidden);
  const res = await apiFetch("/api/settings", {
    method: "PUT",
    body: JSON.stringify({ inactive_calendar_ids: [...hidden] }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Could not save calendar visibility");
  }
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function eventDayKey(ev: CalendarEvent): string {
  if (ev.all_day) return ev.start.slice(0, 10);
  const dt = new Date(ev.start);
  if (Number.isNaN(dt.getTime())) return ev.start.slice(0, 10);
  return toIsoDate(dt);
}

function minutesSinceMidnight(iso: string): number {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return 0;
  return dt.getHours() * 60 + dt.getMinutes();
}

function formatDayHeading(iso: string): string {
  return parseLocalDate(iso).toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function formatHourLabel(hour: number): string {
  const dt = new Date();
  dt.setHours(hour, 0, 0, 0);
  return dt.toLocaleTimeString([], { hour: "numeric" });
}

function formatEventTime(ev: CalendarEvent): string {
  if (ev.all_day) return "All day";
  const start = new Date(ev.start);
  if (Number.isNaN(start.getTime())) return "";
  const startLabel = start.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
  if (!ev.end) return startLabel;
  const end = new Date(ev.end);
  if (Number.isNaN(end.getTime())) return startLabel;
  return `${startLabel} – ${end.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

type TimedLayout = {
  event: CalendarEvent;
  top: number;
  height: number;
  leftPct: number;
  widthPct: number;
  color: string;
};

function eventRangeMinutes(ev: CalendarEvent): { start: number; end: number } {
  const startMin = minutesSinceMidnight(ev.start);
  const endMin = ev.end ? minutesSinceMidnight(ev.end) : startMin + 30;
  const gridStart = DAY_START_HOUR * 60;
  const gridEnd = DAY_END_HOUR * 60;
  const clampedStart = Math.max(startMin, gridStart);
  const clampedEnd = Math.min(Math.max(endMin, clampedStart + 20), gridEnd);
  return { start: clampedStart, end: clampedEnd };
}

/** Pack overlapping timed events into side-by-side columns. */
function layoutTimedEvents(events: CalendarEvent[]): TimedLayout[] {
  const sorted = events
    .map((event) => {
      const range = eventRangeMinutes(event);
      return { event, ...range };
    })
    .sort((a, b) => a.start - b.start || b.end - a.end);

  type Placed = (typeof sorted)[number] & { column: number };
  const placed: Placed[] = [];
  const columnEnds: number[] = [];

  for (const item of sorted) {
    let column = columnEnds.findIndex((end) => end <= item.start);
    if (column === -1) {
      column = columnEnds.length;
      columnEnds.push(item.end);
    } else {
      columnEnds[column] = item.end;
    }
    placed.push({ ...item, column });
  }

  const clusters: Placed[][] = [];
  let cluster: Placed[] = [];
  let clusterEnd = -1;
  for (const item of placed) {
    if (cluster.length === 0 || item.start < clusterEnd) {
      cluster.push(item);
      clusterEnd = Math.max(clusterEnd, item.end);
    } else {
      clusters.push(cluster);
      cluster = [item];
      clusterEnd = item.end;
    }
  }
  if (cluster.length) clusters.push(cluster);

  const gridStart = DAY_START_HOUR * 60;
  const layouts: TimedLayout[] = [];
  for (const group of clusters) {
    const colCount = Math.max(...group.map((g) => g.column)) + 1;
    for (const item of group) {
      layouts.push({
        event: item.event,
        top: ((item.start - gridStart) / 60) * PX_PER_HOUR,
        height: Math.max(((item.end - item.start) / 60) * PX_PER_HOUR, 22),
        leftPct: (item.column / colCount) * 100,
        widthPct: 100 / colCount,
        color: item.event.calendar_color || "#3f6b45",
      });
    }
  }
  return layouts;
}

function timedEventStyle(layout: TimedLayout): CSSProperties {
  return {
    top: `${layout.top}px`,
    height: `${layout.height}px`,
    left: `calc(${layout.leftPct}% + 2px)`,
    width: `calc(${layout.widthPct}% - 4px)`,
    background: layout.color,
    borderColor: "rgba(255, 255, 255, 0.55)",
  };
}

export function CalendarPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [week, setWeek] = useState<WeekPlan | null>(null);
  const [weekStart, setWeekStart] = useState(() => sundayOf(new Date()));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [showSetup, setShowSetup] = useState(true);
  const [copied, setCopied] = useState(false);
  const [hiddenCalendars, setHiddenCalendars] = useState<Set<string>>(
    () => readLocalHiddenCalendars(),
  );

  const startIso = useMemo(() => toIsoDate(weekStart), [weekStart]);
  const todayIso = useMemo(() => toIsoDate(new Date()), []);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/settings")
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        const fromProfile = Array.isArray(data.inactive_calendar_ids)
          ? data.inactive_calendar_ids.filter(
              (x: unknown): x is string => typeof x === "string" && !!x.trim(),
            )
          : [];
        const local = readLocalHiddenCalendars();
        // Prefer saved profile; if empty, migrate any local-only hides once.
        const merged =
          fromProfile.length > 0
            ? new Set(fromProfile)
            : local.size > 0
              ? local
              : new Set<string>();
        if (cancelled) return;
        setHiddenCalendars(merged);
        writeLocalHiddenCalendars(merged);
        if (fromProfile.length === 0 && local.size > 0) {
          void persistInactiveCalendars(merged).catch(() => {
            /* keep local cache if profile save fails */
          });
        }
      })
      .catch(() => {
        /* keep local cache */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const statusRes = await apiFetch("/api/calendar/google/status");
      if (!statusRes.ok) {
        setShowSetup(true);
        throw new Error(
          statusRes.status === 404
            ? "Calendar API routes missing — restart the backend (uvicorn)."
            : await statusRes.text(),
        );
      }
      const nextStatus = (await statusRes.json()) as GoogleStatus;
      setStatus(nextStatus);
      setShowSetup(!nextStatus.configured);

      const weekRes = await apiFetch(
        `/api/calendar/week?start=${encodeURIComponent(startIso)}`,
      );
      if (!weekRes.ok) {
        const body = await weekRes.json().catch(() => null);
        throw new Error(body?.detail || (await weekRes.text()));
      }
      setWeek((await weekRes.json()) as WeekPlan);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load calendar");
      setShowSetup(true);
    } finally {
      setBusy(false);
    }
  }, [startIso]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const flag = searchParams.get("google");
    if (!flag) return;
    if (flag === "connected") {
      setMessage("Google Calendar connected.");
    } else if (flag === "error") {
      setError(
        searchParams.get("detail") ||
          "Google Calendar connection failed. Try again.",
      );
    }
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  async function onSaveAppCredentials(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch("/api/calendar/google/app-credentials", {
        method: "PUT",
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim(),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save credentials");
      setStatus(data as GoogleStatus);
      setClientSecret("");
      setShowSetup(false);
      setMessage("Google app setup saved. You can connect your calendar now.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const connected = Boolean(status?.connected || week?.connected);
  const configured = status?.configured ?? false;
  const setupVisible = showSetup || !configured;
  const redirectUri =
    status?.redirect_uri ||
    "http://127.0.0.1:8765/api/calendar/google/callback";

  async function onConnect() {
    if (!configured) {
      setShowSetup(true);
      setMessage("Finish the one-time Google setup below, then connect.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch("/api/calendar/google/auth-url");
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setShowSetup(true);
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Google Calendar isn’t set up yet.",
        );
      }
      window.location.href = data.url as string;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
      setBusy(false);
    }
  }

  async function onDisconnect() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch("/api/calendar/google", { method: "DELETE" });
      if (!res.ok) throw new Error(await res.text());
      setMessage("Disconnected Google Calendar.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
      setBusy(false);
    }
  }

  async function copyRedirectUri() {
    const uri = status?.redirect_uri || redirectUri;
    try {
      await navigator.clipboard.writeText(uri);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy — select the redirect URI and copy manually.");
    }
  }

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => toIsoDate(addDays(weekStart, i)));
  }, [weekStart]);

  const hours = useMemo(
    () =>
      Array.from(
        { length: DAY_END_HOUR - DAY_START_HOUR },
        (_, i) => DAY_START_HOUR + i,
      ),
    [],
  );

  const calendarLegend = useMemo(() => {
    const seen = new Map<
      string,
      { id: string; name: string; color: string; visible: boolean }
    >();
    for (const ev of week?.events || []) {
      const id = ev.calendar_id || ev.calendar_name || "calendar";
      if (seen.has(id)) continue;
      seen.set(id, {
        id,
        name: ev.calendar_name || "Calendar",
        color: ev.calendar_color || "#3f6b45",
        visible: !hiddenCalendars.has(id),
      });
    }
    return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [week, hiddenCalendars]);

  const byDay = useMemo(() => {
    const map = new Map<
      string,
      { allDay: CalendarEvent[]; timed: CalendarEvent[] }
    >();
    for (const day of days) map.set(day, { allDay: [], timed: [] });
    for (const ev of week?.events || []) {
      const calId = ev.calendar_id || ev.calendar_name || "calendar";
      if (hiddenCalendars.has(calId)) continue;
      const key = eventDayKey(ev);
      const bucket = map.get(key);
      if (!bucket) continue;
      if (ev.all_day) bucket.allDay.push(ev);
      else bucket.timed.push(ev);
    }
    return map;
  }, [days, week, hiddenCalendars]);

  function toggleCalendar(id: string) {
    setHiddenCalendars((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      writeLocalHiddenCalendars(next);
      void persistInactiveCalendars(next).catch((err: Error) => {
        setError(err.message || "Could not save calendar visibility");
      });
      return next;
    });
  }

  const gridHeight = (DAY_END_HOUR - DAY_START_HOUR) * PX_PER_HOUR;

  return (
    <AuthGate eyebrow="02 · Plan" title="Plan">
      <section className="page-panel plan-page">
        <p className="eyebrow">02 · Plan</p>
        <h1>Plan</h1>
        <p className="lede">
          Your Google calendars for the week — read-only for now. Meal planning
          comes later.
        </p>

        {setupVisible && (
          <div className="plan-setup" id="google-setup">
            <h2>One-time Google setup</h2>
            <p>
              Google requires a free OAuth client for this app (same idea as
              Cognito). Do this once; after that everyone just clicks{" "}
              <strong>Connect Google Calendar</strong> and signs in with Gmail.
            </p>
            <ol className="plan-setup-steps">
              <li>
                Open{" "}
                <a
                  href="https://console.cloud.google.com/apis/credentials"
                  target="_blank"
                  rel="noreferrer"
                >
                  Google Cloud → Credentials
                </a>{" "}
                (create a project if prompted).
              </li>
              <li>
                Enable the{" "}
                <a
                  href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"
                  target="_blank"
                  rel="noreferrer"
                >
                  Google Calendar API
                </a>
                .
              </li>
              <li>
                Configure the OAuth consent screen (External). Add your Gmail as
                a test user while the app is in testing.
              </li>
              <li>
                Create credentials → <strong>OAuth client ID</strong> → type{" "}
                <strong>Web application</strong>. Under Authorized redirect
                URIs, paste exactly:
                <div className="plan-redirect-row">
                  <code className="plan-redirect-uri">{redirectUri}</code>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() => void copyRedirectUri()}
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </li>
              <li>Paste the Client ID and Client secret below, then Save.</li>
            </ol>

            <form className="settings-form" onSubmit={onSaveAppCredentials}>
              <label>
                Client ID
                <input
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  autoComplete="off"
                  required
                  placeholder="….apps.googleusercontent.com"
                />
              </label>
              <label>
                Client secret
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  autoComplete="off"
                  required
                  placeholder="GOCSPX-…"
                />
              </label>
              <div className="settings-actions">
                <button type="submit" disabled={busy}>
                  Save Google app setup
                </button>
                {configured && (
                  <button
                    type="button"
                    className="text-btn"
                    disabled={busy}
                    onClick={() => setShowSetup(false)}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>
        )}

        <div className="plan-toolbar">
          <div className="plan-week-nav">
            <button
              type="button"
              className="text-btn"
              disabled={busy}
              onClick={() => setWeekStart((d) => addDays(d, -7))}
            >
              ← Prev
            </button>
            <span className="plan-week-label">
              Week of {formatDayHeading(startIso)}
            </span>
            <button
              type="button"
              className="text-btn"
              disabled={busy}
              onClick={() => setWeekStart((d) => addDays(d, 7))}
            >
              Next →
            </button>
            <button
              type="button"
              className="text-btn"
              disabled={busy}
              onClick={() => setWeekStart(sundayOf(new Date()))}
            >
              Today
            </button>
          </div>

          <div className="settings-actions">
            {!connected ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void onConnect()}
              >
                Connect Google Calendar
              </button>
            ) : (
              <button
                type="button"
                className="text-btn danger"
                disabled={busy}
                onClick={() => void onDisconnect()}
              >
                Disconnect
              </button>
            )}
            {!setupVisible && (
              <button
                type="button"
                className="text-btn"
                disabled={busy}
                onClick={() => setShowSetup(true)}
              >
                One-time Google setup
              </button>
            )}
          </div>
        </div>

        {configured && !connected && !setupVisible && (
          <p className="plan-connected-hint">
            Click Connect, choose your Google account, and allow calendar
            access.
          </p>
        )}

        {connected && (status?.email || week?.email) && (
          <p className="plan-connected-hint">
            Connected as {status?.email || week?.email}
            {busy ? " · Refreshing…" : ""}
          </p>
        )}

        {calendarLegend.length > 0 && (
          <div className="plan-legend-block">
            <p className="plan-legend-hint">
              Click a calendar to mark it inactive — stays saved on your profile
            </p>
            <ul className="plan-legend">
              {calendarLegend.map((cal) => (
                <li key={cal.id}>
                  <button
                    type="button"
                    className={`plan-legend-toggle${cal.visible ? "" : " is-off"}`}
                    onClick={() => toggleCalendar(cal.id)}
                    aria-pressed={cal.visible}
                  >
                    <span
                      className="plan-legend-swatch"
                      style={{ background: cal.color }}
                    />
                    {cal.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {message && <p className="settings-status">{message}</p>}
        {error && <p className="inline-notice">{error}</p>}
        {busy && !week && <p className="settings-status">Loading…</p>}

        {connected && week && (
          <div className="plan-timetable">
            <div className="plan-timetable-head">
              <div className="plan-time-gutter" />
              {days.map((day) => (
                <div
                  key={day}
                  className={`plan-day-head${day === todayIso ? " is-today" : ""}`}
                >
                  {formatDayHeading(day)}
                </div>
              ))}
            </div>

            <div className="plan-allday-row">
              <div className="plan-time-gutter">
                <span>All day</span>
              </div>
              {days.map((day) => {
                const allDay = byDay.get(day)?.allDay || [];
                return (
                  <div key={day} className="plan-allday-cell">
                    {allDay.map((ev) => (
                      <div
                        key={ev.id}
                        className="plan-allday-event"
                        style={{
                          background: ev.calendar_color || "#3f6b45",
                        }}
                        title={`${ev.title}${ev.calendar_name ? ` · ${ev.calendar_name}` : ""}`}
                      >
                        {ev.title}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            <div className="plan-timetable-body">
              <div className="plan-time-gutter" style={{ height: gridHeight }}>
                {hours.map((hour) => (
                  <div
                    key={hour}
                    className="plan-hour-label"
                    style={{ height: PX_PER_HOUR }}
                  >
                    {formatHourLabel(hour)}
                  </div>
                ))}
              </div>

              {days.map((day) => {
                const timed = layoutTimedEvents(byDay.get(day)?.timed || []);
                return (
                  <div
                    key={day}
                    className={`plan-day-column${day === todayIso ? " is-today" : ""}`}
                    style={{ height: gridHeight }}
                  >
                    {hours.map((hour) => (
                      <div
                        key={hour}
                        className="plan-hour-line"
                        style={{ top: (hour - DAY_START_HOUR) * PX_PER_HOUR }}
                      />
                    ))}
                    {timed.map((layout) => {
                      const ev = layout.event;
                      return (
                        <div
                          key={ev.id}
                          className="plan-timed-event"
                          style={timedEventStyle(layout)}
                          title={`${formatEventTime(ev)} · ${ev.title}${ev.calendar_name ? ` · ${ev.calendar_name}` : ""}`}
                        >
                          <span className="plan-timed-event-time">
                            {formatEventTime(ev)}
                          </span>
                          <span className="plan-timed-event-title">
                            {ev.title}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </AuthGate>
  );
}
