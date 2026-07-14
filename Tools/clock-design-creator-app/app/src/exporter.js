import { ArrayBufferTarget, Muxer } from 'mp4-muxer';
import { CLOCK, DIAL_SIZE, PENDULUM_SIZE } from './clockConfig.js';
import { renderClock, renderDial, renderPendulumSprite, seekVideo } from './renderer.js';
import { toThemeJson } from './defaults.js';
import { makeZip } from './zip.js';
import { slugify } from './utils.js';
import { validateEncodedVideo } from './validation.js';

export const H264_CODEC = 'avc1.42001f';

function canvasToBlob(canvas, type) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error(`Could not render ${type}.`));
    }, type);
  });
}

export async function supportsDeterministicH264() {
  if (!globalThis.VideoEncoder || !globalThis.VideoFrame) return false;
  try {
    const support = await VideoEncoder.isConfigSupported({
      codec: H264_CODEC,
      width: DIAL_SIZE,
      height: DIAL_SIZE,
      bitrate: 2_500_000,
      framerate: 15,
      avc: { format: 'avc' },
    });
    return support.supported;
  } catch {
    return false;
  }
}

async function encodeDialMp4(state, media, onProgress) {
  const duration = Number(state.dial.duration);
  const fps = Number(state.dial.fps);
  const frameCount = Math.round(duration * fps);
  const frameDuration = Math.round(1_000_000 / fps);
  const canvas = document.createElement('canvas');
  canvas.width = DIAL_SIZE;
  canvas.height = DIAL_SIZE;
  const context = canvas.getContext('2d', { alpha: false, desynchronized: false });
  const target = new ArrayBufferTarget();
  const muxer = new Muxer({
    target,
    video: { codec: 'avc', width: DIAL_SIZE, height: DIAL_SIZE },
    fastStart: 'in-memory',
    firstTimestampBehavior: 'offset',
  });
  let encodedChunks = 0;
  let encoderFailure = null;
  const encoder = new VideoEncoder({
    output: (chunk, metadata) => {
      muxer.addVideoChunk(chunk, metadata);
      encodedChunks += 1;
    },
    error: (error) => { encoderFailure = error; },
  });
  encoder.configure({
    codec: H264_CODEC,
    width: DIAL_SIZE,
    height: DIAL_SIZE,
    bitrate: 2_500_000,
    framerate: fps,
    latencyMode: 'quality',
    avc: { format: 'avc' },
  });

  const importedVideo = state.dial.mode === 'media' && media?.kind === 'video'
    ? media.element
    : null;
  importedVideo?.pause();
  for (let index = 0; index < frameCount; index += 1) {
    const time = index / fps;
    if (importedVideo) await seekVideo(importedVideo, time % media.duration);
    renderDial(context, state.dial, time, media, index);
    const frame = new VideoFrame(canvas, {
      timestamp: index * frameDuration,
      duration: frameDuration,
    });
    encoder.encode(frame, { keyFrame: index === 0 || index % (fps * 2) === 0 });
    frame.close();
    if (encoder.encodeQueueSize > 8) await encoder.flush();
    onProgress?.((index + 1) / frameCount * 0.78);
  }
  await encoder.flush();
  encoder.close();
  if (encoderFailure) throw encoderFailure;
  muxer.finalize();

  const bytes = new Uint8Array(target.buffer);
  const metadata = {
    codec: H264_CODEC,
    width: DIAL_SIZE,
    height: DIAL_SIZE,
    duration,
    fps,
    frameCount: encodedChunks,
    byteLength: bytes.byteLength,
  };
  const validationErrors = validateEncodedVideo(metadata);
  if (validationErrors.length) throw new Error(validationErrors.join(' '));
  return { bytes, metadata };
}

function readmeText(state, slug, metadata) {
  return `${state.name} - Pi Clock design package
Made with Pi Clock Design Creator

Contents
  loop.mp4      ${DIAL_SIZE}x${DIAL_SIZE} H.264 animation, ${metadata.duration}s at ${metadata.fps} fps (${metadata.frameCount} frames)
  pendulum.png  ${PENDULUM_SIZE.width}x${PENDULUM_SIZE.height} transparent sprite, pivot at top center
  theme.json    hands, dial, pendulum motion and ambiance
  preview.png   full ${CLOCK.width}x${CLOCK.height} layout snapshot

Install from the SD card
  Copy this folder to piclock-designs/${slug}/ on the boot partition.

Install over the network
  scp -r ${slug} terry@192.168.1.217:/home/terry/piclock-designs/

Restart piclock-renderer or power-cycle the clock. Design folders are scanned at startup.
`;
}

export async function exportDesignPackage({ state, resources, onProgress }) {
  onProgress?.(0.01, 'Rendering pendulum.png');
  const pendulumCanvas = document.createElement('canvas');
  pendulumCanvas.width = PENDULUM_SIZE.width;
  pendulumCanvas.height = PENDULUM_SIZE.height;
  renderPendulumSprite(pendulumCanvas.getContext('2d'), state.pendulum, resources.pendulumImage);
  const pendulumBlob = await canvasToBlob(pendulumCanvas, 'image/png');

  onProgress?.(0.04, 'Encoding exact H.264 frames');
  const { bytes: videoBytes, metadata } = await encodeDialMp4(
    state,
    resources.dialMedia,
    (progress) => {
      const total = Math.round(state.dial.duration * state.dial.fps);
      const current = Math.min(total, Math.max(1, Math.round(progress / 0.78 * total)));
      onProgress?.(0.04 + progress, `Encoding frame ${current} of ${total}`);
    },
  );

  onProgress?.(0.84, 'Rendering preview.png');
  const dialCanvas = document.createElement('canvas');
  dialCanvas.width = DIAL_SIZE;
  dialCanvas.height = DIAL_SIZE;
  if (resources.dialMedia?.kind === 'video') await seekVideo(resources.dialMedia.element, 0);
  renderDial(dialCanvas.getContext('2d'), state.dial, 0, resources.dialMedia, 0);
  const previewCanvas = document.createElement('canvas');
  previewCanvas.width = CLOCK.width;
  previewCanvas.height = CLOCK.height;
  renderClock(previewCanvas.getContext('2d'), state, dialCanvas, pendulumCanvas, 0, new Date(), false);
  const previewBlob = await canvasToBlob(previewCanvas, 'image/png');

  const slug = slugify(state.name);
  const encoder = new TextEncoder();
  const themeBytes = encoder.encode(`${JSON.stringify(toThemeJson(state), null, 2)}\n`);
  const reportBytes = encoder.encode(`${JSON.stringify({
    format: 'pi-clock-design-v1',
    generated_at: new Date().toISOString(),
    video: metadata,
  }, null, 2)}\n`);
  onProgress?.(0.92, 'Packaging ZIP');
  const zip = makeZip([
    { name: `${slug}/loop.mp4`, data: videoBytes },
    { name: `${slug}/pendulum.png`, data: new Uint8Array(await pendulumBlob.arrayBuffer()) },
    { name: `${slug}/theme.json`, data: themeBytes },
    { name: `${slug}/preview.png`, data: new Uint8Array(await previewBlob.arrayBuffer()) },
    { name: `${slug}/export-report.json`, data: reportBytes },
    { name: `${slug}/README.txt`, data: encoder.encode(readmeText(state, slug, metadata)) },
  ]);
  onProgress?.(1, 'Export complete');
  return { blob: zip, filename: `${slug}.zip`, metadata };
}
