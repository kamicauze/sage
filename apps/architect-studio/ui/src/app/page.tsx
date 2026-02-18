'use client';

import { useEffect, useState } from 'react';
import { architectAPI, UsageStats, MemoryStats } from '@/lib/api';
import { Activity, Database, DollarSign, Zap } from 'lucide-react';
import Link from 'next/link';

export default function Dashboard() {
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [memory, setMemory] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usageData, memoryData] = await Promise.all([
        architectAPI.getUsageStats(),
        architectAPI.getMemoryStats(),
      ]);
      setUsage(usageData);
      setMemory(memoryData);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold mb-2">Dashboard</h1>
        <p className="text-gray-300/80">
          Monitor your AI usage, budget, and system status
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {/* Monthly Budget */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="text-gray-300/70 text-sm">Monthly Budget</div>
            <DollarSign className="text-architect-accent" size={20} />
          </div>
          <div className="text-3xl font-bold mb-2">
            ${usage?.monthly_spend.toFixed(2)}
            <span className="text-gray-300/70 text-lg">
              {' '}
              / ${usage?.monthly_limit}
            </span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2 mb-2">
            <div
              className="bg-architect-accent h-2 rounded-full transition-all"
              style={{ width: `${Math.min(usage?.budget_percentage || 0, 100)}%` }}
            />
          </div>
          <div className="text-sm text-gray-300/70">
            {usage?.budget_percentage.toFixed(1)}% used
          </div>
        </div>

        {/* Daily Spend */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="text-gray-300/70 text-sm">Daily Spend</div>
            <Activity className="text-green-400" size={20} />
          </div>
          <div className="text-3xl font-bold mb-2">
            ${usage?.daily_spend.toFixed(2)}
            <span className="text-gray-300/70 text-lg">
              {' '}
              / ${usage?.daily_limit}
            </span>
          </div>
          <div className="text-sm text-gray-300/70">
            {usage?.daily_spend && usage?.daily_limit
              ? ((usage.daily_spend / usage.daily_limit) * 100).toFixed(1)
              : 0}
            % of daily limit
          </div>
        </div>

        {/* Memory Chunks */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="text-gray-300/70 text-sm">Memory Chunks</div>
            <Database className="text-blue-400" size={20} />
          </div>
          <div className="text-3xl font-bold mb-2">
            {memory?.total_chunks.toLocaleString()}
          </div>
          <div className="text-sm text-gray-300/70">
            Across {Object.keys(memory?.zones || {}).length} cognitive zones
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="text-gray-300/70 text-sm">Recent Calls</div>
            <Zap className="text-yellow-400" size={20} />
          </div>
          <div className="text-3xl font-bold mb-2">
            {usage?.recent_calls.length || 0}
          </div>
          <div className="text-sm text-gray-300/70">
            Last {usage?.recent_calls.slice(-3).length || 0} calls tracked
          </div>
        </div>
      </div>

      {/* Cognitive Zones */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Cognitive Zones</h2>
          <div className="space-y-3">
            {memory &&
              Object.entries(memory.zones)
                .sort((a, b) => b[1] - a[1])
                .map(([zone, count]) => (
                  <div key={zone} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-3 h-3 rounded-full ${zone === 'The Truth'
                            ? 'bg-red-500'
                            : zone === 'The Soul'
                              ? 'bg-purple-500'
                              : zone === 'The Hands'
                                ? 'bg-blue-500'
                                : zone === 'The Body'
                                  ? 'bg-green-500'
                                  : 'bg-gray-500'
                          }`}
                      />
                      <span className="font-medium">{zone}</span>
                    </div>
                    <span className="text-gray-400">{count} chunks</span>
                  </div>
                ))}
          </div>
          <Link
            href="/memory"
            className="mt-4 block text-center btn-secondary"
          >
            Browse Memory
          </Link>
        </div>

        {/* Recent API Calls */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Recent API Calls</h2>
          <div className="space-y-3">
            {usage?.recent_calls.slice(-5).reverse().map((call, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-sm border-b border-white/10 pb-3 last:border-0"
              >
                <div>
                  <div className="font-medium">{call.model}</div>
                  <div className="text-gray-300/70 text-xs">
                    {new Date(call.timestamp).toLocaleString()}
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`font-medium ${call.cost === 0 ? 'text-green-400' : 'text-yellow-400'
                      }`}
                  >
                    ${call.cost.toFixed(4)}
                  </div>
                  <div className="text-gray-300/70 text-xs">
                    {call.input_tokens}→{call.output_tokens} tokens
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/build" className="btn-primary text-center">
            + New Build Request
          </Link>
          <Link href="/memory" className="btn-secondary text-center">
            Search Memory
          </Link>
          <Link href="/stats" className="btn-secondary text-center">
            View Detailed Stats
          </Link>
        </div>
      </div>
    </div>
  );
}
