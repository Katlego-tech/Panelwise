// The API's response types, verbatim from docs/design/web.md §6. The Pydantic models in
// services/api/app/api/v1/schemas.py mirror these field for field (T044).

export type JobState = "queued" | "running" | "done" | "failed";
export type Stage = "parsing" | "extracting" | "planning" | "rendering";
export interface Job {
  id: string;
  state: JobState;
  stage: Stage | null;
  progress: number;
  error: string | null;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  title: string;
  created_at: string;
  pages: number | null;
  scenes: number | null;
  shots: number | null; // null until known
  frames: { settled: number; total: number; withheld: number; active: number } | null;
  // null before rendering. settled = passed + warned + withheld + failed (§3); active = rendering + auditing
  job: Job; // the latest job
}

export interface SpanRef {
  page: number;
  line_start: number;
  line_end: number;
} // script.md Span
export interface QuoteView {
  text: string;
  span: SpanRef;
}
export interface EntityView {
  kind: "character" | "prop" | "location";
  name: string;
  source: "model" | "cue" | "heading";
  scenes: number[];
  quotes: QuoteView[];
}
export interface SceneView {
  index: number;
  number: string;
  heading: string;
  time_of_day: string | null; // resolve_times()
  time_carried: boolean; // true when time_of_day is not null and the heading itself had no absolute time
  elements: number;
  shots: number | null;
}
export interface ReportView {
  // grounding.md GroundingReport, plus the run's models and tokens (extraction, and planning once it has run)
  faithfulness: number;
  entities_proposed: number;
  entities_grounded: number;
  quotes_proposed: number;
  quotes_located: number;
  recall: number;
  cues_total: number;
  cues_found_by_model: number;
  models: string[];
  prompt_tokens: number;
  completion_tokens: number;
}
export interface Project extends ProjectSummary {
  scene_list: SceneView[] | null;
  entities: EntityView[] | null;
  report: ReportView | null;
}

export interface LinesView {
  lines: string[];
  page_starts: number[];
} // Screenplay.text split on "\n"; page_starts[0] == 1

export interface ShotView {
  id: string; // "{scene number}.{shot number}", e.g. "1.4"
  scene_index: number;
  number: number;
  framing: "wide" | "medium" | "close_up" | "extreme_close_up" | "over_shoulder" | "pov" | "insert";
  movement: "static" | "pan" | "tilt" | "dolly" | "tracking" | "handheld" | "crane";
  characters: string[];
  props: string[];
  time_of_day: string | null;
  rationale: string;
  span: SpanRef;
  source: string;
  // one per covered element, in order ([] for a heading-only establishing shot); on_screen is
  // false for dialogue whose speaker (match_speaker against the extraction's characters) is not
  // in `characters`, a cue that matches no character included; true for action
  // extension (T045): the dialogue cue's bracket without its parentheses ("O.S.", "V.O."), null for action or none
  segments: { line_start: number; line_end: number; cue: string | null; extension: string | null; on_screen: boolean }[];
}

export type FrameStateView = "rendering" | "auditing" | "passed" | "warned" | "withheld" | "failed";
export interface CheckView {
  check: string;
  severity: "hard" | "soft";
  ok: boolean;
  detail: string;
}
export interface AuditView {
  // one frame_audits row (verify.md §6)
  attempt: number;
  seed: number;
  verdict: "pass" | "warn" | "fail" | "error";
  description: {
    people: { position: "left" | "centre" | "right"; appearance: string }[];
    setting: string;
    light: string;
    shot_size: string;
    objects: { name: string; category: string; held: boolean }[];
    has_text: boolean;
  } | null;
  judgement: {
    people: { person: number; character: string | null; support: string | null }[];
    objects: { object: number; kind: string; support: string | null }[];
  } | null;
  checks: CheckView[];
  positions: Record<string, "left" | "centre" | "right">;
  models: string[];
  created_at: string;
}
export interface FrameView {
  shot_id: string;
  state: FrameStateView;
  attempt: number;
  max_renders: number;
  image_url: string | null; // a Supabase Storage signed URL; non-null ONLY when passed or warned
  withheld_check: string | null; // the first failed hard check, when withheld (or "audit_error")
  audits: AuditView[]; // [] until T021
}
