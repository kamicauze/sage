'use client';

import { Settings as SettingsIcon, Server, Key, Bell } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Settings</h1>
        <p className="text-gray-400">
          Configure your Architect system preferences
        </p>
      </div>

      <div className="space-y-6">
        {/* API Configuration */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <Server className="text-architect-accent" size={24} />
            <h2 className="text-xl font-bold">API Configuration</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                API Base URL
              </label>
              <input
                type="text"
                defaultValue="http://localhost:8000"
                className="input w-full"
                disabled
              />
              <p className="text-xs text-gray-400 mt-1">
                Backend API endpoint (configured in environment)
              </p>
            </div>
          </div>
        </div>

        {/* Budget Settings */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <SettingsIcon className="text-architect-accent" size={24} />
            <h2 className="text-xl font-bold">Budget Limits</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Monthly Budget Limit ($)
              </label>
              <input
                type="number"
                defaultValue={120}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Daily Burst Limit ($)
              </label>
              <input type="number" defaultValue={5} className="input w-full" />
            </div>
            <button className="btn-primary">Save Budget Settings</button>
          </div>
        </div>

        {/* Routing Preferences */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <Key className="text-architect-accent" size={24} />
            <h2 className="text-xl font-bold">Routing Preferences</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Hybrid Score Threshold
              </label>
              <input type="number" defaultValue={4} className="input w-full" />
              <p className="text-xs text-gray-400 mt-1">
                Score at which to use HYBRID routing (0-15)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Cloud Score Threshold
              </label>
              <input type="number" defaultValue={8} className="input w-full" />
              <p className="text-xs text-gray-400 mt-1">
                Score at which to use CLOUD routing (0-15)
              </p>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <Bell className="text-architect-accent" size={24} />
            <h2 className="text-xl font-bold">Notifications</h2>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-3">
              <input type="checkbox" className="w-4 h-4" defaultChecked />
              <span>Budget warnings at 75%</span>
            </label>
            <label className="flex items-center gap-3">
              <input type="checkbox" className="w-4 h-4" defaultChecked />
              <span>Build completion notifications</span>
            </label>
            <label className="flex items-center gap-3">
              <input type="checkbox" className="w-4 h-4" />
              <span>Daily usage reports</span>
            </label>
          </div>
        </div>

        {/* Coming Soon */}
        <div className="card border-2 border-dashed border-architect-border bg-architect-dark/50">
          <div className="text-center py-8 text-gray-400">
            <p className="text-lg font-medium mb-2">
              More settings coming soon...
            </p>
            <p className="text-sm">
              Model preferences, webhook integrations, and more
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
