'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { architectAPI, PlanResponse, BuildResponse } from '@/lib/api';
import { useProject } from '@/contexts/ProjectContext';
import { Loader2, Send, FileText, DollarSign, CheckCircle, XCircle, Clock, Code, Layers, HelpCircle, Sparkles } from 'lucide-react';
import { TechTerm } from '@/components/TechTerm';
import { OnboardingTour, buildPageTour } from '@/components/OnboardingTour';
import type { Node, Edge } from '@xyflow/react';

const ReactMarkdown = dynamic(() => import('react-markdown'), {
  ssr: false,
  loading: () => <div className="text-gray-400">Loading markdown renderer...</div>,
});

const FlowchartEditor = dynamic(
  () => import('@/components/flowchart/FlowchartEditor').then((m) => m.FlowchartEditor),
  {
    ssr: false,
    loading: () => (
      <div className="h-[600px] rounded-lg border border-architect-border bg-architect-dark flex items-center justify-center text-gray-400">
        Loading flowchart editor...
      </div>
    ),
  }
);

const TemplateSelector = dynamic(
  () => import('@/components/TemplateSelector').then((m) => m.TemplateSelector),
  {
    ssr: false,
    loading: () => null,
  }
);

const GlossarySidebar = dynamic(
  () => import('@/components/TechTerm').then((m) => m.GlossarySidebar),
  {
    ssr: false,
    loading: () => <div className="card text-gray-400">Loading glossary...</div>,
  }
);

interface BuildHistoryItem {
  id: string;
  timestamp: number;
  query: string;
  requestType: string;
  plan?: PlanResponse;
  buildResult?: BuildResponse;
  status: 'planning' | 'planned' | 'building' | 'success' | 'failed';
}

export default function BuildPage() {
  const { currentProject } = useProject();
  const [query, setQuery] = useState('');
  const [requestType, setRequestType] = useState('feature');
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [buildResult, setBuildResult] = useState<BuildResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<BuildHistoryItem[]>([]);
  const [activeTab, setActiveTab] = useState<'form' | 'history' | 'flowchart' | 'glossary'>('form');

  // New features state
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [flowchartNodes, setFlowchartNodes] = useState<Node[]>([]);
  const [flowchartEdges, setFlowchartEdges] = useState<Edge[]>([]);
  const [planDetailLevel, setPlanDetailLevel] = useState<'simple' | 'detailed' | 'expert'>('detailed');

  // Git integration options
  const [gitOptions, setGitOptions] = useState({
    autoCommit: false,
    commitMessage: '',
    createBranch: '',
    pushToRemote: false,
  });

  // Load history from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('buildHistory');
    if (saved) {
      try {
        setHistory(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    }
  }, []);

  // Save history to localStorage
  const saveHistory = (newHistory: BuildHistoryItem[]) => {
    setHistory(newHistory);
    localStorage.setItem('buildHistory', JSON.stringify(newHistory));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      setError('Please enter a build request');
      return;
    }

    if (!currentProject) {
      setError('No project selected');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setPlan(null);
      setBuildResult(null);

      const historyItem: BuildHistoryItem = {
        id: Date.now().toString(),
        timestamp: Date.now(),
        query,
        requestType,
        status: 'planning',
      };

      // Add to history immediately so it shows "Planning..."
      saveHistory([historyItem, ...history]);

      const response = await architectAPI.generatePlan(
        query,
        requestType,
        currentProject.manifest_path
      );

      historyItem.plan = response;
      historyItem.status = 'planned';

      setPlan(response);

      // Update history with completed plan
      const updatedHistory = [historyItem, ...history];
      saveHistory(updatedHistory);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate plan');
      console.error('Build request failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!plan || !currentProject) return;

    try {
      setBuilding(true);
      setError(null);

      // Use Git-integrated endpoint if auto-commit is enabled
      const result = await architectAPI.executeBuildWithGit(
        currentProject.manifest_path,
        gitOptions.autoCommit ? {
          auto_commit: true,
          commit_message: gitOptions.commitMessage || null,
          create_branch: gitOptions.createBranch || null,
          push_to_remote: gitOptions.pushToRemote,
          files: null,  // null = all generated files
        } : null
      );

      setBuildResult(result);

      // Update history
      const updatedHistory = history.map((item) => {
        if (item.plan?.plan_path === plan.plan_path) {
          return {
            ...item,
            buildResult: result,
            status: (result.status === 'SUCCESS' ? 'success' : 'failed') as BuildHistoryItem['status'],
          };
        }
        return item;
      });
      saveHistory(updatedHistory);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to execute build');
      console.error('Build execution failed:', err);
    } finally {
      setBuilding(false);
    }
  };

  const handleNewRequest = () => {
    setQuery('');
    setPlan(null);
    setBuildResult(null);
    setError(null);
  };

  const loadHistoryItem = (item: BuildHistoryItem) => {
    setPlan(item.plan || null);
    setBuildResult(item.buildResult || null);
    setQuery(item.query);
    setRequestType(item.requestType);
    setActiveTab('form');
  };

  const handleTemplateGenerate = (documentation: string, flowchartData?: any[]) => {
    setQuery(documentation);
    setShowTemplateSelector(false);
    if (flowchartData) {
      setFlowchartNodes(flowchartData);
      setFlowchartEdges([]);
    }
  };

  const handleFlowchartSave = (nodes: Node[], edges: Edge[]) => {
    setFlowchartNodes(nodes);
    setFlowchartEdges(edges);
    // Could also convert to query text or documentation
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Build</h1>
        <p className="text-gray-400">
          {currentProject
            ? `Working on: ${currentProject.name}`
            : 'No project selected'}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button
          onClick={() => setActiveTab('form')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'form'
              ? 'bg-architect-accent text-white'
              : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
            }`}
        >
          <FileText className="w-4 h-4" />
          New Request
        </button>
        <button
          onClick={() => setActiveTab('flowchart')}
          className={`flowchart-tab px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'flowchart'
              ? 'bg-architect-accent text-white'
              : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
            }`}
        >
          <Layers className="w-4 h-4" />
          Flowchart
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'history'
              ? 'bg-architect-accent text-white'
              : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
            }`}
        >
          <Clock className="w-4 h-4" />
          History ({history.length})
        </button>
        <button
          onClick={() => setActiveTab('glossary')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${activeTab === 'glossary'
              ? 'bg-architect-accent text-white'
              : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
            }`}
        >
          <HelpCircle className="w-4 h-4" />
          Glossary
        </button>
      </div>

      {activeTab === 'history' && (
        <div className="space-y-4">
          {history.length === 0 ? (
            <div className="card text-center py-12 text-gray-400">
              No build history yet. Create your first build request!
            </div>
          ) : (
            history.map((item) => (
              <div key={item.id} className="card">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      {item.status === 'success' && (
                        <CheckCircle size={16} className="text-green-400" />
                      )}
                      {item.status === 'failed' && (
                        <XCircle size={16} className="text-red-400" />
                      )}
                      {item.status === 'planned' && (
                        <Clock size={16} className="text-yellow-400" />
                      )}
                      {item.status === 'planning' && (
                        <Loader2 size={16} className="text-blue-400 animate-spin" />
                      )}
                      <span className="badge badge-local text-xs">
                        {item.requestType}
                      </span>
                      <span className="text-xs text-gray-400">
                        {new Date(item.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="font-medium mb-2">{item.query}</p>
                    {item.plan && (
                      <div className="text-sm text-gray-400">
                        Route: {item.plan.routing_decision.route} •{' '}
                        {item.plan.routing_decision.model}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => loadHistoryItem(item)}
                    className="btn-secondary text-sm"
                  >
                    View
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'flowchart' && (
        <div className="space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold mb-1">Visual Planning</h2>
                <p className="text-sm text-gray-400">
                  Create flowcharts to visualize your architecture and requirements
                </p>
              </div>
              <button
                onClick={() => setShowTemplateSelector(true)}
                className="btn-primary flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                Use Template
              </button>
            </div>

            <FlowchartEditor
              initialNodes={flowchartNodes}
              initialEdges={flowchartEdges}
              onSave={handleFlowchartSave}
              editable={true}
            />

            <div className="mt-4 p-4 bg-architect-dark rounded-lg">
              <h3 className="font-semibold mb-2 text-sm">💡 Pro Tips:</h3>
              <ul className="text-xs text-gray-400 space-y-1">
                <li>• Click node type buttons to add different components</li>
                <li>• Drag from the blue dots to connect nodes</li>
                <li>• Click nodes to select, then delete with trash icon</li>
                <li>• Use templates above to get started quickly</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'glossary' && (
        <div className="max-w-2xl">
          <GlossarySidebar searchable={true} />
          <div className="mt-6 card">
            <h3 className="font-semibold mb-3">How to Use the Glossary</h3>
            <p className="text-sm text-gray-400 mb-3">
              This glossary contains definitions for common technical terms used in Sage and software development.
            </p>
            <p className="text-sm text-gray-400">
              Throughout the app, hover over underlined terms like{' '}
              <TechTerm term="API">API</TechTerm>,{' '}
              <TechTerm term="MQTT">MQTT</TechTerm>, or{' '}
              <TechTerm term="PWA">PWA</TechTerm> to see quick definitions!
            </p>
          </div>
        </div>
      )}

      {activeTab === 'form' && !plan && (
        <form onSubmit={handleSubmit} className="card mb-8">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium">
                What would you like to build?
              </label>
              <button
                type="button"
                onClick={() => setShowTemplateSelector(true)}
                className="template-button text-sm text-architect-accent hover:text-architect-accent/80 transition-colors flex items-center gap-1"
              >
                <Sparkles className="w-4 h-4" />
                Use Template
              </button>
            </div>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Add MQTT reconnection logic with exponential backoff&#10;&#10;Or click 'Use Template' above to get started with structured documentation!"
              className="build-query-input input w-full h-32 resize-none"
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-2">
              💡 Tip: Be specific! Mention file names, technologies, and expected behavior.
            </p>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">
              Request Type
            </label>
            <div className="request-type-selector flex gap-2 flex-wrap">
              {['feature', 'bugfix', 'refactor', 'test'].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setRequestType(type)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${requestType === type
                      ? 'bg-architect-accent text-white'
                      : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
                    }`}
                  disabled={loading}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              <TechTerm term="Feature" showIcon={false}>Feature</TechTerm>: New functionality •{' '}
              Bugfix: Fix errors •{' '}
              <TechTerm term="Refactor" showIcon={false}>Refactor</TechTerm>: Improve code •{' '}
              Test: Add tests
            </p>
          </div>

          {error && (
            <div className="mb-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="generate-plan-button btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                <span>Generating Plan...</span>
              </>
            ) : (
              <>
                <Send size={20} />
                <span>Generate Plan</span>
              </>
            )}
          </button>
        </form>
      )}

      {activeTab === 'form' && plan && (
        <div className="space-y-6">
          {/* Routing Decision */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">
              Routing Decision
              <span className="text-sm font-normal text-gray-400 ml-2">
                (Where your code will be built)
              </span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-400 mb-1">Route</div>
                <span
                  className={`badge ${plan.routing_decision.route === 'LOCAL'
                      ? 'badge-local'
                      : plan.routing_decision.route === 'HYBRID'
                        ? 'badge-hybrid'
                        : 'badge-cloud'
                    }`}
                >
                  {plan.routing_decision.route}
                </span>
                <p className="text-xs text-gray-500 mt-1">
                  {plan.routing_decision.route === 'LOCAL' && 'Built on your device'}
                  {plan.routing_decision.route === 'HYBRID' && 'Built using both local and cloud'}
                  {plan.routing_decision.route === 'CLOUD' && 'Built in the cloud'}
                </p>
              </div>
              <div>
                <div className="text-sm text-gray-400 mb-1">
                  <TechTerm term="Provider">Provider</TechTerm>
                </div>
                <div className="font-medium">{plan.routing_decision.provider}</div>
              </div>
              <div>
                <div className="text-sm text-gray-400 mb-1">Model</div>
                <div className="font-medium">{plan.routing_decision.model}</div>
                <p className="text-xs text-gray-500 mt-1">
                  The <TechTerm term="AI">AI</TechTerm> model used for generation
                </p>
              </div>
              <div>
                <div className="text-sm text-gray-400 mb-1">Est. Cost</div>
                <div className="font-medium flex items-center gap-1">
                  <DollarSign size={16} />
                  {plan.routing_decision.estimated_cost_min.toFixed(2)} -{' '}
                  {plan.routing_decision.estimated_cost_max.toFixed(2)}
                </div>
              </div>
            </div>
            <div className="mt-4 p-3 bg-architect-dark rounded-lg">
              <div className="text-sm text-gray-400 mb-1">Reason</div>
              <div className="text-sm">{plan.routing_decision.reason}</div>
            </div>
          </div>

          {/* Context Snippets */}
          {plan.context_snippets.length > 0 && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4">Retrieved Context</h2>
              <div className="space-y-2">
                {plan.context_snippets.map((snippet, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-architect-dark rounded-lg border border-architect-border"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <FileText size={16} className="text-architect-accent" />
                      <span className="font-mono text-sm">{snippet.source}</span>
                      <span className="badge badge-local text-xs">
                        {snippet.zone_name}
                      </span>
                    </div>
                    <div className="text-sm text-gray-400">
                      {snippet.content_preview}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Generated Plan */}
          <div className="card">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <h2 className="text-xl font-bold">Implementation Plan</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Detail Level:</span>
                <div className="flex gap-1">
                  {(['simple', 'detailed', 'expert'] as const).map((level) => (
                    <button
                      key={level}
                      onClick={() => setPlanDetailLevel(level)}
                      className={`px-3 py-1 text-xs rounded transition-colors ${
                        planDetailLevel === level
                          ? 'bg-architect-accent text-white'
                          : 'bg-white/5 text-gray-400 hover:text-white'
                      }`}
                    >
                      {level === 'simple' && '🌱 Simple'}
                      {level === 'detailed' && '🌿 Detailed'}
                      {level === 'expert' && '🌳 Expert'}
                    </button>
                  ))}
                </div>
                <button onClick={handleNewRequest} className="btn-secondary ml-2">
                  New Request
                </button>
              </div>
            </div>

            {planDetailLevel === 'simple' && (
              <div className="bg-architect-dark p-6 rounded-lg">
                <h3 className="font-semibold mb-3">📝 Summary</h3>
                <p className="text-gray-300 mb-4">
                  This plan will implement your request using {plan.routing_decision.model}.
                  Estimated cost: ${plan.routing_decision.estimated_cost_min.toFixed(2)} - ${plan.routing_decision.estimated_cost_max.toFixed(2)}
                </p>
                <div className="text-sm text-gray-400">
                  💡 Switch to &quot;Detailed&quot; or &quot;Expert&quot; view for more information
                </div>
              </div>
            )}

            {planDetailLevel === 'detailed' && (
              <div className="prose prose-invert max-w-none bg-architect-dark p-6 rounded-lg overflow-auto max-h-96">
                <ReactMarkdown>{plan.plan_content}</ReactMarkdown>
              </div>
            )}

            {planDetailLevel === 'expert' && (
              <div className="space-y-4">
                <div className="prose prose-invert max-w-none bg-architect-dark p-6 rounded-lg overflow-auto max-h-96">
                  <ReactMarkdown>{plan.plan_content}</ReactMarkdown>
                </div>
                <details className="bg-architect-dark p-6 rounded-lg">
                  <summary className="font-semibold cursor-pointer">
                    🔍 Technical Details
                  </summary>
                  <div className="mt-4 space-y-3 text-sm">
                    <div>
                      <div className="text-gray-400 mb-1">Plan Path:</div>
                      <code className="text-xs text-gray-300">{plan.plan_path}</code>
                    </div>
                    <div>
                      <div className="text-gray-400 mb-1">Routing Decision:</div>
                      <pre className="text-xs text-gray-300 overflow-auto">
                        {JSON.stringify(plan.routing_decision, null, 2)}
                      </pre>
                    </div>
                  </div>
                </details>
              </div>
            )}
          </div>

          {/* Build Result */}
          {buildResult && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Code size={20} />
                Build Output
              </h2>
              <div
                className={`p-4 rounded-lg mb-4 ${buildResult.status === 'SUCCESS'
                    ? 'bg-green-500/10 border border-green-500/20'
                    : 'bg-red-500/10 border border-red-500/20'
                  }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {buildResult.status === 'SUCCESS' ? (
                    <CheckCircle className="text-green-400" size={20} />
                  ) : (
                    <XCircle className="text-red-400" size={20} />
                  )}
                  <span className="font-medium">{buildResult.summary}</span>
                </div>
              </div>

              {buildResult.artifacts.length > 0 && (
                <div className="mb-4">
                  <h3 className="font-medium mb-2">Generated Artifacts:</h3>
                  <ul className="space-y-1">
                    {buildResult.artifacts.map((artifact, idx) => (
                      <li
                        key={idx}
                        className="text-sm text-gray-400 font-mono"
                      >
                        • {artifact}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {buildResult.files_built.length > 0 && (
                <div className="mb-4">
                  <h3 className="font-medium mb-2">Files Built:</h3>
                  <ul className="space-y-1">
                    {buildResult.files_built.map((file, idx) => (
                      <li
                        key={idx}
                        className="text-sm text-gray-400 font-mono"
                      >
                        • {file}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {buildResult.test_results && (
                <div className="mb-4">
                  <h3 className="font-medium mb-2">Test Results:</h3>
                  <pre className="bg-architect-dark p-4 rounded-lg text-sm overflow-auto">
                    {JSON.stringify(buildResult.test_results, null, 2)}
                  </pre>
                </div>
              )}

              {buildResult.git_result && (
                <div>
                  <h3 className="font-medium mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12" />
                    </svg>
                    Git Operations
                  </h3>
                  <div
                    className={`p-4 rounded-lg ${buildResult.git_result.success
                        ? 'bg-green-500/10 border border-green-500/20'
                        : 'bg-red-500/10 border border-red-500/20'
                      }`}
                  >
                    {buildResult.git_result.success ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-green-400">
                          <CheckCircle size={16} />
                          <span className="font-medium">Git operations completed successfully</span>
                        </div>
                        {buildResult.git_result.commit_hash && (
                          <div className="text-sm text-gray-400">
                            Commit: <span className="font-mono text-gray-300">{buildResult.git_result.commit_hash}</span>
                          </div>
                        )}
                        {buildResult.git_result.workflow && (
                          <div className="text-sm space-y-1 mt-2">
                            {buildResult.git_result.workflow.map(([operation, result], idx) => (
                              <div key={idx} className="flex items-center gap-2">
                                <CheckCircle size={12} className="text-green-400" />
                                <span className="text-gray-400">
                                  {operation === 'create_branch' && `Created branch: ${result.branch}`}
                                  {operation === 'commit' && `Committed with hash: ${result.commit_hash}`}
                                  {operation === 'push' && 'Pushed to remote'}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-red-400">
                        <XCircle size={16} />
                        <span>{buildResult.git_result.error || 'Git operation failed'}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Git Integration Options */}
          {!buildResult && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12" />
                </svg>
                Git Integration
              </h2>

              <div className="space-y-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={gitOptions.autoCommit}
                    onChange={(e) => setGitOptions({ ...gitOptions, autoCommit: e.target.checked })}
                    className="w-4 h-4 text-architect-accent bg-architect-gray border-architect-border rounded focus:ring-architect-accent"
                  />
                  <div>
                    <div className="font-medium">Auto-commit on success</div>
                    <div className="text-sm text-gray-400">Automatically commit generated files after successful build</div>
                  </div>
                </label>

                {gitOptions.autoCommit && (
                  <div className="ml-7 space-y-4 border-l-2 border-architect-border pl-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Commit Message (optional)
                      </label>
                      <textarea
                        value={gitOptions.commitMessage}
                        onChange={(e) => setGitOptions({ ...gitOptions, commitMessage: e.target.value })}
                        placeholder="Leave empty to auto-generate from plan"
                        className="input w-full h-20 resize-none text-sm"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Tip: Auto-generated messages include Co-Authored-By: Claude
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Create Branch (optional)
                      </label>
                      <input
                        type="text"
                        value={gitOptions.createBranch}
                        onChange={(e) => setGitOptions({ ...gitOptions, createBranch: e.target.value })}
                        placeholder="feature/my-feature"
                        className="input w-full text-sm font-mono"
                      />
                      <p className="text-xs text-gray-400 mt-1">
                        Creates and checks out a new branch before committing
                      </p>
                    </div>

                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={gitOptions.pushToRemote}
                        onChange={(e) => setGitOptions({ ...gitOptions, pushToRemote: e.target.checked })}
                        className="w-4 h-4 text-architect-accent bg-architect-gray border-architect-border rounded focus:ring-architect-accent"
                      />
                      <div>
                        <div className="font-medium">Push to remote</div>
                        <div className="text-sm text-gray-400">Automatically push changes to origin after commit</div>
                      </div>
                    </label>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-4">
            <button
              onClick={handleBuild}
              disabled={building || !!buildResult}
              className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {building ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  <span>Building...</span>
                </>
              ) : buildResult ? (
                <>
                  <CheckCircle size={20} />
                  <span>Built</span>
                </>
              ) : (
                <>
                  <Code size={20} />
                  <span>Approve & Build</span>
                </>
              )}
            </button>
            <button onClick={handleNewRequest} className="btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Template Selector Modal */}
      {showTemplateSelector && (
        <TemplateSelector
          onGenerate={handleTemplateGenerate}
          onClose={() => setShowTemplateSelector(false)}
        />
      )}

      {/* Onboarding Tour */}
      <OnboardingTour
        steps={buildPageTour}
        storageKey="build-page-tour-completed"
        onComplete={() => console.log('Tour completed!')}
        onSkip={() => console.log('Tour skipped')}
      />
    </div>
  );
}
