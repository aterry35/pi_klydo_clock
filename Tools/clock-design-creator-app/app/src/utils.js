export function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function setNestedValue(source, path, value) {
  const keys = path.split('.');
  const root = { ...source };
  let target = root;
  let current = source;
  for (let index = 0; index < keys.length - 1; index += 1) {
    const key = keys[index];
    current = current[key];
    target[key] = { ...current };
    target = target[key];
  }
  target[keys.at(-1)] = value;
  return root;
}

export function hexToRgb(hex) {
  const clean = String(hex || '#000000').replace('#', '');
  const expanded = clean.length === 3
    ? clean.split('').map((part) => part + part).join('')
    : clean;
  const numeric = Number.parseInt(expanded, 16);
  return [
    (numeric >> 16) & 255,
    (numeric >> 8) & 255,
    numeric & 255,
  ];
}

export function colorWithAlpha(hex, alpha) {
  const [red, green, blue] = hexToRgb(hex);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let next = value;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 20_000);
}
