import { useState } from "react";
import type { ActivityEvent, Notice } from "./types";

type Props = {
  notice: Notice | null;
  activity: ActivityEvent[];
  progressPercent?: number | null;
  idleText?: string;
  onClear?: () => void;
};

export function ActivityStatus({
  notice,
  activity,
  progressPercent = null,
  idleText = "Ready",
  onClear,
}: Props) {
  const [open, setOpen] = useState(false);
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);
  const kind = notice?.kind || "idle";
  const showProgress =
    kind === "progress" &&
    typeof progressPercent === "number" &&
    progressPercent > 0;

  return (
    <div className={`activity-status kind-${kind}`}>
      <div className="activity-status-main" role="status" aria-live="polite">
        {kind === "progress" ? (
          <span className="spinner" aria-hidden="true" />
        ) : null}
        <div className="activity-status-body">
          <p>{notice?.text || idleText}</p>
          {showProgress ? (
            <div
              className="upload-progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progressPercent}
              role="progressbar"
            >
              <div
                className="upload-progress-bar"
                style={{ width: `${progressPercent}%` }}
              />
              <span className="upload-progress-label">{progressPercent}%</span>
            </div>
          ) : null}
        </div>
        <button
          type="button"
          className="activity-status-toggle"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          Activity ({activity.length})
          <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        </button>
      </div>

      {open ? (
        <div className="activity-status-panel">
          <ol className="activity-timeline">
            {activity.length === 0 ? (
              <li className="activity-empty">
                Events for this action show here — prompts, stages, and
                rejects.
              </li>
            ) : (
              [...activity].reverse().map((evt) => (
                <li
                  key={evt.id}
                  className={
                    evt.rejected
                      ? "activity-item rejected"
                      : evt.stage === "error"
                        ? "activity-item error"
                        : "activity-item"
                  }
                >
                  <span className="activity-stage">{evt.stage || "note"}</span>
                  <span className="activity-msg">{evt.message}</span>
                  {evt.prompt_preview ? (
                    <button
                      type="button"
                      className="text-btn activity-prompt-btn"
                      onClick={() =>
                        setExpandedPrompt(
                          expandedPrompt === evt.id ? null : evt.id,
                        )
                      }
                    >
                      {expandedPrompt === evt.id ? "Hide prompt" : "Show prompt"}
                    </button>
                  ) : null}
                  {expandedPrompt === evt.id && evt.prompt_preview ? (
                    <pre className="activity-prompt">{evt.prompt_preview}</pre>
                  ) : null}
                </li>
              ))
            )}
          </ol>
          {activity.length > 0 && onClear ? (
            <button type="button" className="text-btn" onClick={onClear}>
              Clear log
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
