import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, Loader2, Sparkles, CheckCircle, AlertTriangle, Clock, FileText, ClipboardList,
  Download, UserPlus, ChevronDown, ChevronUp, GitBranch, Shield, FolderKanban,
} from 'lucide-react';
import GlassPanel from '../components/ui/GlassPanel';
import {
  getCollaborationActivity, generateMeetingBrief, getReports,
  getProjectMembers, addProjectMember, triggerBriefDownload,
} from '../api/client';
import { apiErrorMessage } from '../lib/auth';
import { useUser } from '../context/UserContext';
import { useProject } from '../context/ProjectContext';

function BriefCard({ brief, expanded, onToggle }) {
  const c = brief.content_json || {};
  return (
    <div className="p-4 rounded-xl border border-cx-border bg-white/40">
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={onToggle} className="min-w-0 text-left flex-1">
          <p className="font-medium text-sm">{brief.title}</p>
          <p className="text-xs text-cx-fgMuted mt-1 line-clamp-2">
            {c.summary || c.body?.slice(0, 160)}
          </p>
          <p className="text-2xs text-cx-fgDim mt-2">
            {c.audience && `${c.audience} · `}
            {new Date(brief.created_at).toLocaleString()}
            {c.confidence != null && ` · ${(c.confidence * 100).toFixed(0)}% confidence`}
          </p>
        </button>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button type="button" onClick={onToggle} className="p-1 text-cx-fgMuted hover:text-cx-accent">
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          <div className="flex gap-1">
            {['markdown', 'docx', 'pdf'].map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => triggerBriefDownload(brief.id, fmt)}
                className="px-2 py-1 rounded-lg border border-cx-border hover:border-cx-accent/30 text-2xs uppercase text-cx-fgMuted hover:text-cx-accent flex items-center gap-1"
              >
                <Download size={12} />
                {fmt === 'markdown' ? 'md' : fmt}
              </button>
            ))}
          </div>
        </div>
      </div>
      {expanded && (
        <div className="mt-4 pt-4 border-t border-cx-line space-y-4 text-sm">
          {c.agenda?.length > 0 && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Agenda</p>
              <ul className="list-disc list-inside text-cx-fgMuted space-y-1">
                {c.agenda.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}
          {c.key_findings?.length > 0 && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Key findings</p>
              <ul className="list-disc list-inside text-cx-fgMuted space-y-1">
                {c.key_findings.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
          {c.decisions_needed?.length > 0 && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Decisions needed</p>
              <ul className="list-disc list-inside text-cx-warn space-y-1">
                {c.decisions_needed.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}
          {c.action_items?.length > 0 && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Action items</p>
              <ul className="text-cx-fgMuted space-y-2">
                {c.action_items.map((item, i) => (
                  <li key={i} className="text-xs">
                    {typeof item === 'object'
                      ? <><strong>{item.owner || 'TBD'}</strong>: {item.task} ({item.due_hint || 'TBD'})</>
                      : item}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {c.body && (
            <div>
              <p className="text-2xs uppercase tracking-wider text-cx-fgDim mb-2">Full brief</p>
              <div className="text-xs text-cx-fgMuted whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed">
                {c.body}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Collaboration() {
  const { displayName } = useUser();
  const { activeProject, activeProjectId, refreshProjects } = useProject();
  const [activity, setActivity] = useState(null);
  const [briefs, setBriefs] = useState([]);
  const [members, setMembers] = useState([]);
  const [memberUsername, setMemberUsername] = useState('');
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('R&D leadership');
  const [lookbackDays, setLookbackDays] = useState(7);
  const [expandedBriefId, setExpandedBriefId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    const tasks = [
      getCollaborationActivity(),
      getReports({ report_type: 'meeting_brief', exclude_meeting_briefs: false }),
    ];
    if (activeProjectId) {
      tasks.push(getProjectMembers(activeProjectId));
    }
    Promise.all(tasks)
      .then(([actRes, reportsRes, membersRes]) => {
        setActivity(actRes.data);
        setBriefs(reportsRes.data || []);
        setMembers(membersRes?.data || []);
      })
      .catch((err) => setError(apiErrorMessage(err, 'Failed to load collaboration data')))
      .finally(() => setLoading(false));
  }, [activeProjectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAddMember = async (e) => {
    e.preventDefault();
    if (!activeProjectId || !memberUsername.trim()) return;
    setAddingMember(true);
    setError('');
    try {
      await addProjectMember(activeProjectId, { username: memberUsername.trim() });
      setMemberUsername('');
      await refreshProjects();
      load();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to add member'));
    } finally {
      setAddingMember(false);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!topic.trim()) return;
    setGenerating(true);
    setError('');
    setSuccess(null);
    try {
      const r = await generateMeetingBrief({
        topic: topic.trim(),
        audience: audience.trim(),
        lookback_days: lookbackDays,
      });
      setSuccess(r.data);
      setExpandedBriefId(r.data.id);
      setTopic('');
      load();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to generate meeting brief'));
    } finally {
      setGenerating(false);
    }
  };

  const isEmptyWorkspace = activity && !activity.recent_documents?.length
    && !activity.recent_agent_runs?.length
    && !activity.recent_workflows?.length;

  if (loading && !activity) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[40vh] text-cx-fgMuted">
        <Loader2 className="animate-spin mr-2" size={20} />
        Loading collaboration hub…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim flex items-center gap-2">
          <Users size={14} /> Decisions
        </p>
        <h2 className="font-display text-xl font-semibold mt-1">Collaboration & Briefs</h2>
        <p className="text-sm text-cx-fgMuted mt-2 max-w-2xl">
          Turn workspace activity into decision-ready meeting briefs — agenda, findings, decisions, and action items —
          scoped to {activeProject ? (
            <span className="text-cx-accent">project {activeProject.name}</span>
          ) : (
            'your personal workspace'
          )}.
        </p>
        {!activeProjectId && (
          <p className="mt-3 text-xs text-cx-fgDim flex items-center gap-2">
            <FolderKanban size={14} />
            Select or create a shared project in the top bar to enable team members and project-scoped activity.
          </p>
        )}
      </GlassPanel>

      {isEmptyWorkspace && (
        <GlassPanel className="border-cx-warn/20 bg-cx-warn/5">
          <p className="text-sm text-cx-fg">
            Your workspace has little recent activity. Meeting briefs work best after you:
          </p>
          <ul className="mt-2 text-sm text-cx-fgMuted list-disc list-inside space-y-1">
            <li><Link to="/data-fabric" className="text-cx-accent hover:underline">Upload or import LIMS data</Link> in Data Fabric</li>
            <li><Link to="/agents/workspace" className="text-cx-accent hover:underline">Run agents</Link> (hypothesis, ADMET, literature)</li>
            <li><Link to="/workflows" className="text-cx-accent hover:underline">Execute a workflow</Link> pipeline</li>
          </ul>
        </GlassPanel>
      )}

      {activeProjectId && (
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4 flex items-center gap-2">
            <Users size={12} /> Project team — {activeProject?.name}
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {members.length === 0 && (
              <span className="text-xs text-cx-fgDim">No members yet — add colleagues by username.</span>
            )}
            {members.map((m) => (
              <span key={m.user_id} className="text-xs px-2 py-1 rounded-lg border border-cx-border bg-white/50">
                {m.full_name || m.username} · {m.role}
              </span>
            ))}
          </div>
          <form onSubmit={handleAddMember} className="flex gap-2">
            <input
              value={memberUsername}
              onChange={(e) => setMemberUsername(e.target.value)}
              placeholder="Add member by username (e.g. scientist)"
              className="flex-1 px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm"
            />
            <button
              type="submit"
              disabled={addingMember}
              className="px-4 py-2 rounded-xl text-sm border border-cx-accent/30 bg-cx-accent/5 text-cx-accent flex items-center gap-2 disabled:opacity-50"
            >
              {addingMember ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
              Add
            </button>
          </form>
        </GlassPanel>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4 flex items-center gap-2">
            <Sparkles size={12} /> Generate meeting brief
          </p>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div>
              <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Meeting topic</label>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                required
                placeholder="e.g. JAK1 program go/no-go — preclinical readout review"
                className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm focus:outline-none focus:border-cx-accent/40"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Audience</label>
                <input
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm"
                />
              </div>
              <div>
                <label className="text-2xs uppercase tracking-wider text-cx-fgDim">Lookback (days)</label>
                <select
                  value={lookbackDays}
                  onChange={(e) => setLookbackDays(Number(e.target.value))}
                  className="mt-1 w-full px-3 py-2 rounded-xl border border-cx-border bg-white/60 text-sm"
                >
                  {[7, 14, 30].map((d) => (
                    <option key={d} value={d}>{d} days</option>
                  ))}
                </select>
              </div>
            </div>
            {error && <p className="text-sm text-cx-danger">{error}</p>}
            {success && (
              <div className="p-3 rounded-xl border border-cx-success/30 bg-cx-success/5 text-sm">
                <p className="flex items-center gap-2 text-cx-success font-medium">
                  <CheckCircle size={16} /> Brief created: {success.title}
                </p>
              </div>
            )}
            <button
              type="submit"
              disabled={generating}
              className="w-full py-2.5 rounded-xl text-sm font-medium border border-cx-accent/30 bg-cx-accent/5 text-cx-accent hover:bg-cx-accent/10 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {generating ? <Loader2 size={16} className="animate-spin" /> : <ClipboardList size={16} />}
              {generating ? 'Synthesizing activity…' : 'Generate meeting brief'}
            </button>
            <p className="text-2xs text-cx-fgDim">
              Pulls uploads, agent runs, workflows, approvals, and risks into an LLM brief. Export as md, docx, or pdf.
            </p>
          </form>
        </GlassPanel>

        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Team activity snapshot</p>
          <div className="grid grid-cols-2 gap-3 text-sm mb-4">
            <div className="p-3 rounded-xl border border-cx-border bg-white/40">
              <Clock size={16} className="text-cx-accent mb-1" />
              <p className="text-2xs text-cx-fgDim">Pending approvals</p>
              <p className="font-semibold">{activity?.pending_approvals?.length ?? 0}</p>
            </div>
            <div className="p-3 rounded-xl border border-cx-border bg-white/40">
              <AlertTriangle size={16} className="text-cx-warn mb-1" />
              <p className="text-2xs text-cx-fgDim">Open risks</p>
              <p className="font-semibold">{activity?.open_risks?.length ?? 0}</p>
            </div>
            <div className="p-3 rounded-xl border border-cx-border bg-white/40">
              <FileText size={16} className="text-cx-accent2 mb-1" />
              <p className="text-2xs text-cx-fgDim">Recent uploads</p>
              <p className="font-semibold">{activity?.recent_documents?.length ?? 0}</p>
            </div>
            <div className="p-3 rounded-xl border border-cx-border bg-white/40">
              <Sparkles size={16} className="text-cx-accent mb-1" />
              <p className="text-2xs text-cx-fgDim">Agent runs</p>
              <p className="font-semibold">{activity?.recent_agent_runs?.length ?? 0}</p>
            </div>
          </div>

          {activity?.recent_workflows?.length > 0 && (
            <div className="mb-3">
              <p className="text-2xs uppercase text-cx-fgDim mb-2 flex items-center gap-1">
                <GitBranch size={12} /> Recent workflows
              </p>
              <div className="space-y-1">
                {activity.recent_workflows.slice(0, 4).map((w) => (
                  <div key={w.id} className="text-xs p-2 rounded-lg border border-cx-border/60 bg-white/30 flex justify-between">
                    <span className="truncate">{w.name}</span>
                    <span className="text-cx-fgDim shrink-0 ml-2">{w.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activity?.pending_approvals?.length > 0 && (
            <div className="mb-3">
              <p className="text-2xs uppercase text-cx-fgDim mb-2 flex items-center gap-1">
                <Shield size={12} /> Pending approvals
              </p>
              <div className="space-y-1">
                {activity.pending_approvals.slice(0, 4).map((a) => (
                  <div key={a.id} className="text-xs p-2 rounded-lg border border-cx-warn/20 bg-cx-warn/5">
                    {a.title}
                    <span className="text-cx-fgDim"> · {a.requested_by}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activity?.recent_documents?.length > 0 && (
            <div>
              <p className="text-2xs uppercase text-cx-fgDim mb-2">Recent uploads</p>
              <div className="space-y-1">
                {activity.recent_documents.slice(0, 4).map((d, i) => (
                  <div key={i} className="text-xs p-2 rounded-lg border border-cx-border/60 bg-white/30 flex justify-between gap-2">
                    <span className="truncate">{d.title}</span>
                    <span className="text-cx-fgDim shrink-0">{d.qc_status || d.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassPanel>
      </div>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">
          Meeting briefs ({briefs.length})
        </p>
        {briefs.length === 0 ? (
          <p className="text-sm text-cx-fgMuted py-4 text-center">
            No meeting briefs yet. Enter a topic above and generate your first brief.
          </p>
        ) : (
          <div className="space-y-3">
            {briefs.slice(0, 8).map((b) => (
              <BriefCard
                key={b.id}
                brief={b}
                expanded={expandedBriefId === b.id}
                onToggle={() => setExpandedBriefId(expandedBriefId === b.id ? null : b.id)}
              />
            ))}
          </div>
        )}
      </GlassPanel>

      {activity?.audit_timeline?.length > 0 && (
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Audit timeline (last 14 days)</p>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {activity.audit_timeline.map((e, i) => (
              <div key={i} className="flex gap-3 text-xs p-2 rounded-lg border border-cx-border/60 bg-white/30">
                <span className="text-cx-fgDim shrink-0 font-mono">{e.event_type}</span>
                <span className="text-cx-fg flex-1">{e.action}</span>
                <span className="text-cx-fgDim shrink-0">{e.actor}</span>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}
    </div>
  );
}
