import { describe, expect, it } from 'vitest';
import { setNestedValue, slugify } from './utils.js';

describe('slugify', () => {
  it('creates a safe folder slug', () => {
    expect(slugify('  Sunny Kitchen!  ')).toBe('sunny-kitchen');
  });
});

describe('setNestedValue', () => {
  it('updates one branch without mutating the source', () => {
    const source = { theme: { hands: { hour: { width: 10 } }, accent: '#fff' } };
    const result = setNestedValue(source, 'theme.hands.hour.width', 12);
    expect(result.theme.hands.hour.width).toBe(12);
    expect(source.theme.hands.hour.width).toBe(10);
    expect(result.theme.accent).toBe('#fff');
  });
});
