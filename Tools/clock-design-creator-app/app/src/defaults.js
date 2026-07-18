import { CIRCLE_DIAMETERS } from './clockConfig.js';

function theme(options) {
  return {
    accent: options.accent,
    background: options.background,
    hands: {
      hour: {
        color: options.hourColor,
        width: options.hourWidth,
        length: options.hourLength,
        glow: options.glow,
        shape: options.shape,
      },
      minute: {
        color: options.minuteColor,
        width: options.minuteWidth,
        length: options.minuteLength,
        glow: options.glow,
        shape: options.shape,
      },
      second: {
        color: options.secondColor,
        width: options.secondWidth,
        length: options.secondLength,
        glow: options.glow,
        visible: options.secondVisible,
      },
    },
    dial: {
      markings: options.markings,
      color: options.dialColor,
      count: 12,
      diameter: options.dialDiameter ?? CIRCLE_DIAMETERS.dial.default,
    },
    pendulum: {
      period_s: options.period,
      amplitude_deg: options.amplitude,
      pivot_x: 0.5,
      pivot_y: options.pivotY,
      rod_length: 0.74,
    },
    bottom: {
      backdrop: options.backdrop,
      color: options.bottomColor,
      diameter: options.pendulumDiameter ?? CIRCLE_DIAMETERS.pendulum.default,
    },
    ambiance: {
      day_night: false,
      twinkle: Boolean(options.twinkle),
      glow: Boolean(options.ambientGlow),
    },
  };
}

const baseOptions = {
  accent: '#ffb70f',
  background: '#050505',
  hourColor: '#063d3a',
  hourWidth: 11,
  hourLength: 0.42,
  minuteColor: '#063d3a',
  minuteWidth: 9,
  minuteLength: 0.66,
  secondColor: '#ffb70f',
  secondWidth: 2,
  secondLength: 0.85,
  secondVisible: false,
  glow: false,
  shape: 'rounded',
  markings: 'none',
  dialColor: '#ffffff',
  period: 1.6,
  amplitude: 9,
  pivotY: 0.035,
  backdrop: 'solid',
  bottomColor: '#000000',
};

export const TEMPLATES = Object.freeze({
  blank: {
    name: 'Untitled Clock',
    dial: {
      mode: 'procedural', anim: 'breathing', c1: '#8a8f9c', c2: '#3c414d',
      c3: '#101216', cycles: 1, density: 4, duration: 6, fps: 15,
    },
    pendulum: {
      mode: 'builder', rodColor: '#c9ccd4', rodWidth: 4, rodLength: 0.58,
      bobShape: 'circle', bobSize: 44, bobColor: '#8a8f9c', bobInner: '#e8e9ec',
      bobInnerScale: 0.68, bobInnerOffsetX: 0,
    },
    theme: theme({ ...baseOptions, accent: '#8a8f9c', hourColor: '#e8e9ec', minuteColor: '#e8e9ec' }),
  },
  'paper-cut': {
    name: 'Paper Cut',
    dial: {
      mode: 'procedural', anim: 'paper-cut', c1: '#e8492a', c2: '#f1e6d0',
      c3: '#1c3a4b', cycles: 1, density: 6, duration: 8, fps: 15,
    },
    pendulum: {
      mode: 'builder', rodColor: '#2e8f7f', rodWidth: 8, rodLength: 0.5,
      bobShape: 'circle', bobSize: 92, bobColor: '#faf6ee', bobInner: '#e8492a',
      bobInnerScale: 0.74, bobInnerOffsetX: 26,
    },
    theme: theme({
      ...baseOptions, accent: '#e8492a', background: '#0d0d0d', hourColor: '#e8492a',
      minuteColor: '#e8492a', secondColor: '#faf6ee', hourWidth: 12,
      hourLength: 0.4, minuteLength: 0.62, period: 1.7, amplitude: 8,
    }),
  },
  'vintage-film': {
    name: 'Vintage Film',
    dial: {
      mode: 'procedural', anim: 'grain', c1: '#cfc6b4', c2: '#7d7566',
      c3: '#151513', cycles: 1, density: 5, duration: 6, fps: 15,
    },
    pendulum: {
      mode: 'builder', rodColor: '#a89e8c', rodWidth: 4, rodLength: 0.6,
      bobShape: 'circle', bobSize: 44, bobColor: '#f5f5f0', bobInner: '#151513',
      bobInnerScale: 0.68, bobInnerOffsetX: 0,
    },
    theme: theme({
      ...baseOptions, accent: '#f5f5f0', background: '#151513', hourColor: '#f5f5f0',
      minuteColor: '#f5f5f0', secondColor: '#f5f5f0', hourWidth: 10, minuteWidth: 7,
    }),
  },
  'kitchen-pop': {
    name: 'Kitchen Pop',
    dial: {
      mode: 'procedural', anim: 'kitchen-pop', c1: '#ffb70f', c2: '#ff8200',
      c3: '#00857a', cycles: 1, density: 5, duration: 6, fps: 15,
    },
    pendulum: {
      mode: 'builder', rodColor: '#ffb70f', rodWidth: 8, rodLength: 0.52,
      bobShape: 'circle', bobSize: 88, bobColor: '#00857a', bobInner: '#ffb70f',
      bobInnerScale: 0.86, bobInnerOffsetX: 0,
    },
    theme: theme({ ...baseOptions, backdrop: 'loop', bottomColor: '#050505' }),
  },
  night: {
    name: 'Night',
    dial: {
      mode: 'procedural', anim: 'drift', c1: '#d9a24a', c2: '#f4efe1',
      c3: '#050914', cycles: 1, density: 3, duration: 8, fps: 15,
    },
    pendulum: {
      mode: 'builder', rodColor: '#8b8e98', rodWidth: 4, rodLength: 0.66,
      bobShape: 'circle', bobSize: 42, bobColor: '#d9a24a', bobInner: '#f4efe1',
      bobInnerScale: 0.68, bobInnerOffsetX: 0,
    },
    theme: theme({
      ...baseOptions, accent: '#d9a24a', background: '#050914', hourColor: '#f4efe1',
      minuteColor: '#f4efe1', hourWidth: 14, hourLength: 0.5, minuteLength: 0.82,
      secondVisible: true, secondWidth: 3, secondLength: 0.9, glow: true,
      shape: 'spindle', markings: 'numerals', dialColor: '#f6f2e8', period: 1.15,
      amplitude: 11, pivotY: 0.04, backdrop: 'loop', bottomColor: '#050914',
      twinkle: true, ambientGlow: true,
    }),
  },
});

export function createInitialState(templateKey = 'kitchen-pop') {
  const selected = TEMPLATES[templateKey];
  return {
    name: selected.name,
    creator: {
      artist: '',
    },
    dial: {
      ...structuredClone(selected.dial),
      mediaName: '',
      mediaLoaded: false,
      mediaKind: null,
      mediaDuration: null,
      mediaScale: 1,
      mediaX: 0,
      mediaY: 0,
      watermark: {
        enabled: false,
        text: '',
        color: '#ffffff',
        opacity: 0.78,
      },
    },
    pendulum: {
      ...structuredClone(selected.pendulum),
      imageLoaded: false,
      imageName: '',
      imageHasAlpha: true,
    },
    theme: structuredClone(selected.theme),
  };
}

export function applyTemplate(current, templateKey, preserveName = false) {
  const selected = TEMPLATES[templateKey];
  if (!selected) return current;
  const fresh = createInitialState(templateKey);
  fresh.creator = structuredClone(current.creator || fresh.creator);
  fresh.dial.watermark = structuredClone(current.dial?.watermark || fresh.dial.watermark);
  return preserveName ? { ...fresh, name: current.name } : fresh;
}

export function toThemeJson(state) {
  const { theme: current } = state;
  return {
    name: state.name,
    creator: {
      artist: state.creator?.artist || '',
      watermark: state.dial?.watermark?.text || '',
      watermark_enabled: Boolean(state.dial?.watermark?.enabled),
      watermark_color: state.dial?.watermark?.color || '#ffffff',
      watermark_opacity: state.dial?.watermark?.opacity ?? 0.78,
    },
    accent: current.accent,
    background: current.background,
    hands: structuredClone(current.hands),
    dial: structuredClone(current.dial),
    pendulum: {
      period_s: current.pendulum.period_s,
      amplitude_deg: current.pendulum.amplitude_deg,
      pivot: [current.pendulum.pivot_x, current.pendulum.pivot_y],
      rod_length: current.pendulum.rod_length,
    },
    bottom: structuredClone(current.bottom),
    ambiance: structuredClone(current.ambiance),
  };
}
