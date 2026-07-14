import { describe, expect, it } from 'vitest';
import { CLOCK } from './clockConfig.js';
import { createInitialState } from './defaults.js';
import { layoutCircles } from './renderer.js';

describe('clock layout circles', () => {
  it('uses the existing layout sizes by default', () => {
    const state = createInitialState();
    expect(layoutCircles(state.theme)).toEqual({
      top: { cx: 224, cy: 260, r: 200 },
      bottom: { cx: 210, cy: 650, r: 150 },
    });
  });

  it('resizes both complete circular cutouts', () => {
    const state = createInitialState();
    state.theme.dial.diameter = 500;
    state.theme.bottom.diameter = 340;
    expect(layoutCircles(state.theme)).toEqual({
      top: { cx: 224, cy: 260, r: 250 },
      bottom: { cx: 210, cy: 650, r: 170 },
    });
  });

  it('does not paint a black inset inside the physical enclosure openings', () => {
    expect(CLOCK.fixtureBorder).toBe(0);
  });
});
