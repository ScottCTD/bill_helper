export type DiffLineSign = "+" | "-";

export interface DiffLine {
  sign: DiffLineSign;
  path: string;
  value: string;
}

interface FlatField {
  path: string;
  value: string;
}

function normalizeForComparison(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizeForComparison);
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
    return Object.fromEntries(entries.map(([key, child]) => [key, normalizeForComparison(child)]));
  }
  return value;
}

function flattenValue(value: unknown, path: string, output: FlatField[]): void {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      output.push({
        path,
        value: "[]"
      });
      return;
    }
    value.forEach((child, index) => {
      const childPath = `${path}[${index}]`;
      flattenValue(child, childPath, output);
    });
    return;
  }

  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
    if (entries.length === 0) {
      output.push({
        path,
        value: "{}"
      });
      return;
    }
    entries.forEach(([key, child]) => {
      const childPath = path ? `${path}.${key}` : key;
      flattenValue(child, childPath, output);
    });
    return;
  }

  output.push({
    path,
    value: JSON.stringify(value)
  });
}

function flattenRecord(record: Record<string, unknown>): FlatField[] {
  const fields: FlatField[] = [];
  const entries = Object.entries(record).sort(([left], [right]) => left.localeCompare(right));

  entries.forEach(([key, value]) => {
    flattenValue(value, key, fields);
  });

  return fields;
}

function mapByPath(fields: FlatField[]): Map<string, string> {
  const map = new Map<string, string>();
  fields.forEach((field) => {
    map.set(field.path, field.value);
  });
  return map;
}

export function jsonRecordsAreEquivalent(left: Record<string, unknown>, right: Record<string, unknown>): boolean {
  const normalizedLeft = normalizeForComparison(left);
  const normalizedRight = normalizeForComparison(right);
  return JSON.stringify(normalizedLeft) === JSON.stringify(normalizedRight);
}

export function buildUnifiedDiffLines(
  basePayload: Record<string, unknown>,
  reviewerOverride?: Record<string, unknown>
): DiffLine[] {
  if (!reviewerOverride || jsonRecordsAreEquivalent(basePayload, reviewerOverride)) {
    return flattenRecord(basePayload).map((field) => ({
      sign: "+",
      path: field.path,
      value: field.value
    }));
  }

  const baseMap = mapByPath(flattenRecord(basePayload));
  const overrideMap = mapByPath(flattenRecord(reviewerOverride));
  const allPaths = Array.from(new Set([...baseMap.keys(), ...overrideMap.keys()])).sort((left, right) =>
    left.localeCompare(right)
  );

  const lines: DiffLine[] = [];
  allPaths.forEach((path) => {
    const previous = baseMap.get(path);
    const next = overrideMap.get(path);

    if (previous === next) {
      return;
    }
    if (previous !== undefined) {
      lines.push({ sign: "-", path, value: previous });
    }
    if (next !== undefined) {
      lines.push({ sign: "+", path, value: next });
    }
  });

  return lines;
}
