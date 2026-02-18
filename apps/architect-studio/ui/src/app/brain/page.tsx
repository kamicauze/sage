'use client';

import { useEffect, useRef, useState } from 'react';
import { Brain, AlertCircle, Power, PowerOff, Eye, Database, Trash2, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useBrain } from '@/contexts/BrainContext';
import { getPersonalityById } from '@/lib/personalities';

export default function BrainMonitor() {
  const {
    status,
    transcripts,
    telemetry,
    vision,
    config,
    isConnected,
    toggleSTT,
    toggleTTS,
    clearTranscripts,
    clearTelemetry,
    sendBrainCommand,
    requestVisionScan,
    sendMessage,
  } = useBrain();
  const [probeRunning, setProbeRunning] = useState(false);
  const [probeError, setProbeError] = useState<string | null>(null);
  const [probeResult, setProbeResult] = useState<{
    roundTripMs: number;
    backendTotalMs: number;
    backendSttMs: number;
    timestamp: string;
    responseSummary: string;
  } | null>(null);
  const probeStartMsRef = useRef<number | null>(null);
  const probeTelemetryStartRef = useRef<number>(0);
  const probeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getMainStatus = () => {
    const { sttStatus, brainStatus, ttsStatus } = status;

    if (brainStatus === 'starting') {
      return { emoji: '⏳', text: 'WARMING UP', detail: 'Brain is loading...' };
    }
    if (ttsStatus === 'speaking') {
      return { emoji: '🔊', text: 'SPEAKING', detail: 'Sage is talking...' };
    }
    if (sttStatus === 'hearing') {
      return { emoji: '👂', text: 'HEARING', detail: 'Listening to you...' };
    }
    if (sttStatus === 'processing') {
      return { emoji: '⚙️', text: 'THINKING', detail: 'Processing your speech...' };
    }
    if (sttStatus === 'listening' && brainStatus === 'ready') {
      return { emoji: '🎤', text: 'READY', detail: 'Waiting for you to speak...' };
    }
    if (sttStatus === 'rejected') {
      return { emoji: '🚫', text: 'REJECTED', detail: status.lastRejectedReason || 'Voice not recognized' };
    }
    if (sttStatus === 'offline' && brainStatus === 'ready') {
      return { emoji: '💤', text: 'STANDBY', detail: 'STT disabled - brain ready for text' };
    }
    if (sttStatus === 'offline') {
      return { emoji: '⚫', text: 'OFFLINE', detail: 'STT service not running' };
    }

    return { emoji: '❓', text: 'UNKNOWN', detail: `${sttStatus} / ${brainStatus}` };
  };

  const mainStatus = getMainStatus();
  const audioBar = '▇'.repeat(Math.floor(status.audioLevel * 20));
  const currentPersonality = getPersonalityById(config.personality);
  const recentTelemetry = telemetry.slice(-30).reverse();
  const runtimeSignals = telemetry
    .filter((event) => (
      event.topic === 'sage/brain/status' ||
      event.topic === 'sage/stt/status' ||
      event.topic === 'sage/tts/status' ||
      event.topic === 'sage/stt/metrics' ||
      event.topic === 'sage/tts/metrics'
    ))
    .slice(-16)
    .reverse();

  const serviceDot = (serviceStatus: string) => {
    if (serviceStatus === 'ready' || serviceStatus === 'listening' || serviceStatus === 'idle' || serviceStatus === 'done') {
      return 'bg-green-500';
    }
    if (serviceStatus === 'warming' || serviceStatus === 'starting' || serviceStatus === 'processing' || serviceStatus === 'hearing' || serviceStatus === 'speaking') {
      return 'bg-yellow-400 animate-pulse';
    }
    if (serviceStatus === 'disabled' || serviceStatus === 'offline') {
      return 'bg-gray-500';
    }
    if (serviceStatus === 'error' || serviceStatus === 'rejected') {
      return 'bg-red-500';
    }
    return 'bg-blue-500';
  };

  const runLatencyProbe = () => {
    if (!isConnected) {
      setProbeError('Cannot run probe: MQTT is not connected.');
      return;
    }
    if (status.brainStatus !== 'ready') {
      setProbeError(`Cannot run probe: Brain status is '${status.brainStatus}'.`);
      return;
    }

    if (probeTimeoutRef.current) {
      clearTimeout(probeTimeoutRef.current);
      probeTimeoutRef.current = null;
    }

    setProbeError(null);
    setProbeResult(null);
    setProbeRunning(true);
    probeStartMsRef.current = Date.now();
    probeTelemetryStartRef.current = telemetry.length;

    // Prompt is short and deterministic to keep probe latency comparable across runs.
    sendMessage("Latency probe: reply with exactly 'pong'.");

    probeTimeoutRef.current = setTimeout(() => {
      setProbeRunning(false);
      setProbeError('Probe timed out waiting for sage/voice/response.');
      probeStartMsRef.current = null;
    }, 20000);
  };

  useEffect(() => {
    if (!probeRunning || probeStartMsRef.current === null) return;

    const newEvents = telemetry.slice(probeTelemetryStartRef.current);
    const responseEvent = [...newEvents].reverse().find((event) => event.topic === 'sage/voice/response');
    if (!responseEvent) return;

    const roundTripMs = Date.now() - probeStartMsRef.current;
    setProbeResult({
      roundTripMs,
      backendTotalMs: status.totalMs,
      backendSttMs: status.sttMs,
      timestamp: new Date().toLocaleTimeString(),
      responseSummary: responseEvent.summary,
    });
    setProbeRunning(false);
    probeStartMsRef.current = null;

    if (probeTimeoutRef.current) {
      clearTimeout(probeTimeoutRef.current);
      probeTimeoutRef.current = null;
    }
  }, [probeRunning, telemetry, status.totalMs, status.sttMs]);

  useEffect(() => {
    return () => {
      if (probeTimeoutRef.current) {
        clearTimeout(probeTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="p-4 md:p-6 max-w-[1520px] mx-auto">
      <div className="mb-4 flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1">Brain Monitor</h1>
          <p className="text-gray-400">Realtime status, warmup visibility, and voice pipeline telemetry.</p>
        </div>
        <Link
          href="/brain/settings"
          className="flex items-center gap-3 bg-architect-gray border border-architect-border hover:border-architect-accent transition-all px-4 py-2 rounded-lg group"
        >
          <div className="text-2xl">{currentPersonality.emoji}</div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-bold group-hover:text-architect-accent transition-colors">Active Personality</div>
            <div className="font-bold text-white leading-none">{currentPersonality.name}</div>
          </div>
        </Link>
      </div>

      <div className="grid grid-cols-1 2xl:grid-cols-12 gap-4">
        <div className="2xl:col-span-8 space-y-4">
          <div className="card">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-4">
                <div className="text-5xl">{mainStatus.emoji}</div>
                <div>
                  <div className="text-2xl font-bold text-architect-accent">{mainStatus.text}</div>
                  <div className="text-sm text-gray-400">{mainStatus.detail}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">STT</div>
                  <div className="font-mono text-lg">{status.sttMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Total</div>
                  <div className="font-mono text-lg">{status.totalMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">TTS Gen</div>
                  <div className="font-mono text-lg">{status.ttsGenMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Engine</div>
                  <div className="font-mono text-lg">{status.ttsEngine || 'unknown'}</div>
                </div>
              </div>
            </div>

            <div className="bg-architect-gray rounded-lg p-3">
              <div className="text-xs text-gray-400 mb-2">Audio Input Level</div>
              <div className="font-mono text-green-500 h-6 overflow-hidden">
                {audioBar || <span className="text-gray-600">Waiting for audio...</span>}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${serviceDot(status.brainStatus)}`}></div>
                    <span className="text-xs uppercase text-gray-400">Brain Core</span>
                  </div>
                  <Brain size={16} className="text-architect-accent" />
                </div>
                <div className="font-mono mt-2">{status.brainStatus}</div>
              </div>
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${serviceDot(status.sttStatus)}`}></div>
                    <span className="text-xs uppercase text-gray-400">STT</span>
                  </div>
                  <button
                    onClick={() => toggleSTT(!config.sttEnabled)}
                    className={`p-2 rounded-lg transition-colors ${config.sttEnabled
                      ? 'bg-green-500/20 text-green-500 hover:bg-green-500/30'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    title={config.sttEnabled ? 'Disable STT' : 'Enable STT'}
                  >
                    {config.sttEnabled ? <Power size={14} /> : <PowerOff size={14} />}
                  </button>
                </div>
                <div className="font-mono mt-2">{status.sttStatus}</div>
                <div className="text-xs text-gray-400 mt-1">Model load: {status.sttModelLoadMs || 0}ms</div>
              </div>
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${serviceDot(status.ttsStatus)}`}></div>
                    <span className="text-xs uppercase text-gray-400">TTS</span>
                  </div>
                  <button
                    onClick={() => toggleTTS(!config.ttsEnabled)}
                    className={`p-2 rounded-lg transition-colors ${config.ttsEnabled
                      ? 'bg-green-500/20 text-green-500 hover:bg-green-500/30'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    title={config.ttsEnabled ? 'Disable TTS' : 'Enable TTS'}
                  >
                    {config.ttsEnabled ? <Power size={14} /> : <PowerOff size={14} />}
                  </button>
                </div>
                <div className="font-mono mt-2">{status.ttsStatus}</div>
                <div className="text-xs text-gray-400 mt-1">Load: {status.ttsModelLoadMs || 0}ms | audio: {status.ttsAudioDurationS || 0}s</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
              <div>
                <div className="text-lg font-semibold">Latency Probe</div>
                <div className="text-sm text-gray-400">Runs a deterministic ping through your current voice path.</div>
              </div>
              <button
                onClick={runLatencyProbe}
                disabled={probeRunning || !isConnected}
                className="btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw size={16} className={probeRunning ? 'animate-spin' : ''} />
                {probeRunning ? 'Running Probe...' : 'Run Probe'}
              </button>
            </div>
            {probeError && <div className="text-sm text-yellow-400 mb-2">{probeError}</div>}
            {!probeError && !probeResult && !probeRunning && <div className="text-sm text-gray-400">No probe run yet.</div>}
            {probeResult && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Round-trip</div>
                  <div className="font-mono text-lg">{probeResult.roundTripMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Backend Total</div>
                  <div className="font-mono text-lg">{probeResult.backendTotalMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Backend STT</div>
                  <div className="font-mono text-lg">{probeResult.backendSttMs}ms</div>
                </div>
                <div className="bg-architect-gray rounded-lg p-3">
                  <div className="text-[11px] text-gray-400 mb-1">Captured</div>
                  <div className="font-mono text-lg">{probeResult.timestamp}</div>
                </div>
                <div className="col-span-2 lg:col-span-4 text-xs text-gray-400 truncate">
                  Response summary: {probeResult.responseSummary}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <Database className="text-architect-accent" size={20} />
              <div className="text-lg font-semibold">Runtime Commands</div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <button
                onClick={() => requestVisionScan(vision.location || 'office')}
                className="btn-secondary flex items-center justify-center gap-2"
              >
                <Eye size={16} />
                Scan Vision
              </button>
              <button
                onClick={() => sendBrainCommand('clear_conversation')}
                className="btn-secondary flex items-center justify-center gap-2"
              >
                <Trash2 size={16} />
                Clear Conversation
              </button>
              <button
                onClick={() => sendBrainCommand('clear_episodes')}
                className="btn-secondary flex items-center justify-center gap-2"
              >
                <RefreshCw size={16} />
                Clear Episodes
              </button>
              <button
                onClick={() => sendBrainCommand('clear_memory')}
                className="btn-secondary flex items-center justify-center gap-2 border-red-500/40 hover:border-red-500/80"
              >
                <Database size={16} />
                Clear All Memory
              </button>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center gap-3 mb-3">
              <Eye className="text-architect-accent" size={20} />
              <div className="text-lg font-semibold">Vision Telemetry</div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Status</div>
                <div className="font-mono">{vision.status}</div>
              </div>
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Location</div>
                <div className="font-mono">{vision.location || '—'}</div>
              </div>
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">People</div>
                <div className="font-mono">{vision.peopleCount}</div>
              </div>
              <div className="bg-architect-gray rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Activity</div>
                <div className="font-mono">{vision.activity || 'unknown'}</div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-3">Mood: <span className="text-gray-200">{vision.mood || 'unknown'}</span></div>
            <div className="text-xs text-gray-400 mt-1">Objects: <span className="text-gray-200">{vision.objects.length > 0 ? vision.objects.join(', ') : 'none'}</span></div>
            <div className="text-xs text-gray-400 mt-1 truncate">Last VLM: <span className="text-gray-200">{vision.lastVlm || 'No VLM output yet'}</span></div>
            <div className="text-xs text-gray-500 mt-1">Last update: {vision.lastUpdate || '—'}</div>
          </div>
        </div>

        <div className="2xl:col-span-4 space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl font-semibold">Runtime Snapshot</h2>
              <span className={`text-xs px-2 py-1 rounded-full border ${isConnected ? 'border-green-500/30 text-green-300 bg-green-500/10' : 'border-yellow-500/30 text-yellow-300 bg-yellow-500/10'}`}>
                {isConnected ? 'MQTT Connected' : 'MQTT Offline'}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2 text-sm mb-3">
              <div className="flex items-center justify-between bg-architect-gray rounded-lg p-2.5">
                <span className="text-gray-400">Brain</span>
                <span className="font-mono">{status.brainStatus}</span>
              </div>
              <div className="flex items-center justify-between bg-architect-gray rounded-lg p-2.5">
                <span className="text-gray-400">STT</span>
                <span className="font-mono">{status.sttStatus} ({status.sttModelLoadMs || 0}ms load)</span>
              </div>
              <div className="flex items-center justify-between bg-architect-gray rounded-lg p-2.5">
                <span className="text-gray-400">TTS</span>
                <span className="font-mono">{status.ttsStatus} ({status.ttsEngine})</span>
              </div>
              <div className="flex items-center justify-between bg-architect-gray rounded-lg p-2.5">
                <span className="text-gray-400">TTS load/gen</span>
                <span className="font-mono">{status.ttsModelLoadMs || 0}ms / {status.ttsGenMs || 0}ms</span>
              </div>
            </div>
            <div className="text-xs text-gray-400 mb-2">Warmup + service signal stream</div>
            <div className="bg-architect-gray rounded-lg p-3 font-mono text-xs h-56 overflow-y-auto">
              {runtimeSignals.length === 0 ? (
                <div className="text-gray-500 text-center py-8">No warmup signals yet.</div>
              ) : (
                <div className="space-y-2">
                  {runtimeSignals.map((event, i) => (
                    <div key={`${event.timestamp}-${event.topic}-${i}`} className="grid grid-cols-12 gap-2">
                      <span className="col-span-3 text-gray-500">{event.timestamp}</span>
                      <span className="col-span-5 text-blue-300 truncate">{event.topic}</span>
                      <span className="col-span-4 text-gray-200 truncate">{event.summary}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {!isConnected && (
            <div className="card bg-yellow-500/10 border-yellow-500/50">
              <div className="flex items-center gap-3">
                <AlertCircle className="text-yellow-500" size={22} />
                <div>
                  <div className="font-semibold text-yellow-400">Not Connected to Brain</div>
                  <div className="text-sm text-gray-400 mt-1">
                    MQTT WebSocket is offline. Start mosquitto with WS support on port 9001.
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Run: <code className="bg-gray-800 px-2 py-1 rounded">mosquitto -c mosquitto.conf</code>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl font-semibold">MQTT Activity</h2>
              <button onClick={clearTelemetry} className="btn-secondary text-sm">Clear</button>
            </div>
            <div className="bg-architect-gray rounded-lg p-3 font-mono text-xs h-[36vh] min-h-[300px] overflow-y-auto">
              {recentTelemetry.length === 0 ? (
                <div className="text-gray-500 text-center py-8">No telemetry yet.</div>
              ) : (
                <div className="space-y-2">
                  {recentTelemetry.map((event, i) => (
                    <div key={`${event.timestamp}-${i}`} className="grid grid-cols-12 gap-2">
                      <span className="col-span-3 text-gray-500">{event.timestamp}</span>
                      <span className="col-span-4 text-blue-300 truncate">{event.topic}</span>
                      <span className="col-span-5 text-gray-200 truncate">{event.summary}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="card mt-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl font-semibold">Recent Activity</h2>
          <button onClick={clearTranscripts} className="btn-secondary text-sm">Clear</button>
        </div>
        <div className="bg-architect-gray rounded-lg p-4 font-mono text-sm h-[40vh] min-h-[320px] overflow-y-auto">
          {transcripts.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No activity yet. {config.sttEnabled ? 'Start talking to Sage!' : 'Enable STT or use Live Chat to send text messages.'}
            </div>
          ) : (
            <div className="space-y-2">
              {transcripts.map((entry, i) => (
                <div key={i} className="flex gap-3">
                  <span className="text-gray-500">[{entry.timestamp}]</span>
                  <span
                    className={
                      entry.type === 'user'
                        ? 'text-blue-400'
                        : entry.type === 'assistant'
                          ? 'text-green-400'
                          : 'text-gray-400'
                    }
                  >
                    {entry.type === 'user' ? '🎤 You:' : entry.type === 'assistant' ? '🧠 Sage:' : '⚙️'}
                  </span>
                  <span className="text-gray-200">{entry.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
