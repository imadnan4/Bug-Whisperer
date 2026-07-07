const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("bw_api_key");
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const key = getApiKey();
  if (key) h["X-API-Key"] = key;
  return h;
}

export interface BugAnalysis {
  recall: {
    found: boolean;
    confidence: number;
    matched_entries: any[];
    suggestion: string | null;
    reasoning: string | null;
  };
  analysis: {
    error_type: string;
    root_cause_analysis: string;
    suggested_fix: string;
    code_snippet: string | null;
    severity: string;
    related_files: string[];
    from_memory: boolean;
  };
  session_id: string;
}

export interface Stats {
  total_bugs: number;
  bugs_resolved: number;
  bugs_recalled_from_memory: number;
  recall_hit_rate: number;
  avg_confidence: number;
  estimated_time_saved_minutes: number;
  memory_graph_size: number;
  top_error_types: { type: string; count: number }[];
  top_files: { file: string; count: number }[];
}

export interface MemoryEntry {
  error: string;
  root_cause: string;
  fix: string;
  files: string[];
  from_memory: boolean;
  confidence: number;
  time: string;
}

export async function analyzeBug(
  errorMessage: string,
  stackTrace: string = "",
  language: string = "python",
  filesInvolved: string[] = []
): Promise<BugAnalysis> {
  const res = await fetch(`${API_BASE}/api/bugs/analyze`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      error_message: errorMessage,
      stack_trace: stackTrace,
      language,
      files_involved: filesInvolved,
    }),
  });
  if (!res.ok) throw new Error("Analysis failed");
  return res.json();
}

export async function rememberFix(data: {
  session_id: string;
  root_cause: string;
  fix_description: string;
  code_snippet?: string;
  files_changed?: string[];
  worked?: boolean;
}) {
  const res = await fetch(`${API_BASE}/api/bugs/remember`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to store fix");
  return res.json();
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function getMemoryEntries(): Promise<MemoryEntry[]> {
  const res = await fetch(`${API_BASE}/api/memory/entries`);
  if (!res.ok) throw new Error("Failed to fetch memory entries");
  return res.json();
}
