import { useEffect, useState } from 'react';
import {
  FileText, Share2, Bot, Workflow, Clock, TrendingUp, AlertTriangle, Database,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import KpiTile from '../components/ui/KpiTile';
import GlassPanel from '../components/ui/GlassPanel';
import { getDashboardStats, getRiskAlerts } from '../api/client';

const CHART_COLORS = ['#0891b2', '#7c6bc4', '#059669', '#d97706', '#6366f1', '#ec4899', '#14b8a6'];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    getDashboardStats().then((r) => setStats(r.data)).catch(console.error);
    getRiskAlerts().then((r) => setAlerts(r.data.slice(0, 5))).catch(console.error);
  }, []);

  if (!stats) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="h-1 w-48 rounded-full bg-cx-border overflow-hidden">
          <div className="h-full w-1/2 bg-gradient-to-r from-cx-accent to-cx-accent2 animate-pulse rounded-full" />
        </div>
      </div>
    );
  }

  const stageData = Object.entries(stats.agent_usage_by_stage || {}).map(([name, value]) => ({
    name: name.replace('Early Development & CMC', 'CMC').replace('Cross-Functional', 'Cross-Fn'),
    value,
  }));

  const pieData = stageData.filter((d) => d.value > 0);

  return (
    <div className="p-6 space-y-6 max-w-[1600px]">
      <GlassPanel hero className="p-6">
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim">SciFabric AgentOS</p>
        <h1 className="font-display text-2xl font-semibold text-cx-fg mt-1">
          Drug Discovery Command Center
        </h1>
        <p className="mt-2 text-sm text-cx-fgMuted max-w-3xl leading-relaxed">
          SciFabric AgentOS is an AI-native Scientific Data Fabric and Agent Operating System for Pharma R&D,
          enabling scientists to connect evidence, generate hypotheses, design experiments, analyze results,
          and produce traceable scientific outputs across the research value chain.
        </p>
        <div className="mt-4 p-4 rounded-xl bg-cx-accent/5 border border-cx-accent/20">
          <p className="text-sm font-medium text-cx-fg">
            AI Assistance empowers scientists to reclaim an extra day each week for high-value research,
            driving faster innovation and enhanced productivity.
          </p>
        </div>
      </GlassPanel>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile label="Documents Ingested" value={stats.total_documents} icon={FileText} trend="+12 this week" trendUp />
        <KpiTile label="Entities Extracted" value={stats.total_entities} icon={Database} accent="accent2" />
        <KpiTile label="Graph Nodes" value={stats.graph_nodes} icon={Share2} suffix={` / ${stats.graph_relationships} rels`} />
        <KpiTile label="Active Agents" value={stats.active_agents} icon={Bot} />
        <KpiTile label="Workflows Completed" value={stats.completed_workflows} icon={Workflow} />
        <KpiTile label="Avg Time Saved" value={stats.avg_time_saved_hours} suffix="hrs/wk" icon={Clock} trendUp trend="+2.1 hrs" />
        <KpiTile label="Productivity Gain" value={stats.productivity_gain_pct} suffix="%" icon={TrendingUp} accent="success" trendUp />
        <KpiTile label="Risk Alerts" value={stats.open_risk_alerts} icon={AlertTriangle} accent="accent2" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Agent Usage by Value Chain</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stageData}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(100,116,139,0.15)', borderRadius: 12, fontSize: 12 }} />
              <Bar dataKey="value" fill="#0891b2" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassPanel>

        <GlassPanel>
          <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Agent Distribution</p>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2}>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(100,116,139,0.15)', borderRadius: 12, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </GlassPanel>
      </div>

      <GlassPanel>
        <p className="text-2xs uppercase tracking-[0.2em] text-cx-fgDim mb-4">Recent Risk Alerts</p>
        <div className="space-y-2">
          {alerts.map((a) => (
            <div key={a.id} className="flex items-center justify-between p-3 rounded-xl border border-cx-border bg-white/40">
              <div>
                <p className="text-sm font-medium text-cx-fg">{a.title}</p>
                <p className="text-xs text-cx-fgDim mt-0.5">{a.category} · {a.source}</p>
              </div>
              <span className={`text-2xs uppercase px-2 py-0.5 rounded-md border ${
                a.severity === 'high' ? 'text-cx-danger border-cx-danger/25 bg-cx-danger/5' :
                a.severity === 'medium' ? 'text-cx-warn border-cx-warn/25 bg-cx-warn/5' :
                'text-cx-fgDim border-cx-border'
              }`}>{a.severity}</span>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
