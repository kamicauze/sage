'use client';

import { useState } from 'react';
import { useBrain } from '@/contexts/BrainContext';
import { Save, RotateCcw } from 'lucide-react';

import { PERSONALITIES } from '@/lib/personalities';

const VOICES = [
  { id: 'af_bella', name: 'Bella (Female, Warm)', gender: 'female' },
  { id: 'af_sarah', name: 'Sarah (Female, Clear)', gender: 'female' },
  { id: 'bf_emma', name: 'Emma (Female, British)', gender: 'female' },
  { id: 'am_michael', name: 'Michael (Male, Deep)', gender: 'male' },
  { id: 'am_adam', name: 'Adam (Male, Friendly)', gender: 'male' },
];

export default function BrainSettings() {
  const { config, updateConfig, isConnected } = useBrain();

  const [localConfig, setLocalConfig] = useState(config);
  const [hasChanges, setHasChanges] = useState(false);

  const handlePersonalityChange = (personality: string) => {
    setLocalConfig({ ...localConfig, personality });
    setHasChanges(true);
  };

  const handleVoiceChange = (voice: string) => {
    setLocalConfig({ ...localConfig, voice });
    setHasChanges(true);
  };

  const handleSpeedChange = (speed: number) => {
    setLocalConfig({ ...localConfig, speed });
    setHasChanges(true);
  };

  const handleSilenceChange = (silenceDuration: number) => {
    setLocalConfig({ ...localConfig, silenceDuration });
    setHasChanges(true);
  };

  const handleRawModeChange = (rawMode: boolean) => {
    setLocalConfig({ ...localConfig, rawMode });
    setHasChanges(true);
  };

  const handleSave = () => {
    updateConfig(localConfig);
    setHasChanges(false);
  };

  const handleReset = () => {
    setLocalConfig(config);
    setHasChanges(false);
  };

  const selectedPersonality = PERSONALITIES.find(p => p.id === localConfig.personality) || PERSONALITIES[0];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Brain Settings</h1>
        <p className="text-gray-400">Configure personality, voice, and behavior</p>
      </div>

      {/* Connection Status */}
      {!isConnected && (
        <div className="card bg-yellow-500/10 border-yellow-500/50 mb-6">
          <div className="text-yellow-500 font-semibold mb-2">⚠️ Not Connected to MQTT</div>
          <div className="text-sm text-gray-400">
            Settings can be changed but won&apos;t be applied until connection is restored.
          </div>
        </div>
      )}

      {/* Personality Section */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Personality</h2>
        <p className="text-sm text-gray-400 mb-4">
          Choose who Sage should be. Each personality has a unique voice, style, and approach.
        </p>

        <div className="mb-4 p-4 rounded-lg border border-architect-border bg-architect-gray">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="font-medium">Raw Mode</div>
              <div className="text-sm text-gray-400">
                Bypass persona and system prompts; send plain chat to Ollama.
              </div>
            </div>
            <input
              type="checkbox"
              checked={localConfig.rawMode}
              onChange={(e) => handleRawModeChange(e.target.checked)}
              className="h-5 w-5 accent-architect-accent"
            />
          </div>
        </div>

        <div className="space-y-3">
          {PERSONALITIES.map((personality) => (
            <button
              key={personality.id}
              onClick={() => handlePersonalityChange(personality.id)}
              className={`w-full text-left p-4 rounded-lg border-2 transition-all ${localConfig.personality === personality.id
                  ? 'border-architect-accent bg-architect-accent/10'
                  : 'border-architect-border hover:border-architect-accent/50'
                }`}
            >
              <div className="flex items-start gap-3">
                <div className="text-4xl">{personality.emoji}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="font-semibold text-lg">{personality.name}</div>
                    {localConfig.personality === personality.id && (
                      <span className="text-xs bg-architect-accent text-white px-2 py-1 rounded">
                        Active
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-400 mb-2">{personality.description}</div>
                  <div className="flex flex-wrap gap-2">
                    {personality.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs bg-architect-gray px-2 py-1 rounded text-gray-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Voice Settings */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Voice Settings</h2>

        {/* Voice Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Voice</label>
          <select
            value={localConfig.voice}
            onChange={(e) => handleVoiceChange(e.target.value)}
            className="w-full bg-architect-gray border border-architect-border rounded-lg px-4 py-3 text-white focus:outline-none focus:border-architect-accent"
          >
            {VOICES.map((voice) => (
              <option key={voice.id} value={voice.id}>
                {voice.name}
              </option>
            ))}
          </select>
        </div>

        {/* Speed Slider */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            Speech Speed: {localConfig.speed.toFixed(1)}x
          </label>
          <input
            type="range"
            min="0.5"
            max="1.5"
            step="0.1"
            value={localConfig.speed}
            onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-architect-gray rounded-lg appearance-none cursor-pointer accent-architect-accent"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Slower</span>
            <span>Normal</span>
            <span>Faster</span>
          </div>
        </div>
      </div>

      {/* Detection Settings */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Detection Settings</h2>

        {/* Silence Duration */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Pause Detection: {localConfig.silenceDuration.toFixed(1)}s
          </label>
          <input
            type="range"
            min="0.3"
            max="2.0"
            step="0.1"
            value={localConfig.silenceDuration}
            onChange={(e) => handleSilenceChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-architect-gray rounded-lg appearance-none cursor-pointer accent-architect-accent"
          />
          <div className="text-sm text-gray-400 mt-2">
            How long to wait after you stop talking before processing your speech.
          </div>
        </div>
      </div>

      {/* Save/Reset Buttons */}
      {hasChanges && (
        <div className="fixed bottom-6 right-6 flex gap-3 bg-architect-gray border border-architect-border rounded-lg p-4 shadow-xl">
          <button
            onClick={handleReset}
            className="btn-secondary flex items-center gap-2"
          >
            <RotateCcw size={18} />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!isConnected}
            className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save size={18} />
            Save Changes
          </button>
        </div>
      )}

      {/* Info Box */}
      <div className="card bg-blue-500/10 border-blue-500/50">
        <div className="text-sm text-gray-300">
          <div className="font-semibold mb-2">💡 How It Works</div>
          <ul className="space-y-1 list-disc list-inside">
            <li>Personality changes take effect immediately on the next response</li>
            <li>Voice changes apply to the next speech output</li>
            <li>Settings are saved to the brain via MQTT</li>
            <li>All changes persist across sessions</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
