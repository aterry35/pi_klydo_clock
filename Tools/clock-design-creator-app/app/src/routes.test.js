import { describe, expect, it } from 'vitest';
import { viewFromLocation } from './routes.js';

describe('public routes', () => {
  it.each([
    ['/', '', 'home'],
    ['/artists', '', 'artists'],
    ['/designer/', '', 'designer'],
    ['/community', '', 'community'],
    ['/build', '', 'build'],
    ['/admin', '', 'admin'],
  ])('maps %s to %s', (pathname, hash, expected) => {
    expect(viewFromLocation({ pathname, hash })).toBe(expected);
  });

  it.each([
    ['#designer', 'designer'],
    ['#community', 'community'],
    ['#admin', 'admin'],
  ])('preserves legacy %s links', (hash, expected) => {
    expect(viewFromLocation({ pathname: '/', hash })).toBe(expected);
  });

  it('returns home for an unknown public path', () => {
    expect(viewFromLocation({ pathname: '/not-a-page', hash: '' })).toBe('home');
  });
});
