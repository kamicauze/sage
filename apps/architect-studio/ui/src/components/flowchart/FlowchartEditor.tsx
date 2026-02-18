'use client';

import { useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  MarkerType,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { nodeTypes } from './FlowchartNodes';
import { Download, Plus, Trash2, ZoomIn, ZoomOut } from 'lucide-react';

interface FlowchartEditorProps {
  initialNodes?: Node[];
  initialEdges?: Edge[];
  onSave?: (nodes: Node[], edges: Edge[]) => void;
  editable?: boolean;
}

const defaultNodes: Node[] = [
  {
    id: '1',
    type: 'requirement',
    position: { x: 250, y: 50 },
    data: {
      label: 'Example User Story',
      description: 'As a junior dev, I want visual documentation',
      acceptanceCriteria: [
        'Can view flowchart',
        'Can add nodes',
        'Can export diagram'
      ],
      priority: 'High'
    }
  }
];

const defaultEdges: Edge[] = [];

export function FlowchartEditor({
  initialNodes = defaultNodes,
  initialEdges = defaultEdges,
  onSave,
  editable = true
}: FlowchartEditorProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeType, setSelectedNodeType] = useState<string>('requirement');

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: true,
            style: { stroke: '#3b82f6' },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#3b82f6',
            },
          },
          eds
        )
      ),
    [setEdges]
  );

  const addNode = useCallback(() => {
    const newNode: Node = {
      id: `node-${Date.now()}`,
      type: selectedNodeType,
      position: {
        x: Math.random() * 400 + 100,
        y: Math.random() * 400 + 100,
      },
      data: getDefaultDataForType(selectedNodeType),
    };
    setNodes((nds) => [...nds, newNode]);
  }, [selectedNodeType, setNodes]);

  const deleteSelected = useCallback(() => {
    setNodes((nds) => nds.filter((node) => !node.selected));
    setEdges((eds) => eds.filter((edge) => !edge.selected));
  }, [setNodes, setEdges]);

  const exportAsJSON = useCallback(() => {
    const data = {
      nodes,
      edges,
      timestamp: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flowchart-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [nodes, edges]);

  const exportAsPNG = useCallback(() => {
    // This would require html-to-image or similar library
    alert('PNG export would be implemented with html-to-image library');
  }, []);

  const handleSave = useCallback(() => {
    if (onSave) {
      onSave(nodes, edges);
    }
  }, [nodes, edges, onSave]);

  return (
    <div className="h-[600px] border border-architect-border rounded-lg overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        className="bg-architect-dark"
        defaultEdgeOptions={{
          animated: true,
          style: { stroke: '#3b82f6', strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#3b82f6',
          },
        }}
      >
        <Background color="#2a2a2a" gap={16} />
        <Controls className="!bg-architect-gray !border-architect-border" />
        <MiniMap
          className="!bg-architect-gray !border-architect-border"
          nodeColor={(node) => {
            switch (node.type) {
              case 'requirement':
                return '#ef4444';
              case 'component':
                return '#3b82f6';
              case 'api':
                return '#10b981';
              case 'database':
                return '#a855f7';
              case 'decision':
                return '#f59e0b';
              case 'process':
                return '#06b6d4';
              default:
                return '#6b7280';
            }
          }}
        />

        {editable && (
          <Panel position="top-left" className="flex flex-col gap-2 bg-architect-gray/90 backdrop-blur p-3 rounded-lg border border-architect-border">
            <div className="text-xs font-semibold text-gray-400 mb-1">Add Node:</div>
            <div className="flex flex-wrap gap-2">
              {[
                { type: 'requirement', icon: '📋', label: 'Story' },
                { type: 'component', icon: '⚛️', label: 'Component' },
                { type: 'api', icon: '🔌', label: 'API' },
                { type: 'database', icon: '🗄️', label: 'DB' },
                { type: 'decision', icon: '🔀', label: 'Decision' },
                { type: 'process', icon: '⚙️', label: 'Process' },
              ].map((nodeType) => (
                <button
                  key={nodeType.type}
                  onClick={() => {
                    setSelectedNodeType(nodeType.type);
                    addNode();
                  }}
                  className={`flex items-center gap-1 px-2 py-1 text-xs rounded transition-all ${
                    selectedNodeType === nodeType.type
                      ? 'bg-architect-accent text-white'
                      : 'bg-white/5 hover:bg-white/10'
                  }`}
                  title={`Add ${nodeType.label}`}
                >
                  <span>{nodeType.icon}</span>
                  <span className="hidden sm:inline">{nodeType.label}</span>
                </button>
              ))}
            </div>
          </Panel>
        )}

        <Panel position="top-right" className="flex gap-2">
          {editable && (
            <>
              <button
                onClick={deleteSelected}
                className="p-2 bg-red-500/20 hover:bg-red-500/30 rounded border border-red-500/30 transition-all"
                title="Delete Selected"
              >
                <Trash2 className="w-4 h-4 text-red-400" />
              </button>
              {onSave && (
                <button
                  onClick={handleSave}
                  className="px-3 py-2 bg-architect-accent hover:bg-architect-accent/80 rounded text-xs font-medium transition-all"
                >
                  Save
                </button>
              )}
            </>
          )}
          <button
            onClick={exportAsJSON}
            className="p-2 bg-white/5 hover:bg-white/10 rounded border border-architect-border transition-all"
            title="Export as JSON"
          >
            <Download className="w-4 h-4" />
          </button>
        </Panel>

        <Panel position="bottom-right" className="bg-architect-gray/90 backdrop-blur px-3 py-2 rounded border border-architect-border">
          <div className="text-xs text-gray-400">
            {nodes.length} node{nodes.length !== 1 ? 's' : ''} • {edges.length} connection{edges.length !== 1 ? 's' : ''}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}

function getDefaultDataForType(type: string): Record<string, any> {
  switch (type) {
    case 'requirement':
      return {
        label: 'New Requirement',
        description: 'Describe what needs to be built',
        acceptanceCriteria: ['Criteria 1', 'Criteria 2'],
        priority: 'Medium',
      };
    case 'component':
      return {
        name: 'NewComponent',
        props: ['prop1: string'],
        state: ['value: string'],
        hooks: ['useState'],
      };
    case 'api':
      return {
        method: 'GET',
        endpoint: '/api/resource',
        auth: false,
        description: 'API endpoint description',
      };
    case 'database':
      return {
        name: 'new_table',
        fields: ['id: integer', 'name: string'],
        relationships: [],
      };
    case 'decision':
      return {
        label: 'Decision Point',
        condition: 'if condition',
      };
    case 'process':
      return {
        label: 'Process Step',
        description: 'What happens in this step',
        steps: ['Step 1', 'Step 2'],
      };
    default:
      return { label: 'New Node' };
  }
}
