import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Check, CircleGauge, Download, Eye, EyeOff, FileImage, Film, Layers3,
  LoaderCircle, LogIn, LogOut, Pause, Play, Settings2, SlidersHorizontal,
  Sparkles, Upload, UploadCloud, UserRound,
} from 'lucide-react';
import { AdminPage } from './Admin.jsx';
import { apiRequest } from './api.js';
import { AuthDialog, CommunityPage, PublishDialog } from './Community.jsx';
import { applyTemplate, createInitialState, TEMPLATES } from './defaults.js';
import { exportDesignPackage, supportsDeterministicH264 } from './exporter.js';
import { renderClock, renderDial, renderPendulumSprite, seekVideo } from './renderer.js';
import {
  CIRCLE_DIAMETERS, CLOCK, DIAL_SIZE, PENDULUM_SIZE, VIDEO_LIMITS,
} from './clockConfig.js';
import { downloadBlob, setNestedValue, slugify } from './utils.js';
import { summarizeValidation, validateProject } from './validation.js';

const SECTIONS = [
  ['setup', Settings2, 'Setup'],
  ['dial', CircleGauge, 'Dial'],
  ['pendulum', Layers3, 'Pendulum'],
  ['theme', SlidersHorizontal, 'Theme'],
  ['export', Download, 'Export'],
];

const TEMPLATE_SWATCHES = {
  blank: ['#8a8f9c', '#3c414d', '#101216'],
  'paper-cut': ['#e8492a', '#2e8f7f', '#f1e6d0'],
  'vintage-film': ['#cfc6b4', '#7d7566', '#151513'],
  'kitchen-pop': ['#00857a', '#ff8200', '#ffb70f'],
  night: ['#d9a24a', '#f4efe1', '#050914'],
};

const ANIMATION_LABELS = {
  mandala: 'Mandala', breathing: 'Breathe', drift: 'Drift', waves: 'Waves',
  colorcycle: 'Color', grain: 'Grain', 'kitchen-pop': 'Kitchen Pop',
  'paper-cut': 'Paper Cut',
};

function Segment({ options, value, onChange, label, className = '' }) {
  return (
    <div className={`segment ${className}`} aria-label={label}>
      {options.map(([option, text]) => (
        <button
          type="button"
          className={value === option ? 'active' : ''}
          key={option}
          onClick={() => onChange(option)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function RangeField({ label, value, min, max, step, onChange, suffix = '', editableOutput = false }) {
  return (
    <label className="range-field">
      <span>{label}</span>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      {editableOutput ? (
        <input
          className="numeric-output"
          aria-label={`${label} value`}
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      ) : <output>{value}{suffix}</output>}
    </label>
  );
}

function ColorField({ label, value, onChange }) {
  return (
    <label className="color-field">
      <input type="color" value={value} onChange={(event) => onChange(event.target.value)} />
      <span>{label}</span>
      <code>{value}</code>
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track"><span /></span>
      <span>{label}</span>
    </label>
  );
}

function PanelHeading({ title, children }) {
  return (
    <header className="panel-heading">
      <h2>{title}</h2>
      <p>{children}</p>
    </header>
  );
}

function SectionLabel({ children }) {
  return <h3 className="section-label">{children}</h3>;
}

function FileButton({ accept, onChange, icon: Icon = Upload, children }) {
  return (
    <label className="file-button">
      <Icon size={15} />
      <span>{children}</span>
      <input type="file" accept={accept} onChange={onChange} />
    </label>
  );
}

export default function App() {
  const [view, setView] = useState(() => (
    window.location.hash === '#admin' ? 'admin'
      : window.location.hash === '#community' ? 'community' : 'designer'
  ));
  const [session, setSession] = useState({ user: null, csrfToken: null, loading: true });
  const [authOpen, setAuthOpen] = useState(false);
  const [publishAfterAuth, setPublishAfterAuth] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishState, setPublishState] = useState({ running: false, error: '' });
  const [communityNotice, setCommunityNotice] = useState('');
  const [project, setProject] = useState(() => createInitialState());
  const [nameEdited, setNameEdited] = useState(false);
  const [section, setSection] = useState('setup');
  const [playing, setPlaying] = useState(true);
  const [showGuides, setShowGuides] = useState(true);
  const [displayTime, setDisplayTime] = useState(0);
  const [resources, setResources] = useState({ dialMedia: null, pendulumImage: null });
  const [webCodecs, setWebCodecs] = useState(null);
  const [notice, setNotice] = useState('');
  const [exportState, setExportState] = useState({ running: false, progress: 0, message: '', completed: false, metadata: null });

  const previewRef = useRef(null);
  const dialCanvasRef = useRef(null);
  const pendulumCanvasRef = useRef(null);
  const timeRef = useRef(0);
  const projectRef = useRef(project);
  const resourcesRef = useRef(resources);
  const playingRef = useRef(playing);
  const guidesRef = useRef(showGuides);
  const exportRef = useRef(exportState.running);

  projectRef.current = project;
  resourcesRef.current = resources;
  playingRef.current = playing;
  guidesRef.current = showGuides;
  exportRef.current = exportState.running || publishState.running;

  useEffect(() => {
    supportsDeterministicH264().then(setWebCodecs);
  }, []);

  useEffect(() => {
    apiRequest('/api/auth/me')
      .then((payload) => setSession({ ...payload, loading: false }))
      .catch(() => setSession({ user: null, csrfToken: null, loading: false }));
  }, []);

  useEffect(() => {
    const onHashChange = () => setView(
      window.location.hash === '#admin' ? 'admin'
        : window.location.hash === '#community' ? 'community' : 'designer',
    );
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    if (!session.loading && view === 'admin' && session.user?.role !== 'admin') {
      setView('community');
      window.location.hash = 'community';
    }
  }, [session.loading, session.user?.role, view]);

  useEffect(() => {
    if (!session.user) return;
    setProject((current) => {
      if (current.creator.artist || current.dial.watermark.text) return current;
      return {
        ...current,
        creator: { artist: session.user.artistName },
        dial: {
          ...current.dial,
          watermark: {
            ...current.dial.watermark,
            enabled: true,
            text: session.user.watermark || session.user.artistName,
          },
        },
      };
    });
  }, [session.user?.id]);

  useEffect(() => () => {
    resourcesRef.current.dialMedia?.url && URL.revokeObjectURL(resourcesRef.current.dialMedia.url);
    resourcesRef.current.pendulumImage?.url && URL.revokeObjectURL(resourcesRef.current.pendulumImage.url);
  }, []);

  useEffect(() => {
    if (view !== 'designer') return undefined;
    dialCanvasRef.current = document.createElement('canvas');
    dialCanvasRef.current.width = DIAL_SIZE;
    dialCanvasRef.current.height = DIAL_SIZE;
    pendulumCanvasRef.current = document.createElement('canvas');
    pendulumCanvasRef.current.width = PENDULUM_SIZE.width;
    pendulumCanvasRef.current.height = PENDULUM_SIZE.height;
    let animationFrame;
    let previous = performance.now();
    let lastLabelUpdate = 0;

    const tick = (now) => {
      const elapsed = Math.min(0.1, (now - previous) / 1000);
      previous = now;
      const currentProject = projectRef.current;
      const currentResources = resourcesRef.current;
      if (playingRef.current && !exportRef.current) {
        if (currentResources.dialMedia?.kind === 'video') {
          timeRef.current = currentResources.dialMedia.element.currentTime || 0;
        } else {
          timeRef.current = (timeRef.current + elapsed) % currentProject.dial.duration;
        }
      }
      const time = timeRef.current;
      renderDial(
        dialCanvasRef.current.getContext('2d'),
        currentProject.dial,
        time,
        currentResources.dialMedia,
        Math.floor(time * currentProject.dial.fps),
      );
      renderPendulumSprite(
        pendulumCanvasRef.current.getContext('2d'),
        currentProject.pendulum,
        currentResources.pendulumImage?.element,
      );
      if (previewRef.current) {
        renderClock(
          previewRef.current.getContext('2d'),
          currentProject,
          dialCanvasRef.current,
          pendulumCanvasRef.current,
          time,
          new Date(),
          guidesRef.current,
        );
      }
      if (now - lastLabelUpdate > 100) {
        setDisplayTime(time);
        lastLabelUpdate = now;
      }
      animationFrame = requestAnimationFrame(tick);
    };
    animationFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationFrame);
  }, [view]);

  const update = (path, value) => {
    setProject((current) => setNestedValue(current, path, value));
    setExportState((current) => ({ ...current, completed: false }));
  };

  const updateName = (value) => {
    setNameEdited(true);
    update('name', value);
  };

  const clearDialMedia = () => {
    const current = resources.dialMedia;
    current?.element?.pause?.();
    if (current?.url) URL.revokeObjectURL(current.url);
    setResources((value) => ({ ...value, dialMedia: null }));
    setProject((value) => ({
      ...value,
      dial: { ...value.dial, mediaLoaded: false, mediaName: '', mediaKind: null, mediaDuration: null },
    }));
  };

  const clearPendulumImage = () => {
    if (resources.pendulumImage?.url) URL.revokeObjectURL(resources.pendulumImage.url);
    setResources((value) => ({ ...value, pendulumImage: null }));
    setProject((value) => ({
      ...value,
      pendulum: { ...value.pendulum, imageLoaded: false, imageName: '', imageHasAlpha: true },
    }));
  };

  const chooseTemplate = (key) => {
    clearDialMedia();
    clearPendulumImage();
    setProject((current) => applyTemplate(current, key, nameEdited));
    timeRef.current = 0;
    setNotice('');
  };

  const importDialMedia = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    clearDialMedia();
    setNotice('Decoding imported media...');
    const url = URL.createObjectURL(file);
    try {
      if (file.type.startsWith('video/')) {
        const video = document.createElement('video');
        video.src = url;
        video.muted = true;
        video.loop = true;
        video.playsInline = true;
        video.preload = 'auto';
        await new Promise((resolve, reject) => {
          video.addEventListener('loadedmetadata', resolve, { once: true });
          video.addEventListener('error', () => reject(new Error('This browser cannot decode the selected video.')), { once: true });
          video.load();
        });
        if (
          !Number.isFinite(video.duration)
          || video.duration < VIDEO_LIMITS.minDuration
          || video.duration > VIDEO_LIMITS.maxDuration
        ) {
          throw new Error(`Choose a short video between ${VIDEO_LIMITS.minDuration} and ${VIDEO_LIMITS.maxDuration} seconds.`);
        }
        const duration = Math.round(video.duration * 100) / 100;
        setResources((value) => ({ ...value, dialMedia: { kind: 'video', element: video, duration, url } }));
        setProject((value) => ({
          ...value,
          dial: {
            ...value.dial, mode: 'media', mediaLoaded: true, mediaName: file.name,
            mediaKind: 'video', mediaDuration: duration, duration,
          },
        }));
        if (playing) await video.play();
      } else {
        const image = new Image();
        image.src = url;
        await image.decode();
        if (!image.naturalWidth || !image.naturalHeight) throw new Error('The selected image has no readable pixels.');
        setResources((value) => ({ ...value, dialMedia: { kind: 'image', element: image, duration: null, url } }));
        setProject((value) => ({
          ...value,
          dial: {
            ...value.dial, mode: 'media', mediaLoaded: true, mediaName: file.name,
            mediaKind: 'image', mediaDuration: null,
          },
        }));
      }
      setNotice('');
    } catch (error) {
      URL.revokeObjectURL(url);
      setNotice(error.message);
    }
  };

  const importPendulum = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    clearPendulumImage();
    const url = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      const probe = document.createElement('canvas');
      probe.width = Math.min(200, image.naturalWidth);
      probe.height = Math.min(260, image.naturalHeight);
      const probeContext = probe.getContext('2d');
      probeContext.drawImage(image, 0, 0, probe.width, probe.height);
      const pixels = probeContext.getImageData(0, 0, probe.width, probe.height).data;
      let hasAlpha = false;
      for (let index = 3; index < pixels.length; index += 4) {
        if (pixels[index] < 250) { hasAlpha = true; break; }
      }
      setResources((value) => ({ ...value, pendulumImage: { element: image, url } }));
      setProject((value) => ({
        ...value,
        pendulum: {
          ...value.pendulum, mode: 'image', imageLoaded: true,
          imageName: file.name, imageHasAlpha: hasAlpha,
        },
      }));
      setNotice('');
    } catch {
      URL.revokeObjectURL(url);
      setNotice('The selected pendulum image could not be decoded.');
    }
  };

  const togglePlayback = async () => {
    const next = !playing;
    setPlaying(next);
    const video = resources.dialMedia?.kind === 'video' ? resources.dialMedia.element : null;
    if (video) {
      if (next) await video.play().catch(() => setNotice('The imported video could not start playback.'));
      else video.pause();
    }
  };

  const scrubTo = async (value) => {
    setPlaying(false);
    resources.dialMedia?.element?.pause?.();
    timeRef.current = value;
    setDisplayTime(value);
    if (resources.dialMedia?.kind === 'video') {
      await seekVideo(resources.dialMedia.element, value % resources.dialMedia.duration).catch((error) => setNotice(error.message));
    }
  };

  const capabilities = { webCodecs: webCodecs === true };
  const checks = useMemo(
    () => validateProject(project, resources, capabilities),
    [project, resources, webCodecs],
  );
  const validation = summarizeValidation(checks);

  const doExport = async () => {
    if (validation.errors || exportState.running) {
      setSection('export');
      return;
    }
    setPlaying(false);
    resources.dialMedia?.element?.pause?.();
    setSection('export');
    setExportState({ running: true, progress: 0, message: 'Preparing export', completed: false, metadata: null });
    try {
      const output = await exportDesignPackage({
        state: project,
        resources: {
          dialMedia: resources.dialMedia,
          pendulumImage: resources.pendulumImage?.element,
        },
        onProgress: (progress, message) => setExportState((current) => ({ ...current, progress, message })),
      });
      downloadBlob(output.blob, output.filename);
      setExportState({ running: false, progress: 1, message: 'Package downloaded', completed: true, metadata: output.metadata });
    } catch (error) {
      setExportState({ running: false, progress: 0, message: error.message, completed: false, metadata: null });
    }
  };

  const changeView = (nextView) => {
    setView(nextView);
    window.location.hash = nextView;
  };

  const handleAuthenticated = (payload) => {
    setSession({ ...payload, loading: false });
    if (publishAfterAuth) {
      setPublishAfterAuth(false);
      setPublishOpen(true);
    }
  };

  const logout = async () => {
    try {
      await apiRequest('/api/auth/logout', { method: 'POST', csrfToken: session.csrfToken });
    } catch (error) {
      setNotice(error.message);
    } finally {
      setSession({ user: null, csrfToken: null, loading: false });
    }
  };

  const openPublish = () => {
    if (!session.user) {
      setPublishAfterAuth(true);
      setAuthOpen(true);
      return;
    }
    setPublishState({ running: false, error: '' });
    setPublishOpen(true);
  };

  const doCommunityPublish = async ({ description, license }) => {
    if (!session.user || validation.errors || publishState.running) return;
    setPlaying(false);
    resources.dialMedia?.element?.pause?.();
    exportRef.current = true;
    setPublishState({ running: true, error: '' });
    try {
      const output = await exportDesignPackage({
        state: project,
        resources: {
          dialMedia: resources.dialMedia,
          pendulumImage: resources.pendulumImage?.element,
        },
        onProgress: (_progress, message) => setPublishState({ running: true, error: '', message }),
      });
      const form = new FormData();
      form.append('title', project.name);
      form.append('description', description);
      form.append('license', license);
      form.append('package', output.blob, output.filename);
      await apiRequest('/api/designs', {
        method: 'POST', body: form, csrfToken: session.csrfToken,
      });
      setPublishOpen(false);
      setPublishState({ running: false, error: '' });
      setCommunityNotice('Design submitted for administrator review. It will appear after approval.');
      changeView('community');
    } catch (error) {
      setPublishState({ running: false, error: error.message });
    } finally {
      exportRef.current = false;
    }
  };

  if (view === 'community') {
    return (
      <>
        <CommunityPage
          session={session}
          notice={communityNotice}
          onDismissNotice={() => setCommunityNotice('')}
          onCreate={() => changeView('designer')}
          onAdmin={() => changeView('admin')}
          onAuth={() => setAuthOpen(true)}
          onLogout={logout}
        />
        <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} onAuthenticated={handleAuthenticated} />
      </>
    );
  }

  if (view === 'admin' && session.user?.role === 'admin') {
    return (
      <AdminPage
        session={session}
        onCreate={() => changeView('designer')}
        onCommunity={() => changeView('community')}
        onLogout={logout}
      />
    );
  }

  return (
    <>
    <main className="app-shell editor-shell">
      <header className="topbar">
        <div className="brand"><CircleGauge size={22} /><strong>Clock Design Creator</strong></div>
        <nav className="page-switch" aria-label="Application pages">
          <button type="button" className="active">Designer</button>
          <button type="button" onClick={() => changeView('community')}>Community</button>
          {session.user?.role === 'admin' && <button type="button" onClick={() => changeView('admin')}>Admin</button>}
        </nav>
        <div className="package-name"><span>Package</span><code>{slugify(project.name) || 'untitled'}/</code></div>
        <div className="topbar-spacer" />
        <span className={`codec-badge ${webCodecs ? 'ready' : ''}`}>{webCodecs ? 'H.264 · exact frames' : 'Checking encoder'}</span>
        <button className="secondary-button" type="button" onClick={openPublish} disabled={exportState.running || publishState.running || validation.errors > 0}>
          <UploadCloud size={16} />Submit
        </button>
        <button className="primary-button" type="button" onClick={doExport} disabled={exportState.running || validation.errors > 0}>
          {exportState.running ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}
          Export ZIP
        </button>
        {session.user ? (
          <><span className="artist-chip"><UserRound size={14} />{session.user.artistName}</span><button className="icon-button" type="button" title="Sign out" onClick={logout}><LogOut size={16} /></button></>
        ) : <button className="icon-button" type="button" title="Sign in" onClick={() => setAuthOpen(true)}><LogIn size={16} /></button>}
      </header>

      <div className="workspace">
        <nav className="nav-rail" aria-label="Editor sections">
          {SECTIONS.map(([key, Icon, label]) => (
            <button className={section === key ? 'active' : ''} type="button" key={key} onClick={() => setSection(key)}>
              <Icon size={18} /><span>{label}</span>
            </button>
          ))}
        </nav>

        <section className="preview-stage">
          <canvas ref={previewRef} width={CLOCK.width} height={CLOCK.height} aria-label="Live Pi clock preview" />
          <div className="transport">
            <button className="icon-button" type="button" title={playing ? 'Pause preview' : 'Play preview'} onClick={togglePlayback}>
              {playing ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <input
              aria-label="Animation time"
              type="range"
              min="0"
              max={project.dial.duration}
              step="0.01"
              value={Math.min(displayTime, project.dial.duration)}
              onChange={(event) => scrubTo(Number(event.target.value))}
            />
            <code>{displayTime.toFixed(1)} / {project.dial.duration}s</code>
            <button className={`icon-button ${showGuides ? 'active' : ''}`} type="button" title="Toggle geometry guides" onClick={() => setShowGuides((value) => !value)}>
              {showGuides ? <Eye size={16} /> : <EyeOff size={16} />}
            </button>
          </div>
        </section>

        <aside className="inspector">
          {notice && <div className="notice">{notice}</div>}
          {section === 'setup' && (
            <SetupPanel project={project} update={update} updateName={updateName} chooseTemplate={chooseTemplate} />
          )}
          {section === 'dial' && (
            <DialPanel project={project} update={update} resources={resources} importMedia={importDialMedia} clearMedia={clearDialMedia} />
          )}
          {section === 'pendulum' && (
            <PendulumPanel project={project} update={update} resources={resources} importImage={importPendulum} clearImage={clearPendulumImage} />
          )}
          {section === 'theme' && <ThemePanel project={project} update={update} />}
          {section === 'export' && (
            <ExportPanel
              checks={checks}
              validation={validation}
              state={exportState}
              slug={slugify(project.name)}
              doExport={doExport}
            />
          )}
        </aside>
      </div>
    </main>
    <AuthDialog open={authOpen} onClose={() => { setAuthOpen(false); setPublishAfterAuth(false); }} onAuthenticated={handleAuthenticated} />
    <PublishDialog
      open={publishOpen}
      onClose={() => setPublishOpen(false)}
      project={project}
      session={session}
      busy={publishState.running}
      error={publishState.error}
      onPublish={doCommunityPublish}
    />
    </>
  );
}

function SetupPanel({ project, update, updateName, chooseTemplate }) {
  return (
    <>
      <PanelHeading title="Setup">Name the package and choose an editable starting point.</PanelHeading>
      <SectionLabel>Design name</SectionLabel>
      <input className="text-input" value={project.name} onChange={(event) => updateName(event.target.value)} />
      <div className="slug-row"><span>slug</span><code>{slugify(project.name) || 'invalid'}</code></div>
      <SectionLabel>Creator credit</SectionLabel>
      <label className="stacked-field"><span>Artist name</span><input className="text-input" maxLength="60" value={project.creator.artist} onChange={(event) => update('creator.artist', event.target.value)} /></label>
      <Toggle label="Embed watermark in dial" checked={project.dial.watermark.enabled} onChange={(value) => update('dial.watermark.enabled', value)} />
      <label className="stacked-field"><span>Watermark text</span><input className="text-input" maxLength="60" value={project.dial.watermark.text} onChange={(event) => update('dial.watermark.text', event.target.value)} /></label>
      <ColorField label="Watermark color" value={project.dial.watermark.color} onChange={(value) => update('dial.watermark.color', value)} />
      <RangeField label="Opacity" value={Math.round(project.dial.watermark.opacity * 100)} min={25} max={100} step={1} onChange={(value) => update('dial.watermark.opacity', value / 100)} suffix="%" />
      <SectionLabel>Templates</SectionLabel>
      <div className="template-grid">
        {Object.entries(TEMPLATES).map(([key, template]) => (
          <button type="button" key={key} onClick={() => chooseTemplate(key)}>
            <span className="swatches">{TEMPLATE_SWATCHES[key].map((color) => <i style={{ background: color }} key={color} />)}</span>
            <strong>{template.name}</strong>
            <small>{ANIMATION_LABELS[template.dial.anim] || template.dial.anim}</small>
          </button>
        ))}
      </div>
      <div className="info-band">Exports a validated design folder containing H.264 video, a transparent pendulum, and renderer-compatible JSON.</div>
    </>
  );
}

function DialPanel({ project, update, resources, importMedia, clearMedia }) {
  const dial = project.dial;
  return (
    <>
      <PanelHeading title="Dial animation">A deterministic {DIAL_SIZE} x {DIAL_SIZE} loop. Clock hands are rendered by the Pi.</PanelHeading>
      <SectionLabel>Background circle</SectionLabel>
      <RangeField
        label="Dial diameter"
        value={project.theme.dial.diameter}
        min={CIRCLE_DIAMETERS.dial.min}
        max={CIRCLE_DIAMETERS.dial.max}
        step={2}
        onChange={(value) => update('theme.dial.diameter', value)}
        suffix=" px"
        editableOutput
      />
      <Segment label="Dial source" options={[["procedural", 'Procedural'], ['media', 'Import media']]} value={dial.mode} onChange={(value) => update('dial.mode', value)} />
      {dial.mode === 'procedural' ? (
        <>
          <SectionLabel>Animation</SectionLabel>
          <Segment className="animation-types" label="Animation type" options={[
            ['mandala', 'Mandala'], ['breathing', 'Breathe'], ['drift', 'Drift'],
            ['waves', 'Waves'], ['colorcycle', 'Color'], ['grain', 'Grain'],
            ['kitchen-pop', 'Kitchen'], ['paper-cut', 'Paper Cut'],
          ]} value={dial.anim} onChange={(value) => update('dial.anim', value)} />
          <SectionLabel>Palette</SectionLabel>
          <ColorField label="Primary" value={dial.c1} onChange={(value) => update('dial.c1', value)} />
          <ColorField label="Secondary" value={dial.c2} onChange={(value) => update('dial.c2', value)} />
          <ColorField label="Base" value={dial.c3} onChange={(value) => update('dial.c3', value)} />
          <RangeField label="Cycles" value={dial.cycles} min={1} max={4} step={1} onChange={(value) => update('dial.cycles', value)} />
          <RangeField label="Density" value={dial.density} min={1} max={10} step={1} onChange={(value) => update('dial.density', value)} />
        </>
      ) : (
        <>
          <FileButton accept="image/*,video/mp4,video/webm,video/quicktime" onChange={importMedia} icon={Film}>Import image or short video</FileButton>
          {resources.dialMedia && (
            <div className="file-status"><Film size={14} /><span>{dial.mediaName}</span><button type="button" onClick={clearMedia}>Remove</button></div>
          )}
          <RangeField label="Scale" value={dial.mediaScale} min={1} max={3} step={0.01} onChange={(value) => update('dial.mediaScale', value)} />
          <RangeField label="Pan X" value={dial.mediaX} min={-1} max={1} step={0.01} onChange={(value) => update('dial.mediaX', value)} />
          <RangeField label="Pan Y" value={dial.mediaY} min={-1} max={1} step={0.01} onChange={(value) => update('dial.mediaY', value)} />
          {dial.mediaKind === 'video' && <p className="field-note">Video duration is locked to the imported source for a seamless loop.</p>}
        </>
      )}
      <SectionLabel>Loop</SectionLabel>
      <RangeField
        label="Duration"
        value={dial.duration}
        min={VIDEO_LIMITS.minDuration}
        max={VIDEO_LIMITS.maxDuration}
        step={dial.mediaKind === 'video' ? 0.01 : 1}
        onChange={(value) => update('dial.duration', value)}
        suffix="s"
      />
      <RangeField label="Frame rate" value={dial.fps} min={VIDEO_LIMITS.minFps} max={VIDEO_LIMITS.maxFps} step={1} onChange={(value) => update('dial.fps', value)} suffix=" fps" />
    </>
  );
}

function PendulumPanel({ project, update, resources, importImage, clearImage }) {
  const pendulum = project.pendulum;
  const motion = project.theme.pendulum;
  return (
    <>
      <PanelHeading title="Pendulum">A {PENDULUM_SIZE.width} x {PENDULUM_SIZE.height} transparent sprite with its pivot at top center.</PanelHeading>
      <SectionLabel>Background circle</SectionLabel>
      <RangeField
        label="Pendulum diameter"
        value={project.theme.bottom.diameter}
        min={CIRCLE_DIAMETERS.pendulum.min}
        max={CIRCLE_DIAMETERS.pendulum.max}
        step={2}
        onChange={(value) => update('theme.bottom.diameter', value)}
        suffix=" px"
        editableOutput
      />
      <Segment label="Pendulum source" options={[["builder", 'Shape builder'], ['image', 'Import image']]} value={pendulum.mode} onChange={(value) => update('pendulum.mode', value)} />
      {pendulum.mode === 'builder' ? (
        <>
          <SectionLabel>Rod</SectionLabel>
          <RangeField label="Length" value={pendulum.rodLength} min={0.35} max={0.75} step={0.01} onChange={(value) => update('pendulum.rodLength', value)} />
          <RangeField label="Width" value={pendulum.rodWidth} min={2} max={14} step={1} onChange={(value) => update('pendulum.rodWidth', value)} />
          <ColorField label="Rod color" value={pendulum.rodColor} onChange={(value) => update('pendulum.rodColor', value)} />
          <SectionLabel>Bob</SectionLabel>
          <Segment label="Bob shape" options={[["circle", 'Disc'], ['ring', 'Ring'], ['diamond', 'Diamond'], ['drop', 'Drop']]} value={pendulum.bobShape} onChange={(value) => update('pendulum.bobShape', value)} />
          <RangeField
            label="Bob width"
            value={pendulum.bobSize * 2}
            min={40}
            max={PENDULUM_SIZE.width - 40}
            step={2}
            onChange={(value) => update('pendulum.bobSize', value / 2)}
            suffix=" px"
            editableOutput
          />
          <ColorField label="Outer color" value={pendulum.bobColor} onChange={(value) => update('pendulum.bobColor', value)} />
          <ColorField label="Inner color" value={pendulum.bobInner} onChange={(value) => update('pendulum.bobInner', value)} />
          {pendulum.bobShape === 'circle' && (
            <>
              <RangeField label="Inner size" value={Math.round(pendulum.bobInnerScale * 100)} min={10} max={95} step={1} onChange={(value) => update('pendulum.bobInnerScale', value / 100)} suffix="%" />
              <RangeField label="Inner offset" value={pendulum.bobInnerOffsetX} min={-70} max={70} step={1} onChange={(value) => update('pendulum.bobInnerOffsetX', value)} suffix=" px" />
            </>
          )}
        </>
      ) : (
        <>
          <FileButton accept="image/png,image/webp" onChange={importImage} icon={FileImage}>Import transparent image</FileButton>
          {resources.pendulumImage && (
            <div className="file-status"><FileImage size={14} /><span>{pendulum.imageName}</span><button type="button" onClick={clearImage}>Remove</button></div>
          )}
          <p className={`field-note ${pendulum.imageHasAlpha ? 'ok' : 'warning'}`}>{pendulum.imageHasAlpha ? 'Transparency detected.' : 'No transparent pixels detected.'}</p>
        </>
      )}
      <SectionLabel>Motion</SectionLabel>
      <RangeField label="Period" value={motion.period_s} min={0.6} max={3} step={0.05} onChange={(value) => update('theme.pendulum.period_s', value)} suffix="s" />
      <RangeField label="Amplitude" value={motion.amplitude_deg} min={1} max={25} step={0.5} onChange={(value) => update('theme.pendulum.amplitude_deg', value)} suffix="°" />
      <RangeField label="Pivot X" value={motion.pivot_x} min={0.3} max={0.7} step={0.005} onChange={(value) => update('theme.pendulum.pivot_x', value)} />
      <RangeField label="Pivot Y" value={motion.pivot_y} min={0} max={0.15} step={0.005} onChange={(value) => update('theme.pendulum.pivot_y', value)} />
    </>
  );
}

function HandEditor({ label, path, hand, update, second = false }) {
  return (
    <>
      <SectionLabel>{label}</SectionLabel>
      {second && <Toggle label="Visible" checked={hand.visible} onChange={(value) => update(`${path}.visible`, value)} />}
      <ColorField label="Color" value={hand.color} onChange={(value) => update(`${path}.color`, value)} />
      {!second && <Segment label={`${label} shape`} options={[["rounded", 'Baton'], ['spindle', 'Spindle']]} value={hand.shape} onChange={(value) => update(`${path}.shape`, value)} />}
      <RangeField label="Width" value={hand.width} min={1} max={24} step={1} onChange={(value) => update(`${path}.width`, value)} />
      <RangeField label="Length" value={hand.length} min={0.2} max={1} step={0.01} onChange={(value) => update(`${path}.length`, value)} />
      <Toggle label="Glow" checked={hand.glow} onChange={(value) => update(`${path}.glow`, value)} />
    </>
  );
}

function ThemePanel({ project, update }) {
  const theme = project.theme;
  return (
    <>
      <PanelHeading title="Clock theme">Controls rendered live by the Raspberry Pi clock.</PanelHeading>
      <SectionLabel>Colors</SectionLabel>
      <ColorField label="Accent" value={theme.accent} onChange={(value) => update('theme.accent', value)} />
      <ColorField label="Hub background" value={theme.background} onChange={(value) => update('theme.background', value)} />
      <HandEditor label="Hour hand" path="theme.hands.hour" hand={theme.hands.hour} update={update} />
      <HandEditor label="Minute hand" path="theme.hands.minute" hand={theme.hands.minute} update={update} />
      <HandEditor label="Second hand" path="theme.hands.second" hand={theme.hands.second} update={update} second />
      <SectionLabel>Dial markings</SectionLabel>
      <Segment label="Dial markings" options={[["none", 'None'], ['ticks', 'Ticks'], ['numerals', 'Numbers'], ['both', 'Both']]} value={theme.dial.markings} onChange={(value) => update('theme.dial.markings', value)} />
      <ColorField label="Marking color" value={theme.dial.color} onChange={(value) => update('theme.dial.color', value)} />
      <RangeField label="Count" value={theme.dial.count} min={4} max={60} step={1} onChange={(value) => update('theme.dial.count', value)} />
      <SectionLabel>Bottom backdrop</SectionLabel>
      <Segment label="Bottom backdrop" options={[["loop", 'Loop'], ['solid', 'Solid'], ['none', 'None']]} value={theme.bottom.backdrop} onChange={(value) => update('theme.bottom.backdrop', value)} />
      <ColorField label="Solid color" value={theme.bottom.color} onChange={(value) => update('theme.bottom.color', value)} />
      <SectionLabel>Ambiance</SectionLabel>
      <Toggle label="Day and night tint" checked={theme.ambiance.day_night} onChange={(value) => update('theme.ambiance.day_night', value)} />
      <Toggle label="Twinkle overlay" checked={theme.ambiance.twinkle} onChange={(value) => update('theme.ambiance.twinkle', value)} />
      <Toggle label="Ambient accent glow" checked={theme.ambiance.glow} onChange={(value) => update('theme.ambiance.glow', value)} />
    </>
  );
}

function ExportPanel({ checks, validation, state, slug, doExport }) {
  return (
    <>
      <PanelHeading title="Validate and export">The package is checked before and after deterministic encoding.</PanelHeading>
      <div className="validation-list">
        {checks.map((check) => (
          <div className={check.level} key={check.code}>
            {check.level === 'ok' ? <Check size={14} /> : <span>{check.level === 'error' ? '×' : '!'}</span>}
            <p>{check.message}</p>
          </div>
        ))}
      </div>
      <button className="primary-button export-button" type="button" onClick={doExport} disabled={validation.errors > 0 || state.running}>
        {state.running ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}
        {state.running ? 'Encoding...' : `Export ${slug || 'untitled'}.zip`}
      </button>
      {state.running && (
        <div className="progress-block">
          <div><span style={{ width: `${Math.round(state.progress * 100)}%` }} /></div>
          <p>{state.message}</p>
        </div>
      )}
      {!state.running && state.message && !state.completed && <div className="notice error">{state.message}</div>}
      {state.completed && (
        <div className="export-success">
          <Sparkles size={18} />
          <div><strong>Package downloaded</strong><p>{state.metadata.frameCount} exact H.264 frames · {state.metadata.duration}s at {state.metadata.fps} fps</p></div>
        </div>
      )}
      <SectionLabel>Install paths</SectionLabel>
      <div className="install-path"><span>SD card</span><code>piclock-designs/{slug}/</code></div>
      <div className="install-path"><span>SCP</span><code>terry@192.168.1.217:~/piclock-designs/</code></div>
    </>
  );
}
