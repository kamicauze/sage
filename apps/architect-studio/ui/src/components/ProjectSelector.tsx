'use client';

import { useProject } from '@/contexts/ProjectContext';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export function ProjectSelector() {
  const { currentProject, projects, loading, selectProject } = useProject();
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();

  if (loading) {
    return (
      <div className="px-4 py-3 bg-architect-border rounded-lg animate-pulse">
        <div className="h-4 bg-architect-border rounded w-32"></div>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 bg-architect-gray border border-architect-border rounded-lg hover:bg-architect-border transition-colors flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${
              currentProject?.memory_enabled ? 'bg-green-500' : 'bg-gray-500'
            }`}
          />
          <div>
            <div className="font-medium">{currentProject?.name || 'No Project'}</div>
            <div className="text-xs text-gray-400">
              {currentProject?.stack.primary || 'N/A'}
            </div>
          </div>
        </div>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-architect-gray border border-architect-border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
          {/* Create New Project Button */}
          <button
            onClick={() => {
              router.push('/new-project');
              setIsOpen(false);
            }}
            className="w-full text-left px-4 py-3 bg-architect-accent/10 hover:bg-architect-accent/20 transition-colors border-b border-architect-border flex items-center gap-3"
          >
            <Plus size={18} className="text-architect-accent" />
            <div>
              <div className="font-medium text-architect-accent">Create New Project</div>
              <div className="text-xs text-gray-400">Add a new codebase to Architect</div>
            </div>
          </button>

          {/* Project List */}
          {loading ? (
            <div className="p-4 text-gray-400 text-center">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="p-4 text-gray-400 text-sm text-center">
              No projects found. Create your first project!
            </div>
          ) : (
            projects.map((project) => (
              <button
                key={project.id}
                onClick={() => {
                  selectProject(project.id);
                  setIsOpen(false);
                }}
                className={`
                  w-full text-left px-4 py-3 hover:bg-architect-border transition-colors
                  ${currentProject?.id === project.id
                    ? 'bg-architect-border'
                    : ''
                  }
                `}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium">{project.name}</span>
                  <span className="badge badge-local text-xs">
                    {project.stack.primary}
                  </span>
                </div>
                <div className="text-sm text-gray-400">{project.description}</div>
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                  <span>{project.zone_count} zones</span>
                  {project.stack.tags.map((tag) => (
                    <span key={tag} className="badge badge-local text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            )))}
        </div>
      )}
    </div>
  );
}
