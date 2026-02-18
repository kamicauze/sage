'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { architectAPI, UsageStats } from '@/lib/api';
import { DollarSign, TrendingUp, Activity } from 'lucide-react';

const DailySpendingChart = dynamic(
  () => import('@/components/charts/DailySpendingChart').then((m) => m.DailySpendingChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] flex items-center justify-center text-gray-400">
        Loading chart...
      </div>
    ),
  }
);

export default function StatsPage() {
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [history, setHistory] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usageData, historyData] = await Promise.all([
        architectAPI.getUsageStats(),
        architectAPI.getUsageHistory(100),
      ]);
      setUsage(usageData);
      setHistory(historyData);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400">Loading statistics...</div>
      </div>
    );
  }

  // Prepare chart data
  const chartData = history?.daily_breakdown
    ? Object.entries(history.daily_breakdown).map(([date, data]: [string, any]) => ({
        date,
        cost: data.total_cost,
        calls: data.call_count,
      }))
    : [];

  // Group calls by provider
  const byProvider: Record<string, number> = {};
  const byModel: Record<string, number> = {};

  usage?.recent_calls.forEach((call) => {
    byProvider[call.provider] = (byProvider[call.provider] || 0) + call.cost;
    byModel[call.model] = (byModel[call.model] || 0) + call.cost;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Usage Statistics</h1>
        <p className="text-gray-400">
          Detailed analytics on your AI usage and spending
        </p>
      </div>

      {/* Budget Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-architect-accent/10 rounded-lg">
              <DollarSign className="text-architect-accent" size={24} />
            </div>
            <div>
              <div className="text-sm text-gray-400">Monthly Spend</div>
              <div className="text-2xl font-bold">
                ${usage?.monthly_spend.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="w-full bg-architect-border rounded-full h-2">
            <div
              className="bg-architect-accent h-2 rounded-full transition-all"
              style={{
                width: `${Math.min(usage?.budget_percentage || 0, 100)}%`,
              }}
            />
          </div>
          <div className="mt-2 text-sm text-gray-400">
            {usage?.budget_percentage.toFixed(1)}% of ${usage?.monthly_limit}
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-green-500/10 rounded-lg">
              <Activity className="text-green-400" size={24} />
            </div>
            <div>
              <div className="text-sm text-gray-400">Daily Spend</div>
              <div className="text-2xl font-bold">
                ${usage?.daily_spend.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="text-sm text-gray-400">
            ${usage?.daily_limit} daily limit
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-blue-500/10 rounded-lg">
              <TrendingUp className="text-blue-400" size={24} />
            </div>
            <div>
              <div className="text-sm text-gray-400">Total Calls</div>
              <div className="text-2xl font-bold">
                {usage?.recent_calls.length || 0}
              </div>
            </div>
          </div>
          <div className="text-sm text-gray-400">Recent activity tracked</div>
        </div>
      </div>

      {/* Spending Over Time */}
      {chartData.length > 0 && (
        <div className="card mb-8">
          <h2 className="text-xl font-bold mb-4">Daily Spending</h2>
          <DailySpendingChart data={chartData} />
        </div>
      )}

      {/* Provider Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h2 className="text-xl font-bold mb-4">By Provider</h2>
          <div className="space-y-3">
            {Object.entries(byProvider).map(([provider, cost]) => (
              <div
                key={provider}
                className="flex items-center justify-between p-3 bg-architect-dark rounded-lg"
              >
                <span className="font-medium capitalize">{provider}</span>
                <span className="text-gray-400">${cost.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="text-xl font-bold mb-4">By Model</h2>
          <div className="space-y-3">
            {Object.entries(byModel).map(([model, cost]) => (
              <div
                key={model}
                className="flex items-center justify-between p-3 bg-architect-dark rounded-lg"
              >
                <span className="font-medium font-mono text-sm">{model}</span>
                <span className="text-gray-400">${cost.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Calls Detail */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">Recent API Calls</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-400 border-b border-architect-border">
                <th className="pb-3">Timestamp</th>
                <th className="pb-3">Provider</th>
                <th className="pb-3">Model</th>
                <th className="pb-3">Input</th>
                <th className="pb-3">Output</th>
                <th className="pb-3 text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              {usage?.recent_calls
                .slice()
                .reverse()
                .map((call, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-architect-border last:border-0"
                  >
                    <td className="py-3 text-sm text-gray-400">
                      {new Date(call.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 text-sm capitalize">{call.provider}</td>
                    <td className="py-3 text-sm font-mono">{call.model}</td>
                    <td className="py-3 text-sm text-gray-400">
                      {call.input_tokens.toLocaleString()}
                    </td>
                    <td className="py-3 text-sm text-gray-400">
                      {call.output_tokens.toLocaleString()}
                    </td>
                    <td
                      className={`py-3 text-sm text-right ${
                        call.cost === 0 ? 'text-green-400' : 'text-yellow-400'
                      }`}
                    >
                      ${call.cost.toFixed(4)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
