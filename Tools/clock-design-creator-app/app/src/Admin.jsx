import React, { useEffect, useState } from 'react';
import {
  Check, CircleGauge, ClipboardCheck, Download, Eye, EyeOff, Flag, History,
  House, LogOut, RefreshCw, RotateCcw, ShieldCheck, UserCheck, UserRound, UserX, X,
} from 'lucide-react';
import { apiRequest } from './api.js';

const TABS = [
  ['review', ClipboardCheck, 'Review'],
  ['reports', Flag, 'Reports'],
  ['designs', Eye, 'Designs'],
  ['users', UserRound, 'Artists'],
  ['audit', History, 'Audit'],
];

function ActionDialog({ action, busy, error, onClose, onConfirm }) {
  const [reason, setReason] = useState('');
  useEffect(() => setReason(''), [action]);
  if (!action) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal-panel admin-action-dialog" role="dialog" aria-modal="true" aria-label={action.title}>
        <header><h2>{action.title}</h2><button className="icon-button" type="button" title="Close" onClick={onClose}><X size={17} /></button></header>
        <form className="dialog-form" onSubmit={(event) => { event.preventDefault(); onConfirm(reason); }}>
          <p className="dialog-note">{action.label}</p>
          <label><span>Reason</span><textarea autoFocus required minLength="3" maxLength="500" rows="4" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          {error && <div className="notice error">{error}</div>}
          <button className="primary-button dialog-submit" type="submit" disabled={busy || reason.trim().length < 3}>{busy ? 'Applying...' : action.confirmLabel}</button>
        </form>
      </section>
    </div>
  );
}

function AdminHeader({ session, onHome, onCreate, onCommunity, onBuild, onLogout }) {
  return (
    <header className="community-topbar">
      <button className="brand brand-button" type="button" title="Pi Klydo Clock home" onClick={onHome}><CircleGauge size={22} /><strong>Pi Klydo Clock</strong></button>
      <nav className="page-switch" aria-label="Application pages">
        <button type="button" title="Home" onClick={onHome}><House size={14} /></button>
        <button type="button" onClick={onCreate}>Designer</button>
        <button type="button" onClick={onCommunity}>Community</button>
        <button type="button" onClick={onBuild}>Build</button>
        <button type="button" className="active">Admin</button>
      </nav>
      <div className="topbar-spacer" />
      <span className="artist-chip"><ShieldCheck size={14} />{session.user.artistName}</span>
      <button className="icon-button" type="button" title="Sign out" onClick={onLogout}><LogOut size={16} /></button>
    </header>
  );
}

export function AdminPage({ session, onHome, onCreate, onCommunity, onBuild, onLogout }) {
  const [tab, setTab] = useState('review');
  const [data, setData] = useState({ summary: null, reports: [], designs: [], users: [], actions: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [summary, reports, designs, users, actions] = await Promise.all([
        apiRequest('/api/admin/summary'),
        apiRequest('/api/admin/reports?status=all'),
        apiRequest('/api/admin/designs?status=all'),
        apiRequest('/api/admin/users'),
        apiRequest('/api/admin/actions'),
      ]);
      setData({ summary: summary.summary, reports: reports.reports, designs: designs.designs, users: users.users, actions: actions.actions });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const confirmAction = async (reason) => {
    setActionBusy(true);
    setActionError('');
    try {
      await apiRequest(pending.path, {
        method: 'POST',
        body: pending.body(reason),
        csrfToken: session.csrfToken,
      });
      setPending(null);
      await load();
    } catch (requestError) {
      setActionError(requestError.message);
    } finally {
      setActionBusy(false);
    }
  };

  const designAction = (design, status) => {
    const labels = {
      published: design.status === 'pending_review' ? ['Approve design', 'Approve'] : ['Restore design', 'Restore'],
      rejected: ['Reject design', 'Reject'],
      hidden: ['Hide design', 'Hide design'],
      pending_review: ['Reopen review', 'Reopen review'],
    };
    const [title, confirmLabel] = labels[status];
    setPending({
      title,
      label: `${design.title} by ${design.artistName}`,
      confirmLabel,
      path: `/api/admin/designs/${design.id}/status`,
      body: (reason) => ({ status, reason }),
    });
  };

  const userAction = (user, status) => setPending({
    title: status === 'suspended' ? 'Suspend artist' : 'Restore artist',
    label: `${user.artistName} (${user.email})`,
    confirmLabel: status === 'suspended' ? 'Suspend artist' : 'Restore artist',
    path: `/api/admin/users/${user.id}/status`,
    body: (reason) => ({ status, reason }),
  });

  const reportAction = (report, status) => setPending({
    title: status === 'resolved' ? 'Resolve report' : 'Dismiss report',
    label: `${report.designTitle}: ${report.reason.replaceAll('_', ' ')}`,
    confirmLabel: status === 'resolved' ? 'Resolve report' : 'Dismiss report',
    path: `/api/admin/reports/${report.id}/resolve`,
    body: (resolution) => ({ status, resolution }),
  });

  const reviewDesigns = data.designs.filter((design) => design.status === 'pending_review');

  return (
    <main className="community-shell admin-shell">
      <AdminHeader session={session} onHome={onHome} onCreate={onCreate} onCommunity={onCommunity} onBuild={onBuild} onLogout={onLogout} />
      <section className="admin-heading">
        <div><h1>Community administration</h1><p>Signed in as {session.user.artistName}</p></div>
        <button className="secondary-button" type="button" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} />Refresh</button>
      </section>
      {data.summary && (
        <section className="admin-metrics" aria-label="Community status">
          <article><span>Open reports</span><strong>{data.summary.openReports}</strong></article>
          <article><span>Awaiting review</span><strong>{data.summary.pendingDesigns}</strong></article>
          <article><span>Published</span><strong>{data.summary.publishedDesigns}</strong></article>
          <article><span>Rejected</span><strong>{data.summary.rejectedDesigns}</strong></article>
          <article><span>Hidden</span><strong>{data.summary.hiddenDesigns}</strong></article>
          <article><span>Active artists</span><strong>{data.summary.activeUsers}</strong></article>
          <article><span>Suspended</span><strong>{data.summary.suspendedUsers}</strong></article>
          <article><span>Downloads</span><strong>{data.summary.totalDownloads}</strong></article>
        </section>
      )}
      <nav className="admin-tabs" aria-label="Administration views">
        {TABS.map(([key, Icon, label]) => <button type="button" className={tab === key ? 'active' : ''} key={key} onClick={() => setTab(key)}><Icon size={15} />{label}</button>)}
      </nav>
      {loading && <div className="gallery-status">Loading administration data...</div>}
      {error && <div className="gallery-status error">{error}</div>}
      {!loading && !error && (
        <section className="admin-content">
          {tab === 'review' && (
            <div className="admin-list review-list">
              {reviewDesigns.length === 0 && <div className="admin-empty">No designs are awaiting review.</div>}
              {reviewDesigns.map((design) => (
                <article key={design.id} className="attention">
                  <div className="review-design-row">
                    <img src={design.previewUrl} alt={`${design.title} preview`} />
                    <div>
                      <div className="admin-row-main"><div><strong>{design.title}</strong><span>by {design.artistName}</span></div><span className="status-badge pending_review">pending review</span></div>
                      <p>{design.description || 'No description provided.'}</p>
                      <div className="admin-meta"><span>{design.license}</span><span>{Math.ceil(design.packageBytes / 1024)} KB</span><span>{new Date(design.createdAt).toLocaleString()}</span></div>
                      <div className="admin-buttons"><a href={design.downloadUrl}><Download size={14} />Download package</a><button type="button" className="approve" onClick={() => designAction(design, 'published')}><Check size={14} />Approve</button><button type="button" className="danger" onClick={() => designAction(design, 'rejected')}><X size={14} />Reject</button></div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
          {tab === 'reports' && (
            <div className="admin-list">
              {data.reports.length === 0 && <div className="admin-empty">No reports.</div>}
              {data.reports.map((report) => (
                <article key={report.id} className={report.status === 'open' ? 'attention' : ''}>
                  <div className="admin-row-main"><div><strong>{report.designTitle}</strong><span>by {report.designArtist}</span></div><span className={`status-badge ${report.status}`}>{report.status}</span></div>
                  <p><b>{report.reason.replaceAll('_', ' ')}</b>{report.details ? `: ${report.details}` : ''}</p>
                  <div className="admin-meta"><span>Reported by {report.reporterName}</span><span>{new Date(report.createdAt).toLocaleString()}</span></div>
                  {report.resolution && <p className="admin-resolution">{report.resolution}</p>}
                  {report.status === 'open' && <div className="admin-buttons"><button type="button" onClick={() => reportAction(report, 'resolved')}>Resolve</button><button type="button" onClick={() => reportAction(report, 'dismissed')}>Dismiss</button>{report.designStatus === 'published' && <button type="button" className="danger" onClick={() => designAction({ id: report.designId, title: report.designTitle, artistName: report.designArtist }, 'hidden')}><EyeOff size={14} />Hide design</button>}</div>}
                </article>
              ))}
            </div>
          )}
          {tab === 'designs' && (
            <div className="admin-list">
              {data.designs.map((design) => (
                <article key={design.id} className={['hidden', 'rejected'].includes(design.status) ? 'muted' : ''}>
                  <div className="admin-design-row"><img src={design.previewUrl} alt="" /><div className="admin-row-main"><div><strong>{design.title}</strong><span>by {design.artistName}</span></div><span className={`status-badge ${design.status}`}>{design.status.replaceAll('_', ' ')}</span></div></div>
                  <div className="admin-meta"><span>{design.openReportCount} open reports</span><span>{design.downloads} downloads</span></div>
                  {design.reviewReason && <p className="admin-resolution">{design.reviewReason}{design.reviewedByName ? ` — ${design.reviewedByName}` : ''}</p>}
                  <div className="admin-buttons">
                    {design.status === 'published' && <button type="button" className="danger" onClick={() => designAction(design, 'hidden')}><EyeOff size={14} />Hide</button>}
                    {design.status === 'hidden' && <button type="button" onClick={() => designAction(design, 'published')}><Eye size={14} />Restore</button>}
                    {design.status === 'pending_review' && <><button type="button" className="approve" onClick={() => designAction(design, 'published')}><Check size={14} />Approve</button><button type="button" className="danger" onClick={() => designAction(design, 'rejected')}><X size={14} />Reject</button></>}
                    {design.status === 'rejected' && <button type="button" onClick={() => designAction(design, 'pending_review')}><RotateCcw size={14} />Reopen review</button>}
                  </div>
                </article>
              ))}
            </div>
          )}
          {tab === 'users' && (
            <div className="admin-list">
              {data.users.map((user) => (
                <article key={user.id} className={user.status === 'suspended' ? 'muted' : ''}>
                  <div className="admin-row-main"><div><strong>{user.artistName}</strong><span>{user.email}</span></div><span className={`status-badge ${user.status}`}>{user.role} · {user.status}</span></div>
                  <div className="admin-meta"><span>{user.designCount} designs</span><span>{user.reportCount} reports submitted</span></div>
                  {user.suspensionReason && <p className="admin-resolution">{user.suspensionReason}</p>}
                  {user.id !== session.user.id && <div className="admin-buttons">{user.status === 'active' ? <button type="button" className="danger" onClick={() => userAction(user, 'suspended')}><UserX size={14} />Suspend</button> : <button type="button" onClick={() => userAction(user, 'active')}><UserCheck size={14} />Restore</button>}</div>}
                </article>
              ))}
            </div>
          )}
          {tab === 'audit' && (
            <div className="admin-list audit-list">
              {data.actions.length === 0 && <div className="admin-empty">No moderation actions.</div>}
              {data.actions.map((action) => <article key={action.id}><div className="admin-row-main"><div><strong>{action.action.replaceAll('_', ' ')}</strong><span>{action.actorName}</span></div><span>{new Date(action.createdAt).toLocaleString()}</span></div><p>{action.reason}</p><div className="admin-meta"><span>{action.targetType}</span><code>{action.targetId}</code></div></article>)}
            </div>
          )}
        </section>
      )}
      <ActionDialog action={pending} busy={actionBusy} error={actionError} onClose={() => setPending(null)} onConfirm={confirmAction} />
    </main>
  );
}
