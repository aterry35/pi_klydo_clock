import { CIRCLE_DIAMETERS, CLOCK, DIAL_SIZE, PENDULUM_SIZE } from './clockConfig.js';
import { colorWithAlpha, hexToRgb, seededRandom } from './utils.js';

// Procedural templates use a stable virtual canvas and are scaled to the JSON output size.
const BASE_DIAL_SIZE = 480;
const BASE_DIAL_CENTER = BASE_DIAL_SIZE / 2;

function endpoint(cx, cy, degrees, length) {
  const angle = degrees * Math.PI / 180;
  return [cx + Math.sin(angle) * length, cy - Math.cos(angle) * length];
}

function hexToHsl(hex) {
  let [red, green, blue] = hexToRgb(hex).map((value) => value / 255);
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const lightness = (max + min) / 2;
  if (max === min) return [0, 0, lightness * 100];
  const difference = max - min;
  const saturation = lightness > 0.5
    ? difference / (2 - max - min)
    : difference / (max + min);
  let hue;
  if (max === red) hue = (green - blue) / difference + (green < blue ? 6 : 0);
  else if (max === green) hue = (blue - red) / difference + 2;
  else hue = (red - green) / difference + 4;
  return [hue * 60, saturation * 100, lightness * 100];
}

function drawMandala(context, phase, dial) {
  for (let layer = 0; layer < 4; layer += 1) {
    const radius = 54 + layer * 54;
    const count = Math.max(3, dial.density + layer * 2);
    const rotation = phase * (layer % 2 ? -1 : 1) + layer * 0.42;
    for (let item = 0; item < count; item += 1) {
      const angle = rotation + item * Math.PI * 2 / count;
      context.save();
      context.translate(BASE_DIAL_CENTER + Math.cos(angle) * radius, BASE_DIAL_CENTER + Math.sin(angle) * radius);
      context.rotate(angle);
      context.fillStyle = colorWithAlpha(layer % 2 ? dial.c2 : dial.c1, 0.92 - layer * 0.13);
      context.beginPath();
      context.ellipse(0, 0, radius * 0.3, radius * 0.115, 0, 0, Math.PI * 2);
      context.fill();
      context.restore();
    }
  }
  context.fillStyle = dial.c1;
  context.beginPath();
  context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, 26, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = dial.c2;
  context.beginPath();
  context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, 12, 0, Math.PI * 2);
  context.fill();
}

function drawBreathing(context, phase, dial) {
  for (let layer = 6; layer >= 0; layer -= 1) {
    const base = (layer + 1) / 7 * 262;
    const radius = base * (1 + 0.07 * Math.sin(phase + layer * 0.9));
    context.fillStyle = colorWithAlpha(layer % 2 ? dial.c1 : dial.c2, 0.32);
    context.beginPath();
    context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, Math.max(2, radius), 0, Math.PI * 2);
    context.fill();
  }
  context.fillStyle = dial.c1;
  context.beginPath();
  context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, 30 * (1 + 0.12 * Math.sin(phase)), 0, Math.PI * 2);
  context.fill();
}

function drawDrift(context, phase, dial) {
  const count = 4 + dial.density;
  for (let item = 0; item < count; item += 1) {
    const xFrequency = 1 + (item % 2);
    const yFrequency = 1 + ((item + 1) % 2);
    const radiusX = 150 - (item * 23) % 70;
    const radiusY = 150 - (item * 31) % 70;
    const x = BASE_DIAL_CENTER + radiusX * Math.sin(xFrequency * phase + item * 2.399);
    const y = BASE_DIAL_CENTER + radiusY * Math.sin(yFrequency * phase + item * 1.111);
    const radius = 18 + (item * 37) % 42;
    context.fillStyle = colorWithAlpha(item % 2 ? dial.c1 : dial.c2, 0.5);
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  }
}

function polygonPath(context, points) {
  context.beginPath();
  context.moveTo(points[0][0], points[0][1]);
  for (const [x, y] of points.slice(1)) context.lineTo(x, y);
  context.closePath();
}

function organicBlobPoints(cx, cy, radiusX, radiusY, phase, wobble = 0.18) {
  const points = [];
  for (let index = 0; index < 96; index += 1) {
    const angle = index / 96 * Math.PI * 2;
    const radius = 1
      + wobble * Math.sin(angle * 3 + phase)
      + wobble * 0.55 * Math.cos(angle * 5 - phase);
    points.push([
      cx + Math.cos(angle) * radiusX * radius,
      cy + Math.sin(angle) * radiusY * radius,
    ]);
  }
  return points;
}

function drawKitchenPop(context, phase, dial) {
  const cream = '#f4d88f';
  const blobs = [
    [dial.c2, 72, 82, 78, 58, 0.2],
    [dial.c1, 156, 331, 98, 64, 1.0],
    [dial.c2, 339, 66, 74, 60, 2.4],
    [cream, 360, 292, 88, 46, 3.1],
    [dial.c2, 40, 298, 82, 108, 4.0],
    [cream, 250, 158, 38, 58, 0.8],
    [dial.c1, 273, 292, 86, 82, 2.1],
    [cream, 470, 406, 70, 52, 4.7],
  ];
  for (const [color, cx, cy, radiusX, radiusY, offset] of blobs) {
    const blobPhase = phase + offset;
    const driftX = Math.sin(phase * 0.7 + blobPhase) * 6;
    const driftY = Math.cos(phase * 0.6 + blobPhase) * 5;
    polygonPath(context, organicBlobPoints(
      cx + driftX, cy + driftY, radiusX, radiusY, blobPhase,
    ));
    context.fillStyle = color;
    context.fill();
  }
  const vignette = context.createRadialGradient(
    BASE_DIAL_CENTER, BASE_DIAL_CENTER, 170,
    BASE_DIAL_CENTER, BASE_DIAL_CENTER, 270,
  );
  vignette.addColorStop(0, 'rgba(0,0,0,0)');
  vignette.addColorStop(1, 'rgba(0,0,0,0.22)');
  context.fillStyle = vignette;
  context.fillRect(0, 0, BASE_DIAL_SIZE, BASE_DIAL_SIZE);
}

function paperCutPoints(radius, wobble, scallops, offset, phase, sway) {
  const points = [];
  const rotation = Math.sin(phase) * Math.PI / 90 * sway;
  for (let index = 0; index < 220; index += 1) {
    const angle = index / 220 * Math.PI * 2 + rotation;
    const edge = radius * (
      1
      + wobble * Math.sin(scallops * angle + offset + phase)
      + wobble * 0.38 * Math.sin((scallops + 5) * angle - offset * 1.7)
    );
    points.push([
      BASE_DIAL_CENTER + Math.cos(angle) * edge,
      BASE_DIAL_CENTER + Math.sin(angle) * edge,
    ]);
  }
  return points;
}

function drawPaperCut(context, phase, dial) {
  const layers = [
    [dial.c2, 1.22, 0.045, 18, 0.6, 1],
    [dial.c1, 1.05, 0.05, 18, 2.1, 1],
    ['#ef9a80', 0.94, 0.05, 16, 4.0, 1],
    ['#faf6ee', 0.84, 0.052, 16, 1.2, 1],
    ['#2e8f7f', 0.74, 0.055, 15, 3.3, -1],
    ['#a5d3bf', 0.64, 0.055, 14, 0.9, -1],
    [dial.c3, 0.53, 0.06, 13, 5.1, -1],
    ['#14675a', 0.43, 0.062, 12, 2.6, 1],
    [dial.c1, 0.3, 0.08, 11, 0.4, 1],
    ['#faf6ee', 0.2, 0.1, 10, 3.8, 1],
    [dial.c1, 0.105, 0.12, 9, 1.5, 1],
  ];
  for (const [color, radius, wobble, scallops, offset, sway] of layers) {
    context.save();
    context.shadowColor = 'rgba(8,18,24,0.35)';
    context.shadowBlur = 8;
    context.shadowOffsetY = 6;
    polygonPath(context, paperCutPoints(
      radius * BASE_DIAL_SIZE / 2, wobble, scallops, offset, phase, sway,
    ));
    context.fillStyle = color;
    context.fill();
    context.restore();
  }
}

function drawWaves(context, phase, dial) {
  for (let row = 0; row < 6; row += 1) {
    const baseY = 56 + row * 74;
    const amplitude = 16 + row * 5;
    const direction = row % 2 ? -1 : 1;
    context.fillStyle = colorWithAlpha(row % 2 ? dial.c1 : dial.c2, 0.55);
    context.beginPath();
    context.moveTo(0, BASE_DIAL_SIZE);
    for (let x = 0; x <= BASE_DIAL_SIZE; x += 10) {
      context.lineTo(x, baseY + amplitude * Math.sin(x * 0.02 + direction * phase + row * 1.3));
    }
    context.lineTo(BASE_DIAL_SIZE, BASE_DIAL_SIZE);
    context.closePath();
    context.fill();
  }
}

function drawColorCycle(context, phase, dial) {
  const [baseHue, baseSaturation, baseLightness] = hexToHsl(dial.c1);
  const saturation = Math.max(35, baseSaturation);
  const lightness = Math.min(62, Math.max(38, baseLightness));
  const shift = phase / (Math.PI * 2) * 360;
  for (let layer = 5; layer >= 0; layer -= 1) {
    const radius = (layer + 1) / 6 * 255;
    const hue = (baseHue + shift + layer * 26) % 360;
    context.fillStyle = `hsl(${hue}, ${saturation}%, ${lightness - layer * 3}%)`;
    context.beginPath();
    context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, radius, 0, Math.PI * 2);
    context.fill();
  }
}

function drawGrain(context, phase, dial, frameIndex) {
  const random = seededRandom(0x51f15e + frameIndex * 97);
  context.fillStyle = colorWithAlpha(dial.c1, 0.08);
  context.beginPath();
  context.arc(BASE_DIAL_CENTER, BASE_DIAL_CENTER, 205, 0, Math.PI * 2);
  context.fill();
  const gradient = context.createRadialGradient(
    BASE_DIAL_CENTER, BASE_DIAL_CENTER, 110,
    BASE_DIAL_CENTER, BASE_DIAL_CENTER, 265,
  );
  gradient.addColorStop(0, 'rgba(0,0,0,0)');
  gradient.addColorStop(1, 'rgba(0,0,0,0.6)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, BASE_DIAL_SIZE, BASE_DIAL_SIZE);
  for (let point = 0; point < 420; point += 1) {
    const light = random() > 0.5;
    context.fillStyle = light
      ? `rgba(255,255,255,${0.03 + random() * 0.07})`
      : `rgba(0,0,0,${0.04 + random() * 0.08})`;
    context.fillRect(
      random() * BASE_DIAL_SIZE,
      random() * BASE_DIAL_SIZE,
      1 + random(),
      1 + random(),
    );
  }
  if (random() < 0.14) {
    context.fillStyle = colorWithAlpha(dial.c2, 0.14);
    context.fillRect(random() * BASE_DIAL_SIZE, 0, 1.5, BASE_DIAL_SIZE);
  }
  context.fillStyle = `rgba(0,0,0,${0.02 + 0.045 * Math.abs(Math.sin(phase * 7.3))})`;
  context.fillRect(0, 0, BASE_DIAL_SIZE, BASE_DIAL_SIZE);
}

export function drawImportedMedia(context, dial, media) {
  const source = media?.element;
  const width = source ? (source.videoWidth || source.naturalWidth) : 0;
  const height = source ? (source.videoHeight || source.naturalHeight) : 0;
  context.fillStyle = '#101114';
  context.fillRect(0, 0, DIAL_SIZE, DIAL_SIZE);
  if (!source || !width || !height) return;
  const scale = Math.max(DIAL_SIZE / width, DIAL_SIZE / height) * dial.mediaScale;
  const x = DIAL_SIZE / 2 - width * scale / 2 + dial.mediaX * 160;
  const y = DIAL_SIZE / 2 - height * scale / 2 + dial.mediaY * 160;
  context.drawImage(source, x, y, width * scale, height * scale);
}

function drawWatermark(context, circle, watermark) {
  const text = String(watermark?.text || '').trim();
  if (!watermark?.enabled || !text) return;
  context.save();
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  let size = Math.max(11, Math.round(circle.r * 0.09));
  context.font = `600 ${size}px system-ui, sans-serif`;
  while (size > 11 && context.measureText(text).width > circle.r * 1.12) {
    size -= 1;
    context.font = `600 ${size}px system-ui, sans-serif`;
  }
  context.shadowColor = 'rgba(0,0,0,0.65)';
  context.shadowBlur = 4;
  context.fillStyle = colorWithAlpha(watermark.color || '#ffffff', watermark.opacity ?? 0.78);
  context.fillText(text, circle.cx, circle.cy + circle.r * 0.7, circle.r * 1.12);
  context.restore();
}

export function renderDial(context, dial, time, media = null, frameIndex = 0) {
  const duration = Math.max(0.5, dial.duration);
  const phase = (time % duration) / duration * Math.PI * 2 * Math.max(1, Math.round(dial.cycles));
  context.save();
  if (dial.mode === 'media') {
    drawImportedMedia(context, dial, media);
  } else {
    const outputScale = DIAL_SIZE / BASE_DIAL_SIZE;
    context.scale(outputScale, outputScale);
    context.fillStyle = dial.c3;
    context.fillRect(0, 0, BASE_DIAL_SIZE, BASE_DIAL_SIZE);
    if (dial.anim === 'mandala') drawMandala(context, phase, dial);
    if (dial.anim === 'breathing') drawBreathing(context, phase, dial);
    if (dial.anim === 'drift') drawDrift(context, phase, dial);
    if (dial.anim === 'waves') drawWaves(context, phase, dial);
    if (dial.anim === 'colorcycle') drawColorCycle(context, phase, dial);
    if (dial.anim === 'grain') drawGrain(context, phase, dial, frameIndex);
    if (dial.anim === 'kitchen-pop') drawKitchenPop(context, phase, dial);
    if (dial.anim === 'paper-cut') drawPaperCut(context, phase, dial);
  }
  context.restore();
}

export function renderPendulumSprite(context, pendulum, image = null) {
  context.clearRect(0, 0, PENDULUM_SIZE.width, PENDULUM_SIZE.height);
  if (pendulum.mode === 'image' && image) {
    const scale = Math.min(PENDULUM_SIZE.width / image.naturalWidth, PENDULUM_SIZE.height / image.naturalHeight);
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    context.drawImage(image, PENDULUM_SIZE.width / 2 - width / 2, 0, width, height);
    return;
  }

  const centerX = PENDULUM_SIZE.width / 2;
  const rodEnd = Math.min(
    PENDULUM_SIZE.height - 70,
    pendulum.rodLength * PENDULUM_SIZE.height,
  );
  context.lineCap = 'round';
  context.strokeStyle = pendulum.rodColor;
  context.lineWidth = pendulum.rodWidth;
  context.beginPath();
  context.moveTo(centerX, 4);
  context.lineTo(centerX, rodEnd);
  context.stroke();
  const radius = pendulum.bobSize;
  const bobY = Math.min(PENDULUM_SIZE.height - 8 - radius, rodEnd + radius * 0.85);
  context.save();
  context.translate(centerX, bobY);
  context.fillStyle = pendulum.bobColor;
  context.strokeStyle = pendulum.bobColor;
  if (pendulum.bobShape === 'circle') {
    context.beginPath();
    context.arc(0, 0, radius, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = pendulum.bobInner;
    context.beginPath();
    const innerScale = Math.min(0.95, Math.max(0.1, pendulum.bobInnerScale ?? 0.68));
    const innerOffsetX = Math.min(radius * 0.75, Math.max(-radius * 0.75, pendulum.bobInnerOffsetX ?? 0));
    context.arc(innerOffsetX, 0, radius * innerScale, 0, Math.PI * 2);
    context.fill();
  } else if (pendulum.bobShape === 'ring') {
    context.lineWidth = Math.max(6, radius * 0.32);
    context.beginPath();
    context.arc(0, 0, radius * 0.8, 0, Math.PI * 2);
    context.stroke();
    context.fillStyle = pendulum.bobInner;
    context.beginPath();
    context.arc(0, 0, radius * 0.24, 0, Math.PI * 2);
    context.fill();
  } else if (pendulum.bobShape === 'diamond') {
    context.beginPath();
    context.moveTo(0, -radius);
    context.lineTo(radius * 0.75, 0);
    context.lineTo(0, radius);
    context.lineTo(-radius * 0.75, 0);
    context.closePath();
    context.fill();
  } else {
    context.beginPath();
    context.moveTo(0, -radius * 1.25);
    context.quadraticCurveTo(radius * 0.9, -radius * 0.35, radius * 0.72, radius * 0.35);
    context.arc(0, radius * 0.35, radius * 0.72, 0, Math.PI);
    context.quadraticCurveTo(-radius * 0.9, -radius * 0.35, 0, -radius * 1.25);
    context.fill();
  }
  context.restore();
}

function handPolygon(cx, cy, degrees, length, width, scale = 1) {
  const angle = degrees * Math.PI / 180;
  const sine = Math.sin(angle);
  const cosine = Math.cos(angle);
  const base = width * scale;
  const point = (distance, side) => [cx + distance * sine + side * cosine, cy - distance * cosine + side * sine];
  const tail = length * 0.16 * scale;
  return [
    point(length, 0), point(length * 0.8, base * 0.3), point(length * 0.28, base * 0.5),
    point(0, base * 0.42), point(-tail, 0), point(0, -base * 0.42),
    point(length * 0.28, -base * 0.5), point(length * 0.8, -base * 0.3),
  ];
}

function fillPolygon(context, points) {
  context.beginPath();
  context.moveTo(...points[0]);
  for (const point of points.slice(1)) context.lineTo(...point);
  context.closePath();
  context.fill();
}

function drawMarkings(context, circle, theme) {
  const mode = theme.dial.markings;
  if (mode === 'none') return;
  const { cx, cy, r } = circle;
  if (mode === 'ticks' || mode === 'both') {
    const count = Math.max(1, Math.round(theme.dial.count));
    const majorEvery = Math.max(1, Math.floor(count / 12));
    for (let index = 0; index < count; index += 1) {
      const angle = index * 360 / count;
      const major = index % majorEvery === 0;
      context.strokeStyle = theme.dial.color;
      context.lineWidth = major ? 4 : 2;
      context.beginPath();
      context.moveTo(...endpoint(cx, cy, angle, r * (major ? 0.8 : 0.86)));
      context.lineTo(...endpoint(cx, cy, angle, r * 0.92));
      context.stroke();
    }
  }
  if (mode === 'numerals' || mode === 'both') {
    context.fillStyle = colorWithAlpha(theme.dial.color, 0.22);
    for (let index = 0; index < 60; index += 1) {
      const point = endpoint(cx, cy, index * 6, r * 0.9);
      context.beginPath();
      context.arc(...point, index % 5 === 0 ? 3 : 1, 0, Math.PI * 2);
      context.fill();
    }
    context.font = `700 ${Math.round(r * 0.34)}px system-ui, sans-serif`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    const labels = new Map([[12, '12'], [3, '3'], [6, '6'], [9, '9']]);
    for (let hour = 1; hour <= 12; hour += 1) {
      if (labels.has(hour)) {
        context.fillStyle = theme.dial.color;
        context.fillText(labels.get(hour), ...endpoint(cx, cy, (hour % 12) * 30, r * 0.74));
      } else {
        context.fillStyle = colorWithAlpha(theme.dial.color, 0.7);
        context.beginPath();
        context.arc(...endpoint(cx, cy, hour * 30, r * 0.8), 4, 0, Math.PI * 2);
        context.fill();
      }
    }
  }
}

function drawRoundedHand(context, circle, degrees, style) {
  const length = style.length * circle.r;
  const start = endpoint(circle.cx, circle.cy, degrees + 180, length * 0.08);
  const end = endpoint(circle.cx, circle.cy, degrees, length);
  const width = Math.max(3, style.width);
  if (style.glow) {
    context.save();
    context.globalCompositeOperation = 'lighter';
    context.strokeStyle = colorWithAlpha(style.color, 0.17);
    context.lineWidth = width + 8;
    context.lineCap = 'round';
    context.beginPath();
    context.moveTo(...start);
    context.lineTo(...end);
    context.stroke();
    context.restore();
  }
  context.strokeStyle = style.color;
  context.lineWidth = width;
  context.lineCap = 'round';
  context.beginPath();
  context.moveTo(...start);
  context.lineTo(...end);
  context.stroke();
}

function drawHands(context, circle, theme, now) {
  const second = now.getSeconds() + now.getMilliseconds() / 1000;
  const minute = now.getMinutes() + second / 60;
  const hour = (now.getHours() % 12) + minute / 60;
  const hands = [[hour * 30, theme.hands.hour], [minute * 6, theme.hands.minute]];
  for (const [angle, style] of hands) {
    if (style.shape === 'rounded') drawRoundedHand(context, circle, angle, style);
    else {
      if (style.glow) {
        context.save();
        context.globalCompositeOperation = 'lighter';
        context.fillStyle = colorWithAlpha(style.color, 0.15);
        fillPolygon(context, handPolygon(circle.cx, circle.cy, angle, style.length * circle.r, style.width, 1.4));
        context.restore();
      }
      context.fillStyle = style.color;
      fillPolygon(context, handPolygon(circle.cx, circle.cy, angle, style.length * circle.r, style.width));
    }
  }
  const secondStyle = theme.hands.second;
  if (secondStyle.visible) {
    const length = secondStyle.length * circle.r;
    const start = endpoint(circle.cx, circle.cy, second * 6 + 180, length * 0.2);
    const end = endpoint(circle.cx, circle.cy, second * 6, length);
    const width = Math.max(2, secondStyle.width);
    if (secondStyle.glow) {
      context.save();
      context.globalCompositeOperation = 'lighter';
      context.strokeStyle = colorWithAlpha(secondStyle.color, 0.27);
      context.lineWidth = width + 4;
      context.lineCap = 'round';
      context.beginPath();
      context.moveTo(...start);
      context.lineTo(...end);
      context.stroke();
      context.restore();
    }
    context.strokeStyle = secondStyle.color;
    context.lineWidth = width;
    context.lineCap = 'round';
    context.beginPath();
    context.moveTo(...start);
    context.lineTo(...end);
    context.stroke();
    context.fillStyle = secondStyle.color;
    context.beginPath();
    context.arc(...endpoint(circle.cx, circle.cy, second * 6 + 180, length * 0.16), Math.max(4, width + 2), 0, Math.PI * 2);
    context.fill();
  }
  context.fillStyle = theme.accent;
  context.beginPath();
  context.arc(circle.cx, circle.cy, 8, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = theme.background;
  context.beginPath();
  context.arc(circle.cx, circle.cy, 4, 0, Math.PI * 2);
  context.fill();
}

function nightness(hour) {
  const phase = (hour - 13) / 24 * Math.PI * 2;
  return (1 - Math.cos(phase)) / 2;
}

function mixColor(first, second, amount) {
  return first.map((value, index) => Math.round(value + (second[index] - value) * amount));
}

function ambianceColor(darkness) {
  const day = [18, 26, 42];
  const dusk = [40, 22, 30];
  const night = [5, 7, 16];
  return darkness < 0.5
    ? mixColor(day, dusk, darkness / 0.5)
    : mixColor(dusk, night, (darkness - 0.5) / 0.5);
}

function drawAmbiance(context, circle, theme, time, now, strength = 1) {
  const hour = now.getHours() + now.getMinutes() / 60;
  const darkness = nightness(hour);
  if (theme.ambiance.day_night) {
    const [red, green, blue] = ambianceColor(darkness);
    context.fillStyle = `rgba(${red},${green},${blue},${(18 + 42 * darkness) / 255 * strength})`;
    context.beginPath();
    context.arc(circle.cx, circle.cy, circle.r, 0, Math.PI * 2);
    context.fill();
  }
  if (theme.ambiance.glow) {
    for (let step = 8; step > 0; step -= 1) {
      context.fillStyle = colorWithAlpha(theme.accent, 5 * (9 - step) / 255 * strength);
      context.beginPath();
      context.arc(circle.cx, circle.cy, circle.r * step / 8, 0, Math.PI * 2);
      context.fill();
    }
  }
  if (theme.ambiance.twinkle && darkness >= 0.2) {
    for (let index = 0; index < 60; index += 1) {
      const angle = index * 2.399963;
      const radial = Math.sqrt(((index * 137) % 100) / 100) * circle.r * 0.91;
      const x = circle.cx + Math.cos(angle) * radial;
      const y = circle.cy + Math.sin(angle) * radial;
      const size = 0.6 + ((index * 53) % 100) / 100;
      const phase = (index * 0.61) % (Math.PI * 2);
      const alpha = darkness * (0.5 + 0.5 * Math.sin(time * 2 + phase)) * 0.75 * strength;
      context.fillStyle = `rgba(235,240,255,${alpha})`;
      context.beginPath();
      context.arc(x, y, Math.max(1, size), 0, Math.PI * 2);
      context.fill();
    }
  }
}

function fixtureRing(context, circle) {
  if (CLOCK.fixtureBorder <= 0) return;
  context.strokeStyle = '#000000';
  context.lineWidth = CLOCK.fixtureBorder;
  context.beginPath();
  context.arc(circle.cx, circle.cy, circle.r - CLOCK.fixtureBorder / 2, 0, Math.PI * 2);
  context.stroke();
}

function circleFromDiameter(base, value, limits) {
  const requested = Number(value);
  const diameter = Number.isFinite(requested)
    ? Math.min(limits.max, Math.max(limits.min, requested))
    : limits.default;
  return { cx: base.cx, cy: base.cy, r: diameter / 2 };
}

export function layoutCircles(theme) {
  return {
    top: circleFromDiameter(CLOCK.top, theme?.dial?.diameter, CIRCLE_DIAMETERS.dial),
    bottom: circleFromDiameter(CLOCK.bottom, theme?.bottom?.diameter, CIRCLE_DIAMETERS.pendulum),
  };
}

export function renderClock(context, state, dialCanvas, pendulumCanvas, time, now = new Date(), guides = false) {
  const { top, bottom } = layoutCircles(state.theme);
  context.fillStyle = '#000000';
  context.fillRect(0, 0, CLOCK.width, CLOCK.height);

  context.save();
  context.beginPath();
  context.arc(top.cx, top.cy, top.r, 0, Math.PI * 2);
  context.clip();
  context.drawImage(dialCanvas, top.cx - top.r, top.cy - top.r, top.r * 2, top.r * 2);
  drawAmbiance(context, top, state.theme, time, now);
  drawWatermark(context, top, state.dial.watermark);
  context.restore();
  drawMarkings(context, top, state.theme);
  drawHands(context, top, state.theme, now);
  fixtureRing(context, top);

  const bottomMode = state.theme.bottom.backdrop;
  if (bottomMode !== 'none') {
    context.save();
    context.beginPath();
    context.arc(bottom.cx, bottom.cy, bottom.r, 0, Math.PI * 2);
    context.clip();
    if (bottomMode === 'loop') {
      context.drawImage(dialCanvas, bottom.cx - bottom.r, bottom.cy - bottom.r, bottom.r * 2, bottom.r * 2);
    } else {
      context.fillStyle = state.theme.bottom.color;
      context.fillRect(bottom.cx - bottom.r, bottom.cy - bottom.r, bottom.r * 2, bottom.r * 2);
    }
    drawAmbiance(context, bottom, state.theme, time, now, 0.75);
    context.restore();
  }

  const physics = state.theme.pendulum;
  const pivotX = bottom.cx - bottom.r + physics.pivot_x * bottom.r * 2;
  const pivotY = bottom.cy - bottom.r + physics.pivot_y * bottom.r * 2;
  const angle = physics.amplitude_deg * Math.sin(Math.PI * 2 * time / Math.max(0.2, physics.period_s));
  const availableHeight = bottom.cy + bottom.r - pivotY;
  let scale = availableHeight * 0.94 / PENDULUM_SIZE.height;
  if (PENDULUM_SIZE.width * scale > bottom.r * 2 * 0.9) scale = bottom.r * 2 * 0.9 / PENDULUM_SIZE.width;
  context.save();
  context.beginPath();
  context.arc(bottom.cx, bottom.cy, bottom.r, 0, Math.PI * 2);
  context.clip();
  context.translate(pivotX, pivotY);
  context.rotate(angle * Math.PI / 180);
  context.drawImage(pendulumCanvas, -PENDULUM_SIZE.width * scale / 2, 0, PENDULUM_SIZE.width * scale, PENDULUM_SIZE.height * scale);
  context.restore();
  context.fillStyle = state.theme.accent;
  context.beginPath();
  context.arc(pivotX, pivotY, 6, 0, Math.PI * 2);
  context.fill();
  fixtureRing(context, bottom);

  if (guides) drawGuides(context, pivotX, pivotY, top, bottom);
}

function drawGuides(context, pivotX, pivotY, top, bottom) {
  context.save();
  context.setLineDash([5, 5]);
  context.strokeStyle = 'rgba(217,162,74,0.65)';
  context.lineWidth = 1;
  for (const circle of [top, bottom]) {
    context.beginPath();
    context.arc(circle.cx, circle.cy, circle.r, 0, Math.PI * 2);
    context.stroke();
  }
  context.setLineDash([3, 4]);
  context.strokeStyle = 'rgba(110,170,255,0.7)';
  context.beginPath();
  context.moveTo(pivotX, bottom.cy - bottom.r);
  context.lineTo(pivotX, bottom.cy + bottom.r);
  context.stroke();
  context.setLineDash([]);
  context.font = '500 11px ui-monospace, monospace';
  context.textAlign = 'center';
  context.fillStyle = 'rgba(217,162,74,0.85)';
  context.fillText(
    `DIAL BACKGROUND ${Math.round(top.r * 2)} · ${top.cx},${top.cy}`,
    top.cx,
    Math.max(14, top.cy - top.r - 12),
  );
  context.fillText(
    `PENDULUM BACKGROUND ${Math.round(bottom.r * 2)} · ${bottom.cx},${bottom.cy}`,
    bottom.cx,
    bottom.cy - bottom.r - 12,
  );
  context.textAlign = 'left';
  context.fillStyle = 'rgba(110,170,255,0.9)';
  context.fillText('PIVOT', pivotX + 9, pivotY + 4);
  context.restore();
}

export async function seekVideo(video, time) {
  if (!Number.isFinite(video.duration) || video.duration <= 0) return;
  const target = Math.min(Math.max(0, time), Math.max(0, video.duration - 0.001));
  if (Math.abs(video.currentTime - target) < 0.001 && video.readyState >= 2) return;
  await new Promise((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onError);
    };
    const onSeeked = () => { cleanup(); resolve(); };
    const onError = () => { cleanup(); reject(new Error('The imported video could not seek to an export frame.')); };
    video.addEventListener('seeked', onSeeked, { once: true });
    video.addEventListener('error', onError, { once: true });
    video.currentTime = target;
  });
}
