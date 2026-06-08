import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/shell/AppShell';
import { UserProvider } from './context/UserContext';
import { ProjectProvider } from './context/ProjectContext';
import Dashboard from './pages/Dashboard';
import ValueChain from './pages/ValueChain';
import DataFabric from './pages/DataFabric';
import Documents from './pages/Documents';
import KnowledgeGraph from './pages/KnowledgeGraph';
import AgentMarketplace from './pages/AgentMarketplace';
import AgentWorkspace from './pages/AgentWorkspace';
import WorkflowBuilder from './pages/WorkflowBuilder';
import SLMManagement from './pages/SLMManagement';
import Governance from './pages/Governance';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import Collaboration from './pages/Collaboration';
import Login from './pages/Login';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('scinova_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <UserProvider>
                <ProjectProvider>
                  <AppShell />
                </ProjectProvider>
              </UserProvider>
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="value-chain" element={<ValueChain />} />
          <Route path="data-fabric" element={<DataFabric />} />
          <Route path="documents" element={<Documents />} />
          <Route path="knowledge-graph" element={<KnowledgeGraph />} />
          <Route path="agents" element={<AgentMarketplace />} />
          <Route path="agents/workspace" element={<AgentWorkspace />} />
          <Route path="agents/run/:agentId" element={<AgentWorkspace />} />
          <Route path="workflows" element={<WorkflowBuilder />} />
          <Route path="slm" element={<SLMManagement />} />
          <Route path="governance" element={<Governance />} />
          <Route path="collaboration" element={<Collaboration />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="settings/users" element={<Settings />} />
          <Route path="settings/tool-fabric" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
