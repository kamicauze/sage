'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { architectAPI, Project } from '@/lib/api';

interface ProjectContextType {
  currentProject: Project | null;
  projects: Project[];
  loading: boolean;
  selectProject: (projectId: string) => void;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const data = await architectAPI.listProjects();
      setProjects(data.projects);

      // Auto-select first project if none selected
      if (!currentProject && data.projects.length > 0) {
        const savedProjectId = localStorage.getItem('selectedProjectId');
        const projectToSelect = savedProjectId
          ? data.projects.find(p => p.id === savedProjectId) || data.projects[0]
          : data.projects[0];

        setCurrentProject(projectToSelect);
        localStorage.setItem('selectedProjectId', projectToSelect.id);
      }
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const selectProject = (projectId: string) => {
    const project = projects.find(p => p.id === projectId);
    if (project) {
      setCurrentProject(project);
      localStorage.setItem('selectedProjectId', projectId);
    }
  };

  const refreshProjects = async () => {
    await loadProjects();
  };

  return (
    <ProjectContext.Provider
      value={{
        currentProject,
        projects,
        loading,
        selectProject,
        refreshProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
