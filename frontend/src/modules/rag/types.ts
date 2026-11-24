export type RecipeSummary = {
  recipe_id: string;
  title: string;
  source: "upload" | "web";
  difficulty: "easy" | "medium" | "hard" | null;
  total_time_minutes: number | null;
  cuisine: string | null;
  ingredient_keywords: string[];
  preview: string;
  source_doc: string | null;
  source_url: string | null;
};

export type Recipe = {
  recipe_id: string;
  title: string;
  source: "upload" | "web";
  raw_text: string;
  ingredient_keywords: string[];
  ingredients: { name: string; quantity: string | null; unit: string | null }[];
  steps: string[];
  difficulty: "easy" | "medium" | "hard" | null;
  total_time_minutes: number | null;
  servings: number | null;
  cuisine: string | null;
  tags: string[];
  source_url: string | null;
  source_doc: string | null;
  updated_at?: string;
};

export type SearchHit = {
  recipe: Recipe;
  score: number;
  reason: string;
  origin: "local" | "web";
};

export type ActivityEvent = {
  id: string;
  at: number;
  stage?: string;
  message: string;
  prompt_preview?: string;
  rejected?: boolean;
  web_query?: string;
  percent?: number;
};

export type SearchResponse = {
  results: SearchHit[];
  web_queried: boolean;
  web_query: string | null;
  web_imported: number;
  web_previews?: number;
  activity?: Record<string, unknown>[];
};

export type Notice = {
  kind: "info" | "success" | "error" | "progress";
  text: string;
};
