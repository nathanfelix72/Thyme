import type { Recipe } from "./types";

export function parseTags(raw: string): string[] {
  return raw
    .split(/[,;\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function errorDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item && "msg" in item
          ? String((item as { msg: string }).msg)
          : JSON.stringify(item),
      )
      .join("; ");
  }
  return fallback;
}

export function previewText(recipe: Recipe, max = 140): string {
  const raw = (recipe.raw_text || "").replace(/\s+/g, " ").trim();
  if (raw.length <= max) return raw;
  return `${raw.slice(0, max - 1)}…`;
}

export function formatIngredientLine(ing: {
  name: string;
  quantity: string | null;
  unit: string | null;
}): string {
  return [ing.quantity, ing.unit, ing.name].filter(Boolean).join(" ");
}

export function recipePlainText(recipe: Recipe): string {
  const lines: string[] = [recipe.title, ""];

  if (recipe.ingredients.length > 0) {
    lines.push("Ingredients");
    for (const ing of recipe.ingredients) {
      lines.push(`- ${formatIngredientLine(ing)}`);
    }
    lines.push("");
  }

  if (recipe.steps.length > 0) {
    lines.push("Steps");
    recipe.steps.forEach((step, idx) => {
      lines.push(`${idx + 1}. ${step}`);
    });
    lines.push("");
  }

  if (recipe.raw_text?.trim()) {
    lines.push("Source text");
    lines.push(recipe.raw_text.trim());
  }

  return lines.join("\n").trim() + "\n";
}

export function downloadRecipeText(recipe: Recipe) {
  const blob = new Blob([recipePlainText(recipe)], {
    type: "text/plain;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const safe = recipe.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
  a.href = url;
  a.download = `${safe || "recipe"}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

let activitySeq = 0;

export function nextActivityId(): string {
  return `a-${++activitySeq}`;
}
