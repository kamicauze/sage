'use client';

import { useState, useEffect } from 'react';
import { architectAPI, MemorySearchResponse, ZonesResponse } from '@/lib/api';
import { Search, Loader2, FileText, Database } from 'lucide-react';

export default function MemoryPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MemorySearchResponse | null>(null);
  const [zones, setZones] = useState<ZonesResponse | null>(null);
  const [selectedZone, setSelectedZone] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [loadingZones, setLoadingZones] = useState(true);

  useEffect(() => {
    loadZones();
  }, []);

  const loadZones = async () => {
    try {
      setLoadingZones(true);
      const data = await architectAPI.getZones();
      setZones(data);
    } catch (error) {
      console.error('Failed to load zones:', error);
    } finally {
      setLoadingZones(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) return;

    try {
      setLoading(true);
      const data = await architectAPI.searchMemory(
        query,
        'sage_brain',
        10,
        selectedZone
      );
      setResults(data);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const getZoneColor = (zoneName: string) => {
    const colors: Record<string, string> = {
      'The Truth': 'text-red-400 bg-red-500/10 border-red-500/20',
      'The Soul': 'text-purple-400 bg-purple-500/10 border-purple-500/20',
      'The Hands': 'text-blue-400 bg-blue-500/10 border-blue-500/20',
      'The Body': 'text-green-400 bg-green-500/10 border-green-500/20',
      unknown: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
    };
    return colors[zoneName] || colors.unknown;
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Memory Search</h1>
        <p className="text-gray-400">
          Semantic search across your codebase using vector similarity
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="card mb-8">
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            Search Query
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., MQTT connection handling"
              className="input flex-1"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <Search size={20} />
              )}
              Search
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Filter by Zone (Optional)
          </label>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setSelectedZone(undefined)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                selectedZone === undefined
                  ? 'bg-architect-accent text-white'
                  : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
              }`}
            >
              All Zones
            </button>
            {zones?.zones.map((zone) => (
              <button
                key={zone.name}
                type="button"
                onClick={() => setSelectedZone(zone.name)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  selectedZone === zone.name
                    ? 'bg-architect-accent text-white'
                    : 'bg-architect-gray border border-architect-border text-gray-400 hover:text-white'
                }`}
              >
                {zone.name} ({zone.chunk_count})
              </button>
            ))}
          </div>
        </div>
      </form>

      {/* Search Results */}
      {results && (
        <div className="space-y-4 mb-8">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">
              Search Results ({results.total_results})
            </h2>
            <span className="text-sm text-gray-400">
              Query: "{results.query}"
            </span>
          </div>

          {results.results.length === 0 ? (
            <div className="card text-center py-12 text-gray-400">
              No results found. Try a different query or zone filter.
            </div>
          ) : (
            results.results.map((result, idx) => (
              <div key={idx} className="card">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-architect-accent" />
                    <span className="font-mono text-sm">{result.source}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`badge ${getZoneColor(result.zone_name)}`}>
                      {result.zone_name}
                    </span>
                    <span className="text-xs text-gray-400">
                      {(1 - result.distance).toFixed(2)}% match
                    </span>
                  </div>
                </div>

                <pre className="bg-architect-dark p-4 rounded-lg overflow-x-auto text-sm">
                  <code>{result.content}</code>
                </pre>

                <div className="mt-3 text-xs text-gray-400">
                  Role: {result.role} • Distance: {result.distance.toFixed(4)}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Zones Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Database size={20} className="text-architect-accent" />
            Cognitive Zones
          </h2>

          {loadingZones ? (
            <div className="text-center py-8 text-gray-400">
              Loading zones...
            </div>
          ) : (
            <div className="space-y-3">
              {zones?.zones.map((zone) => (
                <div
                  key={zone.name}
                  className="p-4 bg-architect-dark rounded-lg border border-architect-border"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className={`badge ${getZoneColor(zone.name)}`}>
                      {zone.name}
                    </span>
                    <span className="text-sm text-gray-400">
                      {zone.chunk_count} chunks
                    </span>
                  </div>
                  <div className="text-sm text-gray-400">
                    Role: {zone.role} • {zone.files.length} files
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="text-xl font-bold mb-4">Memory Statistics</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-architect-dark rounded-lg">
              <span className="text-gray-400">Total Chunks</span>
              <span className="text-2xl font-bold">
                {zones?.total_chunks.toLocaleString() || 0}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 bg-architect-dark rounded-lg">
              <span className="text-gray-400">Zone Count</span>
              <span className="text-2xl font-bold">
                {zones?.zone_count || 0}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 bg-architect-dark rounded-lg">
              <span className="text-gray-400">Project ID</span>
              <span className="font-mono text-sm">
                {zones?.project_id || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
