'use client';

import { Handle, Position } from '@xyflow/react';
import { FileCode, Database, Plug, FileText, GitBranch, CheckCircle2 } from 'lucide-react';

interface NodeData {
  label?: string;
  description?: string;
  acceptanceCriteria?: string[];
  priority?: string;
  [key: string]: any;
}

interface NodeProps {
  data: NodeData;
  id: string;
  selected?: boolean;
}

export function RequirementNode({ data, selected }: NodeProps) {
  const priorityColors = {
    Critical: 'border-red-500 bg-red-500/10',
    High: 'border-orange-500 bg-orange-500/10',
    Medium: 'border-yellow-500 bg-yellow-500/10',
    Low: 'border-blue-500 bg-blue-500/10'
  };

  const borderClass = data.priority
    ? priorityColors[data.priority as keyof typeof priorityColors]
    : 'border-white/10 bg-white/5';

  return (
    <div className={`card min-w-[280px] max-w-[350px] ${borderClass} ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-architect-accent" />

      <div className="flex items-start gap-3">
        <div className="text-3xl flex-shrink-0">📋</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-sm">{data.label || 'Requirement'}</h3>
            {data.priority && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                data.priority === 'Critical' ? 'bg-red-500/20 text-red-300' :
                data.priority === 'High' ? 'bg-orange-500/20 text-orange-300' :
                data.priority === 'Medium' ? 'bg-yellow-500/20 text-yellow-300' :
                'bg-blue-500/20 text-blue-300'
              }`}>
                {data.priority}
              </span>
            )}
          </div>

          {data.description && (
            <p className="text-xs text-gray-400 mb-3">{data.description}</p>
          )}

          {data.acceptanceCriteria && data.acceptanceCriteria.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-architect-accent">
                Acceptance Criteria:
              </p>
              {data.acceptanceCriteria.slice(0, 3).map((criteria, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <CheckCircle2 className="w-3 h-3 text-green-400 flex-shrink-0 mt-0.5" />
                  <span className="text-gray-300">{criteria}</span>
                </div>
              ))}
              {data.acceptanceCriteria.length > 3 && (
                <p className="text-xs text-gray-500">
                  +{data.acceptanceCriteria.length - 3} more...
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-architect-accent" />
    </div>
  );
}

export function ComponentNode({ data, selected }: NodeProps) {
  return (
    <div className={`card min-w-[280px] max-w-[350px] border-blue-500/30 bg-blue-500/5 ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-blue-400" />

      <div className="flex items-start gap-3">
        <div className="text-3xl flex-shrink-0">⚛️</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <FileCode className="w-4 h-4 text-blue-400" />
            <h3 className="font-semibold text-sm">{data.name || 'Component'}</h3>
          </div>

          {data.props && data.props.length > 0 && (
            <div className="mb-2">
              <p className="text-xs font-semibold text-blue-400 mb-1">Props:</p>
              <div className="space-y-0.5">
                {data.props.slice(0, 3).map((prop: string, i: number) => (
                  <code key={i} className="text-xs block text-gray-300">
                    {prop}
                  </code>
                ))}
                {data.props.length > 3 && (
                  <p className="text-xs text-gray-500">+{data.props.length - 3} more...</p>
                )}
              </div>
            </div>
          )}

          {data.state && data.state.length > 0 && (
            <div className="mb-2">
              <p className="text-xs font-semibold text-blue-400 mb-1">State:</p>
              <div className="space-y-0.5">
                {data.state.slice(0, 2).map((s: string, i: number) => (
                  <code key={i} className="text-xs block text-gray-300">
                    {s}
                  </code>
                ))}
              </div>
            </div>
          )}

          {data.hooks && data.hooks.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-blue-400 mb-1">Hooks:</p>
              <div className="flex flex-wrap gap-1">
                {data.hooks.slice(0, 4).map((hook: string, i: number) => (
                  <span key={i} className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
                    {hook}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-blue-400" />
    </div>
  );
}

export function APIEndpointNode({ data, selected }: NodeProps) {
  const methodColors = {
    GET: 'bg-green-500/20 text-green-300',
    POST: 'bg-blue-500/20 text-blue-300',
    PUT: 'bg-yellow-500/20 text-yellow-300',
    DELETE: 'bg-red-500/20 text-red-300',
    PATCH: 'bg-purple-500/20 text-purple-300'
  };

  return (
    <div className={`card min-w-[280px] max-w-[350px] border-green-500/30 bg-green-500/5 ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-green-400" />

      <div className="flex items-start gap-3">
        <div className="text-3xl flex-shrink-0">🔌</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <Plug className="w-4 h-4 text-green-400" />
            <h3 className="font-semibold text-sm">API Endpoint</h3>
          </div>

          <div className="flex items-center gap-2 mb-2">
            <span className={`text-xs font-bold px-2 py-1 rounded ${
              methodColors[data.method as keyof typeof methodColors] || 'bg-gray-500/20 text-gray-300'
            }`}>
              {data.method || 'GET'}
            </span>
            <code className="text-xs text-gray-300 break-all">
              {data.endpoint || '/api/...'}
            </code>
          </div>

          {data.auth && (
            <div className="flex items-center gap-2 text-xs text-yellow-400">
              <span>🔒</span>
              <span>Authentication Required</span>
            </div>
          )}

          {data.description && (
            <p className="text-xs text-gray-400 mt-2">{data.description}</p>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-green-400" />
    </div>
  );
}

export function DatabaseNode({ data, selected }: NodeProps) {
  return (
    <div className={`card min-w-[280px] max-w-[350px] border-purple-500/30 bg-purple-500/5 ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-purple-400" />

      <div className="flex items-start gap-3">
        <div className="text-3xl flex-shrink-0">🗄️</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <Database className="w-4 h-4 text-purple-400" />
            <h3 className="font-semibold text-sm">{data.name || 'Database Model'}</h3>
          </div>

          {data.fields && data.fields.length > 0 && (
            <div className="mb-2">
              <p className="text-xs font-semibold text-purple-400 mb-1">Fields:</p>
              <div className="space-y-0.5">
                {data.fields.slice(0, 5).map((field: string, i: number) => (
                  <code key={i} className="text-xs block text-gray-300">
                    {field}
                  </code>
                ))}
                {data.fields.length > 5 && (
                  <p className="text-xs text-gray-500">+{data.fields.length - 5} more...</p>
                )}
              </div>
            </div>
          )}

          {data.relationships && data.relationships.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-purple-400 mb-1">Relationships:</p>
              <div className="space-y-0.5">
                {data.relationships.slice(0, 3).map((rel: string, i: number) => (
                  <div key={i} className="flex items-center gap-1 text-xs text-gray-300">
                    <GitBranch className="w-3 h-3" />
                    <span>{rel}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-purple-400" />
    </div>
  );
}

export function DecisionNode({ data, selected }: NodeProps) {
  return (
    <div className={`card min-w-[200px] max-w-[250px] border-yellow-500/30 bg-yellow-500/5 ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-yellow-400" />

      <div className="text-center">
        <div className="text-2xl mb-2">🔀</div>
        <h3 className="font-semibold text-sm">{data.label || 'Decision'}</h3>
        {data.condition && (
          <code className="text-xs text-yellow-300 block mt-2">
            {data.condition}
          </code>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        className="w-3 h-3 !bg-green-400"
        style={{ left: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        className="w-3 h-3 !bg-red-400"
        style={{ left: '70%' }}
      />
    </div>
  );
}

export function ProcessNode({ data, selected }: NodeProps) {
  return (
    <div className={`card min-w-[200px] max-w-[300px] border-cyan-500/30 bg-cyan-500/5 ${selected ? 'ring-2 ring-architect-accent' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-cyan-400" />

      <div className="flex items-start gap-3">
        <div className="text-2xl flex-shrink-0">⚙️</div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm mb-1">{data.label || 'Process'}</h3>
          {data.description && (
            <p className="text-xs text-gray-400">{data.description}</p>
          )}
          {data.steps && data.steps.length > 0 && (
            <ol className="mt-2 space-y-1 text-xs text-gray-300">
              {data.steps.slice(0, 3).map((step: string, i: number) => (
                <li key={i}>{i + 1}. {step}</li>
              ))}
            </ol>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-cyan-400" />
    </div>
  );
}

export const nodeTypes = {
  requirement: RequirementNode,
  component: ComponentNode,
  api: APIEndpointNode,
  database: DatabaseNode,
  decision: DecisionNode,
  process: ProcessNode,
};
