export function fallbackTagColor(tagName: string) {
  let hash = 0;
  for (let index = 0; index < tagName.length; index += 1) {
    hash = (hash * 31 + tagName.charCodeAt(index)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue} 62% 72%)`;
}

export function resolveTagColor(name: string, color: string | null | undefined) {
  return color ?? fallbackTagColor(name);
}