'use client';

import React, { createContext, useContext, useEffect, useState, useRef, ReactNode } from 'react';
import { getMQTTBridge, MQTTMessage } from '@/lib/mqtt-bridge';

interface SystemStatus {
  sttStatus: string;
  brainStatus: string;
  ttsStatus: string;
  audioLevel: number;
  sttMs: number;
  sttModelLoadMs: number;
  ttsModelLoadMs: number;
  ttsGenMs: number;
  ttsAudioDurationS: number;
  ttsEngine: string;
  totalMs: number;
  lastRejectedReason: string | null;
}

interface TranscriptEntry {
  timestamp: string;
  type: 'user' | 'assistant' | 'system';
  message: string;
}

interface VisionSnapshot {
  status: string;
  location: string;
  peopleCount: number;
  activity: string;
  mood: string;
  objects: string[];
  lastVlm: string;
  lastUpdate: string | null;
}

interface TelemetryEvent {
  timestamp: string;
  topic: string;
  summary: string;
}

interface ServiceConfig {
  sttEnabled: boolean;
  ttsEnabled: boolean;
  personality: string;
  voice: string;
  speed: number;
  silenceDuration: number;
  rawMode: boolean;
}

interface BrainContextType {
  status: SystemStatus;
  transcripts: TranscriptEntry[];
  vision: VisionSnapshot;
  telemetry: TelemetryEvent[];
  config: ServiceConfig;
  isConnected: boolean;
  sendMessage: (message: string) => void;
  toggleSTT: (enabled: boolean) => void;
  toggleTTS: (enabled: boolean) => void;
  updateConfig: (updates: Partial<ServiceConfig>) => void;
  sendBrainCommand: (command: 'clear_conversation' | 'clear_memory' | 'clear_episodes') => void;
  requestVisionScan: (location?: string) => void;
  clearTranscripts: () => void;
  clearTelemetry: () => void;
}

const BrainContext = createContext<BrainContextType | undefined>(undefined);

const TELEMETRY_LIMIT = 120;
const TELEMETRY_FLUSH_MS = 200;
const AUDIO_LEVEL_UPDATE_MS = 100;
const AUDIO_LEVEL_MIN_DELTA = 0.02;

export function BrainProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SystemStatus>({
    sttStatus: 'offline',
    brainStatus: 'offline',
    ttsStatus: 'idle',
    audioLevel: 0,
    sttMs: 0,
    sttModelLoadMs: 0,
    ttsModelLoadMs: 0,
    ttsGenMs: 0,
    ttsAudioDurationS: 0,
    ttsEngine: 'unknown',
    totalMs: 0,
    lastRejectedReason: null,
  });

  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryEvent[]>([]);
  const [vision, setVision] = useState<VisionSnapshot>({
    status: 'offline',
    location: 'office',
    peopleCount: 0,
    activity: 'unknown',
    mood: 'unknown',
    objects: [],
    lastVlm: '',
    lastUpdate: null,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [config, setConfig] = useState<ServiceConfig>({
    sttEnabled: true,
    ttsEnabled: true,
    personality: 'kenyan_babe',
    voice: 'af_bella',
    speed: 1.0,
    silenceDuration: 0.7,
    rawMode: false,
  });

  // Streaming optimization: batch tokens to reduce re-renders
  const streamingBufferRef = useRef<string>('');
  const streamingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const requestStartRef = useRef<number | null>(null);
  const telemetryBufferRef = useRef<TelemetryEvent[]>([]);
  const telemetryFlushTimerRef = useRef<NodeJS.Timeout | null>(null);
  const telemetryLastByTopicRef = useRef<Map<string, number>>(new Map());
  const lastAudioUpdateMsRef = useRef(0);
  const lastAudioLevelRef = useRef(0);

  // Stable reference to message handler to prevent duplicate subscriptions
  const messageHandlerRef = useRef<((message: MQTTMessage) => void) | null>(null);

  const summarizePayload = (payload: any): string => {
    if (payload === null || payload === undefined) return 'null';
    if (typeof payload === 'string') return payload.slice(0, 120);
    if (typeof payload !== 'object') return String(payload);

    if (payload.text) return String(payload.text).slice(0, 120);
    if (payload.description) return String(payload.description).slice(0, 120);
    if (payload.status) {
      const parts = [`status=${payload.status}`];
      if (payload.phase) parts.push(`phase=${payload.phase}`);
      if (payload.engine) parts.push(`engine=${payload.engine}`);
      if (payload.model) parts.push(`model=${payload.model}`);
      if (payload.queue_depth !== undefined) parts.push(`queue=${payload.queue_depth}`);
      return parts.join(' ');
    }
    if (payload.event && (payload.load_ms !== undefined || payload.model_load_ms !== undefined || payload.gen_ms !== undefined)) {
      const bits = [`event=${payload.event}`];
      if (payload.engine) bits.push(`engine=${payload.engine}`);
      if (payload.load_ms !== undefined) bits.push(`load=${payload.load_ms}ms`);
      if (payload.model_load_ms !== undefined) bits.push(`model_load=${payload.model_load_ms}ms`);
      if (payload.gen_ms !== undefined) bits.push(`gen=${payload.gen_ms}ms`);
      if (payload.audio_duration_s !== undefined) bits.push(`audio=${payload.audio_duration_s}s`);
      return bits.join(' ');
    }
    if (payload.reason) return `reason=${payload.reason}`;
    if (payload.activity || payload.mood) {
      const activity = payload.activity ?? 'unknown';
      const mood = payload.mood ?? 'unknown';
      return `activity=${activity} mood=${mood}`;
    }

    try {
      return JSON.stringify(payload).slice(0, 120);
    } catch {
      return '[unserializable payload]';
    }
  };

  const getTelemetryThrottleMs = (topic: string): number => {
    if (topic === 'sage/stt/levels') return 750;
    if (topic === 'sage/stt/metrics') return 1000;
    if (topic === 'sage/tts/metrics') return 250;
    if (topic === 'sage/stt/status') return 250;
    if (topic === 'sage/tts/status') return 250;
    if (/^sage\/vision\/[^/]+\/state$/.test(topic)) return 500;
    return 0;
  };

  const flushTelemetryBuffer = () => {
    telemetryFlushTimerRef.current = null;
    if (telemetryBufferRef.current.length === 0) return;

    const batch = telemetryBufferRef.current;
    telemetryBufferRef.current = [];

    setTelemetry((prev) => {
      const merged = [...prev, ...batch];
      return merged.length > TELEMETRY_LIMIT ? merged.slice(-TELEMETRY_LIMIT) : merged;
    });
  };

  const addTelemetry = (topic: string, payload: any, timestamp: string, timestampMs: number) => {
    // Skip very chatty token stream to keep timeline useful.
    if (topic === 'sage/voice/streaming') return;

    const throttleMs = getTelemetryThrottleMs(topic);
    if (throttleMs > 0) {
      const lastTs = telemetryLastByTopicRef.current.get(topic) || 0;
      if (timestampMs - lastTs < throttleMs) return;
      telemetryLastByTopicRef.current.set(topic, timestampMs);
    }

    const summary = summarizePayload(payload);
    telemetryBufferRef.current.push({ timestamp, topic, summary });

    if (!telemetryFlushTimerRef.current) {
      telemetryFlushTimerRef.current = setTimeout(flushTelemetryBuffer, TELEMETRY_FLUSH_MS);
    }
  };

  // Flush streaming buffer and update UI
  const flushStreamingBuffer = () => {
    if (streamingBufferRef.current) {
      const chunk = streamingBufferRef.current;
      streamingBufferRef.current = '';

      setTranscripts((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'assistant') {
          return [
            ...prev.slice(0, -1),
            { ...last, message: last.message + chunk }
          ];
        } else {
          return [
            ...prev.slice(-49),
            { type: 'assistant', message: chunk, timestamp: new Date().toLocaleTimeString() }
          ];
        }
      });
    }
  };

  const normalizeForCompare = (text: string): string =>
    text.replace(/\s+/g, ' ').trim();

  const addOrMergeAssistantTranscript = (message: string, timestamp: string) => {
    if (!message?.trim()) return;

    setTranscripts((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.type === 'assistant') {
        const lastNorm = normalizeForCompare(last.message);
        const nextNorm = normalizeForCompare(message);

        // Duplicate final payload after streaming flush; keep one copy.
        if (nextNorm === lastNorm) {
          return prev;
        }

        // Final payload extends streamed partial text; merge instead of append.
        if (nextNorm.startsWith(lastNorm)) {
          return [
            ...prev.slice(0, -1),
            { ...last, message, timestamp },
          ];
        }

        // Existing assistant message is already longer/richer; ignore shorter echo.
        if (lastNorm.startsWith(nextNorm)) {
          return prev;
        }
      }

      return [
        ...prev.slice(-49),
        { type: 'assistant', message, timestamp },
      ];
    });
  };

  // Define message handler with stable reference
  const handleMQTTMessage = (message: MQTTMessage) => {
    const { topic, payload } = message;
    const timestampMs = message.timestamp || Date.now();
    const timestamp = new Date(timestampMs).toLocaleTimeString();

    try {
      addTelemetry(topic, payload, timestamp, timestampMs);

      // Brain status
      if (topic === 'sage/brain/status') {
        const brainStatus = payload.status || 'unknown';
        setStatus((prev) => (
          prev.brainStatus === brainStatus
            ? prev
            : { ...prev, brainStatus }
        ));
      }

      // STT status
      else if (topic === 'sage/stt/status') {
        const sttStatus = payload.status || 'unknown';
        setStatus((prev) => (
          prev.sttStatus === sttStatus
            ? prev
            : { ...prev, sttStatus }
        ));
        const enabled = sttStatus !== 'offline';
        setConfig((prev) => (
          prev.sttEnabled === enabled
            ? prev
            : { ...prev, sttEnabled: enabled }
        ));

        if (payload.status === 'rejected') {
          const reason = payload.reason || 'unknown';
          setStatus((prev) => (
            prev.lastRejectedReason === reason
              ? prev
              : { ...prev, lastRejectedReason: reason }
          ));
          addTranscript('system', `Voice rejected: ${payload.reason}`, timestamp);
        }
      }

      // Audio levels
      else if (topic === 'sage/stt/levels') {
        const nextAudioLevel = Number(payload.vis || 0);
        const delta = Math.abs(nextAudioLevel - lastAudioLevelRef.current);
        if (timestampMs - lastAudioUpdateMsRef.current < AUDIO_LEVEL_UPDATE_MS) return;
        if (delta < AUDIO_LEVEL_MIN_DELTA) return;

        lastAudioUpdateMsRef.current = timestampMs;
        lastAudioLevelRef.current = nextAudioLevel;
        setStatus((prev) => ({ ...prev, audioLevel: nextAudioLevel }));
      }

      // STT metrics
      else if (topic === 'sage/stt/metrics') {
        setStatus((prev) => {
          const next = { ...prev };
          if (typeof payload.transcribe_ms === 'number') {
            next.sttMs = payload.transcribe_ms;
          }
          if (typeof payload.model_load_ms === 'number') {
            next.sttModelLoadMs = payload.model_load_ms;
          }
          return next;
        });
      }

      // Voice transcript
      else if (topic === 'sage/voice/transcript') {
        const text = typeof payload === 'string' ? payload : payload.text;
        addTranscript('user', text, timestamp);
        requestStartRef.current = Date.now();
      }

      // Voice response
      else if (topic === 'sage/voice/response') {
        // Flush any remaining streaming buffer before adding final response
        if (streamingTimerRef.current) {
          clearTimeout(streamingTimerRef.current);
          streamingTimerRef.current = null;
        }
        flushStreamingBuffer();

        const text = typeof payload === 'string' ? payload : payload.text;
        if (text) {
          addOrMergeAssistantTranscript(text, timestamp);

          if (requestStartRef.current) {
            const totalMs = Date.now() - requestStartRef.current;
            requestStartRef.current = null;
            setStatus((prev) => ({ ...prev, totalMs }));
          }
        }
      }

      // TTS status
      else if (topic === 'sage/tts/status') {
        const ttsStatus = payload.status || 'idle';
        setStatus((prev) => (
          prev.ttsStatus === ttsStatus
            ? prev
            : { ...prev, ttsStatus }
        ));
        if (payload.engine) {
          const nextEngine = String(payload.engine);
          setStatus((prev) => (
            prev.ttsEngine === nextEngine
              ? prev
              : { ...prev, ttsEngine: nextEngine }
          ));
        }
      }

      // TTS metrics
      else if (topic === 'sage/tts/metrics') {
        setStatus((prev) => {
          const next = { ...prev };
          if (typeof payload.load_ms === 'number') {
            next.ttsModelLoadMs = payload.load_ms;
          }
          if (typeof payload.model_load_ms === 'number') {
            next.ttsModelLoadMs = payload.model_load_ms;
          }
          if (typeof payload.gen_ms === 'number') {
            next.ttsGenMs = payload.gen_ms;
          }
          if (typeof payload.audio_duration_s === 'number') {
            next.ttsAudioDurationS = payload.audio_duration_s;
          }
          if (typeof payload.engine === 'string' && payload.engine.trim()) {
            next.ttsEngine = payload.engine;
          }
          return next;
        });
      }

      // Voice Streaming (Real-time updates) - Optimized with batching
      else if (topic === 'sage/voice/streaming') {
        const chunk = payload.text || '';

        // Add to buffer instead of immediate render
        streamingBufferRef.current += chunk;

        // Clear existing timer
        if (streamingTimerRef.current) {
          clearTimeout(streamingTimerRef.current);
        }

        // Batch updates: flush every 100ms or after 50 chars
        if (streamingBufferRef.current.length >= 50) {
          // Flush immediately if buffer is large
          flushStreamingBuffer();
        } else {
          // Otherwise wait 100ms to batch more tokens
          streamingTimerRef.current = setTimeout(flushStreamingBuffer, 100);
        }
      }


      // Brain Config (Update local state when backend confirms)
      else if (topic === 'sage/brain/config') {
        if (payload.personality) {
          setConfig(prev => ({
            ...prev,
            personality: payload.personality
          }));
        }
        if (typeof payload.raw_mode === 'boolean') {
          setConfig(prev => ({
            ...prev,
            rawMode: payload.raw_mode
          }));
        }
      }

      // Vision Status (sage/vision/<location>/status)
      else if (/^sage\/vision\/[^/]+\/status$/.test(topic)) {
        const parts = topic.split('/');
        const location = parts[2] || 'unknown';
        setVision((prev) => ({
          ...prev,
          status: payload.status || 'unknown',
          location,
          lastUpdate: timestamp,
        }));
      }

      // Vision State (sage/vision/<location>/state)
      else if (/^sage\/vision\/[^/]+\/state$/.test(topic)) {
        const parts = topic.split('/');
        const location = parts[2] || 'unknown';
        setVision((prev) => ({
          ...prev,
          status: 'online',
          location,
          peopleCount: payload.people_count ?? prev.peopleCount,
          activity: payload.activity ?? prev.activity,
          mood: payload.primary_emotion ?? prev.mood,
          objects: Array.isArray(payload.detected_objects) ? payload.detected_objects : prev.objects,
          lastUpdate: timestamp,
        }));
      }

      // Vision VLM Result (sage/vision/<location>/vlm)
      else if (/^sage\/vision\/[^/]+\/vlm$/.test(topic)) {
        const parts = topic.split('/');
        const location = parts[2] || 'unknown';
        setVision((prev) => ({
          ...prev,
          status: 'online',
          location,
          activity: payload.activity ?? prev.activity,
          mood: payload.mood ?? prev.mood,
          lastVlm: payload.description || prev.lastVlm,
          lastUpdate: timestamp,
        }));
      }
    } catch (error) {
      console.error('[Brain] Error processing MQTT message:', error);
    }
  };

  // Store handler in ref for stable reference across re-renders
  messageHandlerRef.current = handleMQTTMessage;

  // MQTT connection and subscription effect
  useEffect(() => {
    const bridge = getMQTTBridge();
    let cancelled = false;

    // Wrapper that uses the ref to always call the latest handler
    const stableHandler = (message: MQTTMessage) => {
      if (cancelled) return;
      messageHandlerRef.current?.(message);
    };

    // Check if already connected (from previous mount or other components)
    if (bridge.isConnected()) {
      console.log('[Brain] Using existing MQTT connection');
      if (!cancelled) setIsConnected(true);
      // Subscribe to topics
      if (!cancelled) {
        bridge.subscribe('sage/#', stableHandler);
        bridge.publish('sage/stt/control', { enabled: config.sttEnabled }, { retain: true });
        bridge.publish('sage/tts/control', { enabled: config.ttsEnabled }, { retain: true });
      }
    } else {
      // Only connect if not already connected
      console.log('[Brain] Establishing new MQTT connection');
      bridge.connect()
        .then((connected) => {
          if (cancelled) return;
          setIsConnected(connected);

          if (connected) {
            // Subscribe to all sage topics
            bridge.subscribe('sage/#', stableHandler);
            bridge.publish('sage/stt/control', { enabled: config.sttEnabled }, { retain: true });
            bridge.publish('sage/tts/control', { enabled: config.ttsEnabled }, { retain: true });
          }
        })
        .catch((error) => {
          if (cancelled) return;
          console.error('[Brain] Failed to connect to MQTT:', error);
          setIsConnected(false);
        });
    }

    // Cleanup: unsubscribe with the same stable handler reference
    return () => {
      cancelled = true;
      bridge.unsubscribe('sage/#', stableHandler);
      if (streamingTimerRef.current) {
        clearTimeout(streamingTimerRef.current);
      }
      if (telemetryFlushTimerRef.current) {
        clearTimeout(telemetryFlushTimerRef.current);
      }
    };
  }, []); // Empty deps - only run on mount/unmount

  const addTranscript = (type: 'user' | 'assistant' | 'system', message: string, timestamp: string) => {
    setTranscripts((prev) => [
      ...prev.slice(-49), // Keep last 49 + new one = 50 total
      { type, message, timestamp },
    ]);
  };

  const sendMessage = (message: string) => {
    const bridge = getMQTTBridge();
    if (!bridge.isConnected()) {
      console.error('[Brain] Cannot send message: MQTT not connected');
      return;
    }

    // addTranscript('user', message, timestamp); // Removed local echo to prevent duplicates
    requestStartRef.current = Date.now();

    bridge.publish('sage/voice/transcript', message);
  };

  const toggleSTT = (enabled: boolean) => {
    const bridge = getMQTTBridge();
    bridge.publish('sage/stt/control', { enabled }, { retain: true });
    setConfig((prev) => ({ ...prev, sttEnabled: enabled }));
  };

  const toggleTTS = (enabled: boolean) => {
    const bridge = getMQTTBridge();
    bridge.publish('sage/tts/control', { enabled }, { retain: true });
    setConfig((prev) => ({ ...prev, ttsEnabled: enabled }));
  };

  const updateConfig = (updates: Partial<ServiceConfig>) => {
    const bridge = getMQTTBridge();

    if (updates.personality || updates.rawMode !== undefined) {
      bridge.publish('sage/brain/config', {
        personality: updates.personality,
        raw_mode: updates.rawMode
      });
    }

    if (updates.voice || updates.speed !== undefined) {
      bridge.publish('sage/voice/config', {
        voice: updates.voice || config.voice,
        speed: updates.speed ?? config.speed,
      });
    }

    if (updates.silenceDuration !== undefined) {
      bridge.publish('sage/config/performance', {
        silence_duration: updates.silenceDuration,
      });
    }

    setConfig((prev) => ({ ...prev, ...updates }));
  };

  const clearTranscripts = () => {
    setTranscripts([]);
  };

  const clearTelemetry = () => {
    telemetryBufferRef.current = [];
    if (telemetryFlushTimerRef.current) {
      clearTimeout(telemetryFlushTimerRef.current);
      telemetryFlushTimerRef.current = null;
    }
    setTelemetry([]);
  };

  const sendBrainCommand = (command: 'clear_conversation' | 'clear_memory' | 'clear_episodes') => {
    const bridge = getMQTTBridge();
    bridge.publish('sage/brain/command', { command });
    addTranscript('system', `Command sent: ${command}`, new Date().toLocaleTimeString());
  };

  const requestVisionScan = (location?: string) => {
    const bridge = getMQTTBridge();
    const topic = location ? `sage/vision/${location}/request` : 'sage/vision/request';
    bridge.publish(topic, { source: 'pwa', ts: Date.now() });
    addTranscript('system', `Vision scan requested (${location || 'global'})`, new Date().toLocaleTimeString());
  };

  return (
    <BrainContext.Provider
      value={{
        status,
        transcripts,
        vision,
        telemetry,
        config,
        isConnected,
        sendMessage,
        toggleSTT,
        toggleTTS,
        updateConfig,
        sendBrainCommand,
        requestVisionScan,
        clearTranscripts,
        clearTelemetry,
      }}
    >
      {children}
    </BrainContext.Provider>
  );
}

export function useBrain() {
  const context = useContext(BrainContext);
  if (!context) {
    throw new Error('useBrain must be used within BrainProvider');
  }
  return context;
}
