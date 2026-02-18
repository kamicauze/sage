'use client';

import { useState } from 'react';
import { CheckCircle2, Circle, ChevronDown, ChevronRight } from 'lucide-react';

export interface Requirement {
  id: string;
  title: string;
  description: string;
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  acceptanceCriteria: string[];
  completed: boolean;
  estimatedEffort?: string;
  assignee?: string;
}

interface RequirementsChecklistProps {
  requirements: Requirement[];
  onUpdate: (id: string, completed: boolean) => void;
  onRequirementClick?: (req: Requirement) => void;
  editable?: boolean;
}

export function RequirementsChecklist({
  requirements,
  onUpdate,
  onRequirementClick,
  editable = true,
}: RequirementsChecklistProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const priorityConfig = {
    Critical: {
      badge: 'bg-red-500/20 text-red-300 border-red-500/30',
      border: 'border-red-500/30',
    },
    High: {
      badge: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
      border: 'border-orange-500/30',
    },
    Medium: {
      badge: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
      border: 'border-yellow-500/30',
    },
    Low: {
      badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
      border: 'border-blue-500/30',
    },
  };

  const completedCount = requirements.filter((r) => r.completed).length;
  const totalCount = requirements.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Progress Summary */}
      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold">Requirements Progress</h3>
          <span className="text-sm text-gray-400">
            {completedCount} / {totalCount} completed
          </span>
        </div>
        <div className="w-full bg-architect-border rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-architect-accent to-green-500 h-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Requirements List */}
      <div className="space-y-3">
        {requirements.map((req) => {
          const isExpanded = expandedIds.has(req.id);
          const config = priorityConfig[req.priority];

          return (
            <div
              key={req.id}
              className={`card border ${config.border} transition-all ${
                req.completed ? 'opacity-60' : ''
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Checkbox */}
                {editable && (
                  <button
                    onClick={() => onUpdate(req.id, !req.completed)}
                    className="mt-1 flex-shrink-0"
                  >
                    {req.completed ? (
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                    ) : (
                      <Circle className="w-5 h-5 text-gray-500 hover:text-gray-400 transition-colors" />
                    )}
                  </button>
                )}

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <h4
                      className={`font-medium ${
                        req.completed ? 'line-through text-gray-500' : ''
                      } ${onRequirementClick ? 'cursor-pointer hover:text-architect-accent' : ''}`}
                      onClick={() => onRequirementClick?.(req)}
                    >
                      {req.title}
                    </h4>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${config.badge}`}>
                      {req.priority}
                    </span>
                    {req.estimatedEffort && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-gray-400">
                        {req.estimatedEffort}
                      </span>
                    )}
                    {req.assignee && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-architect-accent/20 text-architect-accent">
                        {req.assignee}
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-gray-400 mb-2">{req.description}</p>

                  {/* Acceptance Criteria */}
                  {req.acceptanceCriteria.length > 0 && (
                    <div>
                      <button
                        onClick={() => toggleExpanded(req.id)}
                        className="flex items-center gap-1 text-xs text-architect-accent hover:text-architect-accent/80 transition-colors"
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                        Acceptance Criteria ({req.acceptanceCriteria.length})
                      </button>

                      {isExpanded && (
                        <ul className="mt-2 space-y-1 ml-5">
                          {req.acceptanceCriteria.map((criteria, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs">
                              <span className="text-green-400 flex-shrink-0 mt-0.5">✓</span>
                              <span className="text-gray-300">{criteria}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {requirements.length === 0 && (
          <div className="card text-center py-12">
            <div className="text-4xl mb-3">📋</div>
            <h3 className="font-semibold mb-2">No Requirements Yet</h3>
            <p className="text-sm text-gray-400">
              Add requirements to start tracking your progress
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

interface AddRequirementFormProps {
  onAdd: (req: Omit<Requirement, 'id' | 'completed'>) => void;
  onCancel: () => void;
}

export function AddRequirementForm({ onAdd, onCancel }: AddRequirementFormProps) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: 'Medium' as Requirement['priority'],
    acceptanceCriteria: '',
    estimatedEffort: '',
    assignee: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAdd({
      title: formData.title,
      description: formData.description,
      priority: formData.priority,
      acceptanceCriteria: formData.acceptanceCriteria
        .split('\n')
        .filter((c) => c.trim()),
      estimatedEffort: formData.estimatedEffort || undefined,
      assignee: formData.assignee || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="card space-y-4">
      <h3 className="font-semibold mb-4">Add Requirement</h3>

      <div>
        <label className="block text-sm font-medium mb-1">Title *</label>
        <input
          type="text"
          required
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          className="input w-full"
          placeholder="Brief title for the requirement"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Description *</label>
        <textarea
          required
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          className="input w-full h-20 resize-none"
          placeholder="Detailed description of what needs to be done"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Priority *</label>
          <select
            value={formData.priority}
            onChange={(e) =>
              setFormData({ ...formData, priority: e.target.value as Requirement['priority'] })
            }
            className="input w-full"
          >
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Estimated Effort</label>
          <select
            value={formData.estimatedEffort}
            onChange={(e) => setFormData({ ...formData, estimatedEffort: e.target.value })}
            className="input w-full"
          >
            <option value="">Not estimated</option>
            <option value="1 day">1 day</option>
            <option value="2-3 days">2-3 days</option>
            <option value="1 week">1 week</option>
            <option value="2 weeks">2 weeks</option>
            <option value="1 month">1 month</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Assignee</label>
        <input
          type="text"
          value={formData.assignee}
          onChange={(e) => setFormData({ ...formData, assignee: e.target.value })}
          className="input w-full"
          placeholder="Who will work on this?"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          Acceptance Criteria (one per line)
        </label>
        <textarea
          value={formData.acceptanceCriteria}
          onChange={(e) =>
            setFormData({ ...formData, acceptanceCriteria: e.target.value })
          }
          className="input w-full h-24 resize-none"
          placeholder="✓ User can login&#10;✓ Error message is shown for invalid credentials&#10;✓ Session persists after refresh"
        />
      </div>

      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
        <button type="submit" className="btn-primary">
          Add Requirement
        </button>
      </div>
    </form>
  );
}
