import React, { useEffect, useState } from 'react';
import {
  CircleGauge, Download, Flag, Heart, LogIn, LogOut, MessageCircle, Search,
  UserRound, X,
} from 'lucide-react';
import { apiRequest } from './api.js';

function Modal({ title, onClose, children, wide = false }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className={`modal-panel ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header><h2>{title}</h2><button className="icon-button" type="button" title="Close" onClick={onClose}><X size={17} /></button></header>
        {children}
      </section>
    </div>
  );
}

export function AuthDialog({ open, onClose, onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', artistName: '', watermark: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!open) return null;
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const payload = await apiRequest(`/api/auth/${mode}`, { method: 'POST', body: form });
      onAuthenticated(payload);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };
  const changeMode = (next) => { setMode(next); setError(''); };
  return (
    <Modal title={mode === 'login' ? 'Sign in' : 'Create artist account'} onClose={onClose}>
      <div className="auth-mode segment" aria-label="Account action">
        <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => changeMode('login')}>Sign in</button>
        <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => changeMode('register')}>Register</button>
      </div>
      <form className="dialog-form" onSubmit={submit}>
        {mode === 'register' && (
          <>
            <label><span>Artist name</span><input required minLength="2" maxLength="60" value={form.artistName} onChange={(event) => setForm({ ...form, artistName: event.target.value })} /></label>
            <label><span>Watermark</span><input required minLength="2" maxLength="60" value={form.watermark} onChange={(event) => setForm({ ...form, watermark: event.target.value })} /></label>
          </>
        )}
        <label><span>Email</span><input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
        <label><span>Password</span><input required minLength="10" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
        {mode === 'register' && <p className="dialog-note">Publishing, likes, and comments use this profile. Public gallery browsing does not require an account.</p>}
        {error && <div className="notice error">{error}</div>}
        <button className="primary-button dialog-submit" type="submit" disabled={busy}>{busy ? 'Working...' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
      </form>
    </Modal>
  );
}

export function PublishDialog({ open, onClose, project, session, busy, error, onPublish }) {
  const [description, setDescription] = useState('');
  const [licenseName, setLicenseName] = useState('CC BY-NC 4.0');
  useEffect(() => {
    if (open) setDescription('');
  }, [open]);
  if (!open) return null;
  const watermark = project.dial.watermark;
  const creatorMatches = project.creator.artist.trim() === session.user.artistName;
  const canPublish = creatorMatches && watermark.enabled && watermark.text.trim();
  return (
    <Modal title="Submit for review" onClose={onClose}>
      <form className="dialog-form" onSubmit={(event) => { event.preventDefault(); onPublish({ description, license: licenseName }); }}>
        <div className="publish-identity"><UserRound size={16} /><div><strong>{project.creator.artist || session.user.artistName}</strong><span>Watermark: {watermark.text || 'Not set'}</span></div></div>
        {!canPublish && <div className="notice error">Use your profile artist name and enable a watermark in Setup before submitting.</div>}
        <label><span>Description</span><textarea maxLength="600" rows="4" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What inspired this clock design?" /></label>
        <label><span>License</span><select value={licenseName} onChange={(event) => setLicenseName(event.target.value)}><option>CC BY-NC 4.0</option><option>CC BY 4.0</option><option>Personal use only</option></select></label>
        <p className="dialog-note">The validated ZIP, preview, artist credit, and visible dial watermark will be sent to the administrator. The design stays private until approved.</p>
        {error && <div className="notice error">{error}</div>}
        <button className="primary-button dialog-submit" type="submit" disabled={busy || !canPublish}>{busy ? 'Encoding submission...' : 'Submit for review'}</button>
      </form>
    </Modal>
  );
}

function ReportDialog({ open, design, busy, error, onClose, onSubmit }) {
  const [reason, setReason] = useState('copyright');
  const [details, setDetails] = useState('');
  useEffect(() => {
    if (open) { setReason('copyright'); setDetails(''); }
  }, [open]);
  if (!open) return null;
  return (
    <Modal title="Report design" onClose={onClose}>
      <form className="dialog-form" onSubmit={(event) => { event.preventDefault(); onSubmit({ reason, details }); }}>
        <p className="dialog-note">{design.title} by {design.artistName}</p>
        <label><span>Reason</span><select value={reason} onChange={(event) => setReason(event.target.value)}><option value="copyright">Copyright or ownership</option><option value="inappropriate">Inappropriate content</option><option value="spam">Spam</option><option value="broken_package">Broken package</option><option value="other">Other</option></select></label>
        <label><span>Details</span><textarea rows="5" maxLength="1000" required={reason === 'other'} value={details} onChange={(event) => setDetails(event.target.value)} placeholder="Add information that will help the administrator review this report." /></label>
        {error && <div className="notice error">{error}</div>}
        <button className="primary-button dialog-submit" type="submit" disabled={busy || (reason === 'other' && details.trim().length < 10)}>{busy ? 'Submitting...' : 'Submit report'}</button>
      </form>
    </Modal>
  );
}

function CommunityHeader({ session, onCreate, onAdmin, onAuth, onLogout }) {
  return (
    <header className="community-topbar">
      <div className="brand"><CircleGauge size={22} /><strong>Clock Design Creator</strong></div>
      <nav className="page-switch" aria-label="Application pages">
        <button type="button" onClick={onCreate}>Designer</button>
        <button type="button" className="active">Community</button>
        {session.user?.role === 'admin' && <button type="button" onClick={onAdmin}>Admin</button>}
      </nav>
      <div className="topbar-spacer" />
      {session.user ? (
        <><span className="artist-chip"><UserRound size={14} />{session.user.artistName}</span><button className="icon-button" type="button" title="Sign out" onClick={onLogout}><LogOut size={16} /></button></>
      ) : <button className="secondary-button" type="button" onClick={onAuth}><LogIn size={15} />Sign in</button>}
    </header>
  );
}

function DesignDetail({ designId, session, onAuth, onClose, onChanged }) {
  const [design, setDesign] = useState(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState('');
  const [reported, setReported] = useState(false);
  const load = async () => {
    try { setDesign((await apiRequest(`/api/designs/${designId}`)).design); }
    catch (requestError) { setError(requestError.message); }
  };
  useEffect(() => { load(); }, [designId]);
  const submitComment = async (event) => {
    event.preventDefault();
    if (!session.user) { onAuth(); return; }
    setBusy(true);
    setError('');
    try {
      await apiRequest(`/api/designs/${designId}/comments`, { method: 'POST', body: { body: comment }, csrfToken: session.csrfToken });
      setComment('');
      await load();
      onChanged();
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };
  const openReport = () => {
    if (!session.user) { onAuth(); return; }
    setReportError('');
    setReportOpen(true);
  };
  const submitReport = async (payload) => {
    setReportBusy(true);
    setReportError('');
    try {
      await apiRequest(`/api/designs/${designId}/reports`, { method: 'POST', body: payload, csrfToken: session.csrfToken });
      setReportOpen(false);
      setReported(true);
    } catch (requestError) { setReportError(requestError.message); }
    finally { setReportBusy(false); }
  };
  return (
    <Modal title={design?.title || 'Design details'} onClose={onClose} wide>
      {!design ? <div className="gallery-status">{error || 'Loading design...'}</div> : (
        <div className="design-detail">
          <img src={design.previewUrl} alt={`${design.title} clock preview`} />
          <div className="design-detail-content">
            <div className="design-byline"><strong>{design.artistName}</strong><span>{design.license}</span></div>
            <p>{design.description || 'No description provided.'}</p>
            <a className="primary-button download-button" href={design.downloadUrl}><Download size={15} />Export for clock</a>
            <button className="report-button" type="button" onClick={openReport}><Flag size={14} />Report design</button>
            {reported && <div className="notice report-success">Report submitted for administrator review.</div>}
            <h3>Comments ({design.comments.length})</h3>
            <div className="comment-list">
              {design.comments.length === 0 && <p className="empty-comments">No comments yet.</p>}
              {design.comments.map((item) => <article key={item.id}><strong>{item.artistName}</strong><p>{item.body}</p></article>)}
            </div>
            <form className="comment-form" onSubmit={submitComment}>
              <textarea aria-label="Comment" maxLength="500" required value={comment} onChange={(event) => setComment(event.target.value)} placeholder={session.user ? 'Add a comment' : 'Sign in to comment'} />
              <button className="secondary-button" type="submit" disabled={busy}>{busy ? 'Posting...' : 'Comment'}</button>
            </form>
            {error && <div className="notice error">{error}</div>}
          </div>
        </div>
      )}
      {design && <ReportDialog open={reportOpen} design={design} busy={reportBusy} error={reportError} onClose={() => setReportOpen(false)} onSubmit={submitReport} />}
    </Modal>
  );
}

export function CommunityPage({ session, notice, onDismissNotice, onCreate, onAdmin, onAuth, onLogout }) {
  const [designs, setDesigns] = useState([]);
  const [sort, setSort] = useState('new');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ sort, query });
      setDesigns((await apiRequest(`/api/designs?${params}`)).designs);
    } catch (requestError) { setError(requestError.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { const timer = setTimeout(load, 180); return () => clearTimeout(timer); }, [sort, query, session.user?.id]);

  const toggleLike = async (design) => {
    if (!session.user) { onAuth(); return; }
    try {
      const payload = await apiRequest(`/api/designs/${design.id}/like`, {
        method: design.likedByMe ? 'DELETE' : 'PUT', csrfToken: session.csrfToken,
      });
      setDesigns((current) => current.map((item) => item.id === design.id ? { ...item, likedByMe: payload.liked, likeCount: payload.likeCount } : item));
    } catch (requestError) { setError(requestError.message); }
  };

  return (
    <main className="community-shell">
      <CommunityHeader session={session} onCreate={onCreate} onAdmin={onAdmin} onAuth={onAuth} onLogout={onLogout} />
      <section className="gallery-toolbar">
        <div><h1>Community clock designs</h1><p>Browse artist-made packages validated for the Pi Klydo Clock.</p></div>
        <label className="gallery-search"><Search size={16} /><input aria-label="Search designs" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title or artist" /></label>
        <div className="segment gallery-sort" aria-label="Gallery sort"><button className={sort === 'new' ? 'active' : ''} type="button" onClick={() => setSort('new')}>Newest</button><button className={sort === 'popular' ? 'active' : ''} type="button" onClick={() => setSort('popular')}>Popular</button></div>
      </section>
      {notice && <div className="community-notice notice report-success">{notice}<button className="icon-button" type="button" title="Dismiss" onClick={onDismissNotice}><X size={14} /></button></div>}
      {loading && <div className="gallery-status">Loading designs...</div>}
      {error && <div className="gallery-status error">{error}</div>}
      {!loading && !error && designs.length === 0 && <div className="gallery-status">No matching designs.</div>}
      <section className="design-grid" aria-label="Community designs">
        {designs.map((design) => (
          <article className="design-card" key={design.id}>
            <button className="preview-button" type="button" onClick={() => setSelected(design.id)}><img src={design.previewUrl} alt={`${design.title} clock preview`} /></button>
            <div className="design-card-body">
              <div className="design-title"><div><h2>{design.title}</h2><p>by {design.artistName}</p></div><a className="icon-button" title="Download design ZIP" href={design.downloadUrl}><Download size={16} /></a></div>
              <p className="design-description">{design.description || 'Clock-ready community design.'}</p>
              <div className="design-actions"><button type="button" className={design.likedByMe ? 'liked' : ''} onClick={() => toggleLike(design)}><Heart size={15} fill={design.likedByMe ? 'currentColor' : 'none'} />{design.likeCount}</button><button type="button" onClick={() => setSelected(design.id)}><MessageCircle size={15} />{design.commentCount}</button><span>{design.downloads} downloads</span></div>
            </div>
          </article>
        ))}
      </section>
      {selected && <DesignDetail designId={selected} session={session} onAuth={onAuth} onClose={() => setSelected(null)} onChanged={load} />}
    </main>
  );
}
