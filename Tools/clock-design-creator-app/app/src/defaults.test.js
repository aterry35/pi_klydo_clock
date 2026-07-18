import { describe, expect, it } from 'vitest';
import { applyTemplate, createInitialState, TEMPLATES, toThemeJson } from './defaults.js';

describe('template application', () => {
  it('uses the template name before the user edits the design name', () => {
    const current = createInitialState('kitchen-pop');
    expect(applyTemplate(current, 'night').name).toBe('Night');
  });

  it('preserves a user-edited design name when changing templates', () => {
    const current = { ...createInitialState('kitchen-pop'), name: 'Kpop' };
    expect(applyTemplate(current, 'night', true).name).toBe('Kpop');
  });

  it('includes dedicated Kitchen Pop and Paper Cut starting points', () => {
    expect(TEMPLATES['kitchen-pop'].dial.anim).toBe('kitchen-pop');
    expect(TEMPLATES['paper-cut'].name).toBe('Paper Cut');
    expect(TEMPLATES['paper-cut'].dial.anim).toBe('paper-cut');
  });

  it('matches the Kitchen Pop loop backdrop and large pendulum proportions', () => {
    const state = createInitialState('kitchen-pop');
    expect(state.pendulum.bobSize * 2).toBeGreaterThan(70);
    expect(toThemeJson(state).bottom.backdrop).toBe('loop');
  });

  it('exports the Paper Cut name and offset paper disc configuration', () => {
    const state = createInitialState('paper-cut');
    expect(state.name).toBe('Paper Cut');
    expect(state.pendulum.bobShape).toBe('circle');
    expect(state.pendulum.bobInnerOffsetX).toBe(26);
  });

  it('preserves creator credit and exports watermark metadata across templates', () => {
    const state = createInitialState('kitchen-pop');
    state.creator.artist = 'Sample Artist';
    state.dial.watermark = { enabled: true, text: 'Sample Artist', color: '#ffffff', opacity: 0.7 };
    const changed = applyTemplate(state, 'night');
    expect(changed.creator.artist).toBe('Sample Artist');
    expect(changed.dial.watermark.text).toBe('Sample Artist');
    expect(toThemeJson(changed).creator).toEqual({
      artist: 'Sample Artist', watermark: 'Sample Artist', watermark_enabled: true,
      watermark_color: '#ffffff', watermark_opacity: 0.7,
    });
  });
});
