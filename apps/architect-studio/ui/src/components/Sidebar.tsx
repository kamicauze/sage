'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Hammer, Search, BarChart3, Settings, Brain, Activity } from 'lucide-react';
import { ProjectSelector } from './ProjectSelector';
import { useProject } from '@/contexts/ProjectContext';

const brainNavigation = [
  { name: 'Brain Monitor', href: '/brain', icon: Brain },
  { name: 'Live Activity', href: '/brain/live', icon: Activity },
  { name: 'Settings', href: '/brain/settings', icon: Settings },
];

const architectNavigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Build', href: '/build', icon: Hammer },
  { name: 'Memory', href: '/memory', icon: Search },
  { name: 'Stats', href: '/stats', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { currentProject } = useProject();
  const isBrainPath = pathname.startsWith('/brain');

  return (
    <div className="hidden md:flex w-64 p-4 flex-col">
      <div className="panel p-4 mb-6">
        <h1 className="text-2xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-white via-white to-sky-200">
          {isBrainPath ? '🧠 Sage Brain' : '🏗️ Architect'}
        </h1>
        <p className="text-sm text-gray-300/80 mt-1">
          {isBrainPath ? 'Runtime Monitor' : 'Repo-Agnostic Builder'}
        </p>
      </div>

      {/* Project Selector - only show for Architect */}
      {!isBrainPath && (
        <div className="mb-6">
          <ProjectSelector />
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="mb-4 flex gap-2">
        <Link
          href="/"
          className={`flex-1 px-3 py-2 rounded-full text-center text-sm font-medium transition-colors ${!isBrainPath
              ? 'bg-white/15 text-white'
              : 'text-gray-300/80 hover:bg-white/10 hover:text-white'
            }`}
        >
          Architect
        </Link>
        <Link
          href="/brain"
          className={`flex-1 px-3 py-2 rounded-full text-center text-sm font-medium transition-colors ${isBrainPath
              ? 'bg-white/15 text-white'
              : 'text-gray-300/80 hover:bg-white/10 hover:text-white'
            }`}
        >
          Brain
        </Link>
      </div>

      <nav className="space-y-2 flex-1">
        {(isBrainPath ? brainNavigation : architectNavigation).map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`
                flex items-center gap-3 px-4 py-3 rounded-xl border transition-all
                ${isActive
                  ? 'bg-white/15 border-white/20 text-white shadow-lg shadow-sky-500/10'
                  : 'border-transparent text-gray-300/80 hover:bg-white/10 hover:text-white'
                }
              `}
            >
              <Icon size={20} />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-4">
        <div className="panel p-3">
          <div className="text-xs text-gray-300/80 mb-1">API Status</div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium">Connected</span>
          </div>
        </div>
      </div>
    </div>
  );
}
