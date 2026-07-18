import React, { useState } from 'react';
import {
  ArrowRight, Brush, CheckCircle2, CircleGauge, Clock3, Code2, Cpu,
  Download, ExternalLink, Github, Hammer, HardDrive, Heart, Layers3,
  Menu, Monitor, Palette, ShieldCheck, UploadCloud, Wifi, X,
} from 'lucide-react';
import { VIEW_PATHS } from './routes.js';

const REPOSITORY_URL = 'https://github.com/aterry35/pi_klydo_clock';
const CONTACT_EMAIL = 'agnel.terry@gmail.com';

function RouteLink({ view, onNavigate, className = '', children, ...props }) {
  return (
    <a
      className={className}
      href={VIEW_PATHS[view]}
      onClick={(event) => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onNavigate(view);
      }}
      {...props}
    >
      {children}
    </a>
  );
}

function SiteHeader({ active, onNavigate }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const go = (view) => {
    setMenuOpen(false);
    onNavigate(view);
  };
  const links = [
    ['home', 'Home'],
    ['artists', 'For artists'],
    ['community', 'Community'],
    ['build', 'Build the clock'],
  ];

  return (
    <header className="site-header">
      <RouteLink view="home" onNavigate={go} className="site-brand" aria-label="Pi Klydo Clock home">
        <span className="site-brand-mark"><CircleGauge size={21} /></span>
        <span><strong>Pi Klydo Clock</strong><small>Open art clock</small></span>
      </RouteLink>
      <nav className={menuOpen ? 'site-nav open' : 'site-nav'} aria-label="Main navigation">
        {links.map(([view, label]) => (
          <RouteLink key={view} view={view} onNavigate={go} className={active === view ? 'active' : ''}>{label}</RouteLink>
        ))}
      </nav>
      <RouteLink view="designer" onNavigate={go} className="site-create-button">
        <Palette size={16} />Create a design
      </RouteLink>
      <button
        className="site-menu-button"
        type="button"
        title={menuOpen ? 'Close navigation' : 'Open navigation'}
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
    </header>
  );
}

function SiteFooter({ onNavigate }) {
  return (
    <footer className="site-footer">
      <div>
        <CircleGauge size={22} />
        <div><strong>Pi Klydo Clock</strong><span>Open source. Community made. Non-commercial.</span></div>
      </div>
      <nav aria-label="Footer navigation">
        <RouteLink view="artists" onNavigate={onNavigate}>Artist guide</RouteLink>
        <RouteLink view="build" onNavigate={onNavigate}>DIY build</RouteLink>
        <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">GitHub</a>
        <a href={`mailto:${CONTACT_EMAIL}`}>Contact</a>
      </nav>
    </footer>
  );
}

const STARTER_DESIGNS = [
  ['Night', '/images/designs/night.png'],
  ['Kitchen Pop', '/images/designs/kitchen-pop.png'],
  ['Paper Cut', '/images/designs/paper-cut.png'],
  ['Vintage Film', '/images/designs/vintage-film.png'],
];

function CommunityPreview({ onNavigate }) {
  return (
    <section className="site-section community-preview-section">
      <div className="section-heading split-heading">
        <div><span>Clock-ready starters</span><h2>Every clock can carry a different voice.</h2></div>
        <RouteLink view="community" onNavigate={onNavigate} className="text-link">Explore all designs <ArrowRight size={16} /></RouteLink>
      </div>
      <div className="featured-designs">
        {STARTER_DESIGNS.map(([title, previewUrl]) => (
          <RouteLink view="community" onNavigate={onNavigate} className="featured-design" key={title}>
            <img src={previewUrl} alt={`${title} starter clock face`} loading="lazy" />
            <span><strong>{title}</strong><small>Pi Klydo Clock starter</small></span>
          </RouteLink>
        ))}
      </div>
    </section>
  );
}

export function LandingPage({ onNavigate }) {
  return (
    <main className="public-site landing-page">
      <SiteHeader active="home" onNavigate={onNavigate} />
      <section className="landing-hero">
        <div className="hero-copy">
          <span className="hero-kicker">Open-source art, brought to life</span>
          <h1>Pi Klydo Clock</h1>
          <p>Turn original artwork into a living clock face, share it with a creative community, or build the complete Raspberry Pi clock yourself.</p>
          <div className="hero-actions">
            <RouteLink view="designer" onNavigate={onNavigate} className="hero-primary"><Brush size={18} />Create a design</RouteLink>
            <RouteLink view="community" onNavigate={onNavigate} className="hero-secondary">Explore community <ArrowRight size={17} /></RouteLink>
          </div>
        </div>
        <p className="hero-image-note">Original Pi Klydo Clock concept render</p>
      </section>

      <section className="project-principles" aria-label="Project principles">
        <span><Code2 size={18} />Open source</span>
        <span><Heart size={18} />Community led</span>
        <span><Palette size={18} />Artist credited</span>
        <span><Hammer size={18} />Built for makers</span>
      </section>

      <section className="site-section mission-section">
        <div className="mission-statement">
          <span>Not a marketplace</span>
          <h2>A shared canvas for artists and makers.</h2>
        </div>
        <div className="mission-copy">
          <p>Pi Klydo Clock is a community-based, open-source project. It does not currently charge artists, sell contributed designs, run advertising, or generate profit. The goal is to help emerging artists experiment with motion, attribution, and physical display while giving makers a clock they can understand, build, and improve.</p>
          <p>Artists keep ownership of their work and choose the sharing license attached to each design. Every public submission is reviewed before it appears in the community.</p>
        </div>
      </section>

      <section className="participation-band">
        <div className="participation-inner">
          <article>
            <Brush size={28} />
            <span>For artists</span>
            <h2>Make time move in your style.</h2>
            <p>Build a dial, animate it, create a matching pendulum, add your name and watermark, then submit a clock-ready package.</p>
            <RouteLink view="artists" onNavigate={onNavigate} className="text-link">Read the artist guide <ArrowRight size={16} /></RouteLink>
          </article>
          <article>
            <Cpu size={28} />
            <span>For makers</span>
            <h2>Build the physical clock.</h2>
            <p>Print the enclosure, install the open-source renderer on a Raspberry Pi, configure the display, and load community designs.</p>
            <RouteLink view="build" onNavigate={onNavigate} className="text-link">Open the DIY guide <ArrowRight size={16} /></RouteLink>
          </article>
        </div>
      </section>

      <section className="site-section process-section">
        <div className="section-heading"><span>Artist workflow</span><h2>From an idea to a working clock face.</h2></div>
        <ol className="process-steps">
          <li><b>01</b><div><h3>Create</h3><p>Start from a template or bring a still image or short animation into the browser designer.</p></div></li>
          <li><b>02</b><div><h3>Compose</h3><p>Tune the dial, real-time hands, pendulum, palette, artist credit, and watermark.</p></div></li>
          <li><b>03</b><div><h3>Submit</h3><p>Validate the package, choose a sharing license, and send it to the private review queue.</p></div></li>
          <li><b>04</b><div><h3>Share</h3><p>Approved work appears in the gallery where the community can download, like, and discuss it.</p></div></li>
        </ol>
        <RouteLink view="designer" onNavigate={onNavigate} className="section-cta"><UploadCloud size={17} />Open the designer</RouteLink>
      </section>

      <CommunityPreview onNavigate={onNavigate} />

      <section className="build-teaser">
        <div className="build-teaser-image"><img src="/images/enclosure-gallery.png" alt="Three printable Pi Klydo Clock enclosure parts" loading="lazy" /></div>
        <div className="build-teaser-copy">
          <span>Make it physical</span>
          <h2>The case, code, and clock are open.</h2>
          <p>The repository includes the native Raspberry Pi renderer, Wi-Fi recovery, RTC support, design packaging tools, and all three printable enclosure STL files.</p>
          <div>
            <RouteLink view="build" onNavigate={onNavigate} className="hero-primary"><Hammer size={17} />Build the clock</RouteLink>
            <a className="hero-secondary dark" href={REPOSITORY_URL} target="_blank" rel="noreferrer"><Github size={17} />View GitHub</a>
          </div>
        </div>
      </section>

      <section className="open-invitation">
        <span>Soft opening</span>
        <h2>Your experiments can help shape the project.</h2>
        <p>We are inviting artists, animators, illustrators, Raspberry Pi builders, and curious first-time contributors to create, test, and share.</p>
        <RouteLink view="artists" onNavigate={onNavigate} className="hero-primary">Start contributing <ArrowRight size={17} /></RouteLink>
      </section>
      <SiteFooter onNavigate={onNavigate} />
    </main>
  );
}

const ARTIST_STEPS = [
  {
    number: '01',
    title: 'Choose a starting point',
    body: 'Open the designer and select Blank, Paper Cut, Vintage Film, Kitchen Pop, or Night. You can also import your own still image or short video.',
  },
  {
    number: '02',
    title: 'Build the dial and pendulum',
    body: 'Adjust the dial background, animation palette, hand style, pendulum shape, scale, motion, and the two circular backgrounds while watching the live portrait preview.',
  },
  {
    number: '03',
    title: 'Credit your work',
    body: 'Add your artist name and watermark. The credit is embedded in the exported package and remains visible in the community listing.',
  },
  {
    number: '04',
    title: 'Validate and submit',
    body: 'Resolve the export checks, create an artist account, add a description, choose a license, and submit. Your design stays private until an administrator approves it.',
  },
];

export function ArtistsPage({ onNavigate }) {
  return (
    <main className="public-site guide-page artists-page">
      <SiteHeader active="artists" onNavigate={onNavigate} />
      <header className="guide-hero artists-hero">
        <div><span>Artist guide</span><h1>Your artwork can keep time.</h1><p>Create motion art for a physical clock while keeping your name, watermark, and chosen license attached to the work.</p></div>
        <RouteLink view="designer" onNavigate={onNavigate} className="hero-primary"><Brush size={18} />Open the designer</RouteLink>
      </header>

      <section className="site-section guide-intro">
        <div className="section-heading"><span>No installation required</span><h2>The complete workflow runs in your browser.</h2></div>
        <p>The designer renders the same 480 × 800 portrait composition used by the Raspberry Pi clock. It generates a validated ZIP containing the animated dial, transparent pendulum, renderer-compatible theme, preview, and validation report.</p>
        <img src="/images/designer-workspace.jpg" alt="Pi Klydo Clock browser designer workspace" />
      </section>

      <section className="guide-steps-band">
        <div className="site-section">
          <div className="section-heading"><span>Publish in four stages</span><h2>Create carefully. Submit confidently.</h2></div>
          <ol className="guide-steps">
            {ARTIST_STEPS.map((step) => <li key={step.number}><b>{step.number}</b><div><h3>{step.title}</h3><p>{step.body}</p></div></li>)}
          </ol>
        </div>
      </section>

      <section className="site-section output-section">
        <div className="output-copy">
          <span>Expected output</span>
          <h2>One portable, clock-ready package.</h2>
          <p>The exported folder is self-contained. It can be downloaded from the community or copied directly to a Pi without changing the renderer code.</p>
          <ul className="check-list">
            <li><CheckCircle2 size={17} /><code>loop.mp4</code> short H.264 dial animation</li>
            <li><CheckCircle2 size={17} /><code>pendulum.png</code> transparent pendulum artwork</li>
            <li><CheckCircle2 size={17} /><code>theme.json</code> hands, color, credit, and motion</li>
            <li><CheckCircle2 size={17} />Preview image and validation report</li>
          </ul>
        </div>
        <figure><img src="/images/design-gallery.png" alt="Four completed clock and pendulum design packages" loading="lazy" /><figcaption>Included design examples: Night, Kitchen Pop, Paper Cut, and Vintage Film.</figcaption></figure>
      </section>

      <section className="license-band">
        <div className="site-section license-inner">
          <div><ShieldCheck size={26} /><span>Ownership and review</span><h2>You choose how your work is shared.</h2></div>
          <div>
            <p>You retain ownership of your original artwork. At submission, choose <strong>CC BY 4.0</strong>, <strong>CC BY-NC 4.0</strong>, or <strong>Personal use only</strong>. The platform itself does not sell contributed designs.</p>
            <p>Every new design enters a private review queue. Copyright concerns, unsafe material, spam, and broken packages can be rejected or reported. Approved designs display the artist, license, watermark, likes, comments, and download count.</p>
          </div>
        </div>
      </section>

      <section className="open-invitation compact-invitation">
        <span>Ready to make something?</span><h2>Start with a template. Make it unmistakably yours.</h2>
        <RouteLink view="designer" onNavigate={onNavigate} className="hero-primary">Create a clock face <ArrowRight size={17} /></RouteLink>
      </section>
      <SiteFooter onNavigate={onNavigate} />
    </main>
  );
}

const BUILD_PARTS = [
  [Cpu, 'Raspberry Pi 3', 'The verified renderer target. A compatible Pi with the same display interfaces may also work after testing.'],
  [Monitor, '7-inch DSI display', '800 × 480 touch display mounted in portrait orientation behind the printed faceplate.'],
  [HardDrive, 'MicroSD and power', 'A reliable microSD card and a regulated 5 V supply rated for the selected Pi and display.'],
  [Clock3, 'DS3231 RTC', 'Optional but recommended for correct time when the clock starts without a network connection.'],
  [Layers3, 'Printed enclosure', 'Frame, faceplate, and rear enclosure from the three included STL files.'],
  [Wifi, 'Local Wi-Fi', 'Used for initial setup, NTP synchronization, SSH maintenance, and copying new designs.'],
];

export function BuildPage({ onNavigate }) {
  return (
    <main className="public-site guide-page build-page">
      <SiteHeader active="build" onNavigate={onNavigate} />
      <header className="guide-hero build-hero">
        <div><span>DIY Raspberry Pi build</span><h1>Build the clock. Keep every layer open.</h1><p>Print the enclosure, install the native renderer, provision Wi-Fi, and load clock faces made by the community.</p></div>
        <a className="hero-primary" href={REPOSITORY_URL} target="_blank" rel="noreferrer"><Github size={18} />Open the repository</a>
      </header>

      <section className="site-section build-proof">
        <img src="/images/pi-klydo-prototype.jpg" alt="Working Pi Klydo Clock prototype on a portrait display" loading="lazy" />
        <div><span>Working prototype</span><h2>A native clock renderer, not a browser kiosk.</h2><p>The Raspberry Pi composites real-time analog hands over a looping dial animation and renders a separately animated pendulum. Designs remain removable folders rather than hardcoded application assets.</p><p>The current hardware geometry uses a 480 × 800 portrait display with a 400 px upper dial and 300 px lower pendulum background.</p></div>
      </section>

      <section className="parts-band">
        <div className="site-section">
          <div className="section-heading"><span>Hardware checklist</span><h2>What you need for the reference build.</h2></div>
          <div className="parts-grid">
            {BUILD_PARTS.map(([Icon, title, body]) => <article key={title}><Icon size={23} /><h3>{title}</h3><p>{body}</p></article>)}
          </div>
        </div>
      </section>

      <section className="site-section enclosure-section">
        <div className="section-heading split-heading"><div><span>3D-printable enclosure</span><h2>Three files form the complete case.</h2></div><a className="text-link" href={`${REPOSITORY_URL}/tree/main/3d_enclosure`} target="_blank" rel="noreferrer">View STL files <ExternalLink size={15} /></a></div>
        <img src="/images/enclosure-gallery.png" alt="Clock frame, faceplate, and back enclosure STL previews" loading="lazy" />
        <div className="enclosure-files">
          <span><code>clock_frame.stl</code> outer frame and surround</span>
          <span><code>clock_face.stl</code> front insert with two circular openings</span>
          <span><code>clock_back.stl</code> rear enclosure shell</span>
        </div>
      </section>

      <section className="install-band">
        <div className="site-section install-inner">
          <div className="section-heading"><span>Software installation</span><h2>Clone, install, and reboot.</h2></div>
          <div className="install-layout">
            <ol className="build-steps">
              <li><b>01</b><div><h3>Prepare Raspberry Pi OS</h3><p>Flash a current supported Raspberry Pi OS image, enable SSH, and connect the DSI display.</p></div></li>
              <li><b>02</b><div><h3>Install Pi Klydo Clock</h3><p>Clone the public repository and run the idempotent installer from the project root.</p></div></li>
              <li><b>03</b><div><h3>Set portrait rotation</h3><p>Apply the documented DSI rotation and touch calibration for your exact panel.</p></div></li>
              <li><b>04</b><div><h3>Verify the clock</h3><p>Check the renderer service, dial registration, Wi-Fi recovery, and RTC before closing the enclosure.</p></div></li>
            </ol>
            <div className="command-panel">
              <span>Install from GitHub</span>
              <pre><code>{`git clone https://github.com/aterry35/pi_klydo_clock.git piclock\ncd piclock\nsudo bash scripts/install.sh`}</code></pre>
              <a href={`${REPOSITORY_URL}#install-on-the-pi`} target="_blank" rel="noreferrer">Read complete installation notes <ExternalLink size={14} /></a>
            </div>
          </div>
        </div>
      </section>

      <section className="site-section operation-section">
        <div className="section-heading"><span>Daily operation</span><h2>Designed to recover without a keyboard.</h2></div>
        <div className="operation-columns">
          <article><Wifi size={24} /><h3>Wi-Fi setup and recovery</h3><p>If no known network is available, the clock can create a <code>PiClock-XXXX</code> setup hotspot. A four-second press on the upper dial opens the on-device network recovery panel.</p></article>
          <article><Download size={24} /><h3>Add community designs</h3><p>Copy each complete design folder to the SD card design directory or to <code>~/piclock-designs/</code> over SCP. The renderer discovers new folders when it restarts.</p></article>
          <article><CircleGauge size={24} /><h3>Calibrate the enclosure</h3><p>Use <code>clock.json</code> to adjust global dial and pendulum centers or panel circle correction without editing every design package.</p></article>
        </div>
      </section>

      <section className="build-note">
        <div><ShieldCheck size={24} /><h2>Build and power it responsibly.</h2></div>
        <p>This is an open hardware prototype, not a certified consumer appliance. Confirm power requirements, connector clearance, display temperature, print tolerances, and strain relief for your own components before unattended use.</p>
      </section>

      <section className="open-invitation compact-invitation">
        <span>Choose what it displays</span><h2>Build the hardware, then fill it with community art.</h2>
        <RouteLink view="community" onNavigate={onNavigate} className="hero-primary">Explore designs <ArrowRight size={17} /></RouteLink>
      </section>
      <SiteFooter onNavigate={onNavigate} />
    </main>
  );
}
