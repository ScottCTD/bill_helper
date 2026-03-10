export type DiffLineSign = "+" | "-";

export interface DiffLine {
  sign: DiffLineSign;
  path: string;
  value: string;
}

export interface DiffMetadata {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "danger";
}

export interface DiffStats {
  added: number;
  changed: number;
  removed: number;
}

export interface ProposalDiff {
  mode: "create" | "update" | "delete" | "snapshot";
  title: string;
  lines: DiffLine[];
  stats: DiffStats;
  metadata: DiffMetadata[];
  note?: string;
}

export type JsonRecord = Record<string, unknown>;

export interface FlatField {
  rawPath: string;
  displayPath: string;
  value: string;
}
