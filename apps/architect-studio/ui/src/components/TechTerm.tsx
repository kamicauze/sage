'use client';

import { useState } from 'react';
import { techGlossary } from '@/lib/templates';
import { HelpCircle } from 'lucide-react';

interface TechTermProps {
  term: string;
  children?: React.ReactNode;
  showIcon?: boolean;
}

export function TechTerm({ term, children, showIcon = false }: TechTermProps) {
  const [isHovered, setIsHovered] = useState(false);
  const definition = techGlossary[term];

  if (!definition) {
    return <span>{children || term}</span>;
  }

  return (
    <span className="relative inline-block">
      <span
        className="underline decoration-dotted decoration-architect-accent cursor-help inline-flex items-center gap-1"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {children || term}
        {showIcon && <HelpCircle className="w-3 h-3 text-architect-accent inline" />}
      </span>

      {isHovered && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 animate-in fade-in duration-200">
          <div className="card p-3 w-64 text-sm shadow-2xl">
            <div className="font-semibold text-architect-accent mb-1">{term}</div>
            <div className="text-gray-300 leading-relaxed">{definition}</div>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-2 h-2 bg-architect-gray border-b border-r border-architect-border rotate-45" />
          </div>
        </div>
      )}
    </span>
  );
}

interface GlossarySidebarProps {
  searchable?: boolean;
}

export function GlossarySidebar({ searchable = true }: GlossarySidebarProps) {
  const [search, setSearch] = useState('');

  const filteredTerms = Object.entries(techGlossary).filter(
    ([term, definition]) =>
      term.toLowerCase().includes(search.toLowerCase()) ||
      definition.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="card h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <HelpCircle className="w-5 h-5 text-architect-accent" />
        <h3 className="font-semibold">Tech Glossary</h3>
      </div>

      {searchable && (
        <input
          type="text"
          placeholder="Search terms..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input mb-4"
        />
      )}

      <div className="flex-1 overflow-y-auto space-y-3">
        {filteredTerms.map(([term, definition]) => (
          <div key={term} className="border-b border-architect-border pb-3 last:border-0">
            <div className="font-semibold text-sm text-architect-accent mb-1">
              {term}
            </div>
            <div className="text-xs text-gray-400 leading-relaxed">
              {definition}
            </div>
          </div>
        ))}

        {filteredTerms.length === 0 && (
          <div className="text-center text-gray-500 text-sm py-8">
            No terms found matching &quot;{search}&quot;
          </div>
        )}
      </div>

      <div className="mt-4 text-xs text-gray-500 text-center">
        {Object.keys(techGlossary).length} terms available
      </div>
    </div>
  );
}
