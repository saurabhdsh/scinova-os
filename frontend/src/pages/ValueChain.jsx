import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Dna, FlaskConical } from 'lucide-react';
import AgentCard from '../components/ui/AgentCard';
import GlassPanel from '../components/ui/GlassPanel';
import { getAgents } from '../api/client';

const STAGES = [
  'Target Discovery',
  'Lead Identification',
  'Lead Optimization',
  'Preclinical Studies',
  'Early Development & CMC',
];

const STUDIOS = [
  {
    title: 'Molecular Discovery',
    href: '/molecular-studio',
    kicker: 'From a target to a molecule',
    summary: 'These specialists stay with one research conversation. The scientist asks, and the right one answers from structures, known compounds, and the designs already on screen.',
    tone: 'from-cx-accent/15 to-white border-cx-accent/25',
    icon: Dna,
    iconClass: 'text-cx-accent',
    agents: [
      { name: 'Target Intelligence', line: 'Finds the protein, its structures, and the biology around it.' },
      { name: 'Known Bioactive Discovery', line: 'Retrieves known active compounds and ranks them for the target.' },
      { name: 'Neural Molecule Generation', line: 'Designs new candidates from the compounds already in the session.' },
      { name: 'Chemical Novelty', line: 'Compares a design with the known inhibitors so the scientist can see what is new.' },
      { name: 'Docking', line: 'Places a designed molecule against a chosen structure.' },
      { name: 'ADMET', line: 'Reads descriptors for the molecule the scientist is considering.' },
      { name: 'Pathway Insight', line: 'Connects the target to pathways that matter for the question.' },
      { name: 'Conversation', line: 'Keeps the reply on the question just asked, using the session record.' },
    ],
  },
  {
    title: 'My Experiments',
    href: '/lab',
    kicker: 'From an intent to a dossier',
    summary: 'One experiment stays on one screen. The scientist writes the aim, reviews a filled plan, and steps in only when a check or the dossier needs a decision.',
    tone: 'from-cx-accent2/15 to-white border-cx-accent2/25',
    icon: FlaskConical,
    iconClass: 'text-cx-accent2',
    agents: [
      { name: 'Lab Assistant', line: 'Turns the scientist’s aim into a protocol, then answers questions about the open experiment.' },
      { name: 'Experiment Planning', line: 'Writes the plan, parameters, and success criteria for approval.' },
      { name: 'Sample and Materials Readiness', line: 'Checks samples and flags a lot that is near expiry.' },
      { name: 'Instrument Readiness', line: 'Checks calibration and names an instrument that is current.' },
      { name: 'Training and Competency', line: 'Checks that the named operator is qualified for the protocol.' },
      { name: 'Compliance', line: 'Holds the run while a blocking readiness issue is still open.' },
      { name: 'Data and Results', line: 'Reads the instrument file, scores it against the plan, and drafts the dossier.' },
    ],
  },
];

const STAGE_COLORS = {
  'Target Discovery': 'from-cx-accent/15 to-cx-accent/5 border-cx-accent/25',
  'Lead Identification': 'from-cx-accent2/15 to-cx-accent2/5 border-cx-accent2/25',
  'Lead Optimization': 'from-cx-success/15 to-cx-success/5 border-cx-success/25',
  'Preclinical Studies': 'from-cx-warn/15 to-cx-warn/5 border-cx-warn/25',
  'Early Development & CMC': 'from-indigo-500/15 to-indigo-500/5 border-indigo-500/25',
};

export default function ValueChain() {
  const [agents, setAgents] = useState([]);

  useEffect(() => {
    getAgents().then((r) => setAgents(r.data)).catch(console.error);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <GlassPanel hero>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Overview</p>
        <h2 className="font-display text-xl font-semibold mt-1">Research Value Chain</h2>
        <p className="text-sm text-cx-fgMuted mt-2">Agents organized by research value chain stage across the full drug discovery pipeline.</p>
      </GlassPanel>

      <div className="overflow-x-auto pb-4">
        <div className="flex gap-4 min-w-max">
          {STAGES.map((stage) => {
            const stageAgents = agents.filter((a) => a.value_chain_stage === stage);
            const color = STAGE_COLORS[stage] || 'from-cx-deep to-white border-cx-border';
            return (
              <div key={stage} className={`w-72 shrink-0 rounded-2xl border bg-gradient-to-b ${color} p-4`}>
                <div className="mb-4">
                  <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Stage</p>
                  <h3 className="font-display font-semibold text-sm text-cx-fg mt-1">{stage}</h3>
                  <p className="text-xs text-cx-fgDim mt-1">{stageAgents.length} agents</p>
                </div>
                <div className="space-y-3">
                  {stageAgents.map((agent) => (
                    <AgentCard key={agent.id} agent={agent} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">Studios</p>
            <h3 className="font-display text-lg font-semibold mt-1">Agents built for the scientist</h3>
          </div>
          <p className="hidden max-w-sm text-right text-xs text-cx-fgMuted sm:block">
            Molecular Discovery designs the molecule. My Experiments runs it in the lab.
          </p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {STUDIOS.map((studio) => {
            const Icon = studio.icon;
            return (
              <div key={studio.title} className={`rounded-2xl border bg-gradient-to-b ${studio.tone} p-5`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className={`rounded-xl border border-white/80 bg-white/80 p-2.5 shadow-sm ${studio.iconClass}`}>
                      <Icon size={18} strokeWidth={1.75} />
                    </div>
                    <div>
                      <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">{studio.kicker}</p>
                      <h3 className="font-display text-base font-semibold text-cx-fg mt-0.5">{studio.title}</h3>
                    </div>
                  </div>
                  <Link
                    to={studio.href}
                    className="inline-flex items-center gap-1 rounded-full border border-black/10 bg-white/80 px-3 py-1.5 text-xs text-cx-fg hover:border-cx-accent/40"
                  >
                    Open
                    <ArrowUpRight size={12} />
                  </Link>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-cx-fgMuted">{studio.summary}</p>
                <ul className="mt-4 space-y-2">
                  {studio.agents.map((agent) => (
                    <li key={agent.name} className="rounded-xl border border-white/70 bg-white/75 px-3 py-2.5">
                      <p className="text-sm font-medium text-cx-fg">{agent.name}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-cx-fgMuted">{agent.line}</p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
