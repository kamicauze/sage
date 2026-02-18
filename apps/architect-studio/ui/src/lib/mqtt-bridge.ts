/**
 * MQTT Bridge for browser-based real-time communication with Sage Brain
 * Uses MQTT.js library to connect directly to MQTT broker from browser
 */

export interface MQTTMessage {
  topic: string;
  payload: any;
  timestamp: number;
}

export type MessageCallback = (message: MQTTMessage) => void;

export class MQTTBridge {
  private client: any = null;
  private callbacks: Map<string, Set<MessageCallback>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(
    private brokerUrl: string = 'ws://localhost:9001', // MQTT WebSocket port
    private options: Record<string, any> = {}
  ) {}

  /**
   * Connect to MQTT broker via WebSocket
   */
  async connect(): Promise<boolean> {
    try {
      console.log('[MQTT] Connecting to:', this.brokerUrl);

      // Lazy-load mqtt to keep initial bundle light for non-brain routes.
      const mqttModule = await import('mqtt');
      const mqttLib = mqttModule.default ?? mqttModule;

      this.client = mqttLib.connect(this.brokerUrl, {
        clean: true,
        reconnectPeriod: 5000,
        connectTimeout: 10000,
        ...this.options,
      });

      return new Promise((resolve, reject) => {
        if (!this.client) {
          reject(new Error('Failed to create MQTT client'));
          return;
        }

        this.client.on('connect', () => {
          console.log('[MQTT] Connected successfully');
          this.reconnectAttempts = 0;
          resolve(true);
        });

        this.client.on('error', (error: any) => {
          console.error('[MQTT] Connection error:', error);
          if (this.reconnectAttempts++ >= this.maxReconnectAttempts) {
            reject(error);
          }
        });

        this.client.on('message', (topic: string, message: Buffer) => {
          this.handleMessage(topic, message);
        });

        this.client.on('offline', () => {
          console.warn('[MQTT] Client offline');
        });

        this.client.on('reconnect', () => {
          console.log('[MQTT] Attempting to reconnect...');
        });
      });
    } catch (error) {
      console.error('[MQTT] Failed to connect:', error);
      return false;
    }
  }

  /**
   * Subscribe to MQTT topic(s)
   */
  subscribe(topics: string | string[], callback: MessageCallback): void {
    if (!this.client) {
      console.error('[MQTT] Cannot subscribe: not connected');
      return;
    }

    const topicList = Array.isArray(topics) ? topics : [topics];

    topicList.forEach((topic) => {
      // Store callback
      if (!this.callbacks.has(topic)) {
        this.callbacks.set(topic, new Set());
      }
      this.callbacks.get(topic)!.add(callback);

      // Subscribe to MQTT topic
      this.client!.subscribe(topic, (err: any) => {
        if (err) {
          console.error(`[MQTT] Failed to subscribe to ${topic}:`, err);
        } else {
          console.log(`[MQTT] Subscribed to ${topic}`);
        }
      });
    });
  }

  /**
   * Unsubscribe from topic(s)
   */
  unsubscribe(topics: string | string[], callback?: MessageCallback): void {
    if (!this.client) return;

    const topicList = Array.isArray(topics) ? topics : [topics];

    topicList.forEach((topic) => {
      if (callback) {
        // Remove specific callback
        this.callbacks.get(topic)?.delete(callback);

        // If no more callbacks, unsubscribe from MQTT
        if (this.callbacks.get(topic)?.size === 0) {
          this.client!.unsubscribe(topic);
          this.callbacks.delete(topic);
        }
      } else {
        // Remove all callbacks for this topic
        this.client!.unsubscribe(topic);
        this.callbacks.delete(topic);
      }
    });
  }

  /**
   * Publish message to MQTT topic
   */
  publish(topic: string, message: any, options?: Record<string, any>): void {
    if (!this.client) {
      console.error('[MQTT] Cannot publish: not connected');
      return;
    }

    const payload = typeof message === 'string' ? message : JSON.stringify(message);

    this.client.publish(topic, payload, options || {}, (err: any) => {
      if (err) {
        console.error(`[MQTT] Failed to publish to ${topic}:`, err);
      } else {
        console.log(`[MQTT] Published to ${topic}:`, message);
      }
    });
  }

  /**
   * Handle incoming MQTT messages
   */
  private handleMessage(topic: string, message: Buffer): void {
    try {
      // Parse message
      let payload: any;
      try {
        payload = JSON.parse(message.toString());
      } catch {
        payload = message.toString();
      }

      const mqttMessage: MQTTMessage = {
        topic,
        payload,
        timestamp: Date.now(),
      };

      // Call all matching callbacks
      this.callbacks.forEach((callbackSet, subscribedTopic) => {
        // Support wildcard matching (# and +)
        if (this.topicMatches(topic, subscribedTopic)) {
          callbackSet.forEach((callback) => callback(mqttMessage));
        }
      });
    } catch (error) {
      console.error('[MQTT] Error handling message:', error);
    }
  }

  /**
   * Check if topic matches subscription pattern
   */
  private topicMatches(topic: string, pattern: string): boolean {
    if (topic === pattern) return true;

    const topicParts = topic.split('/');
    const patternParts = pattern.split('/');

    if (patternParts.includes('#')) {
      // Multi-level wildcard
      const hashIndex = patternParts.indexOf('#');
      return topicParts.slice(0, hashIndex).every((part, i) => part === patternParts[i]);
    }

    if (patternParts.length !== topicParts.length) return false;

    return patternParts.every((part, i) => {
      return part === '+' || part === topicParts[i];
    });
  }

  /**
   * Disconnect from MQTT broker
   */
  disconnect(): void {
    if (this.client) {
      console.log('[MQTT] Disconnecting...');
      this.client.end();
      this.client = null;
      this.callbacks.clear();
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.client?.connected || false;
  }
}

// Singleton instance for global use
let globalBridge: MQTTBridge | null = null;

export function getMQTTBridge(): MQTTBridge {
  if (!globalBridge) {
    const brokerUrl = process.env.NEXT_PUBLIC_MQTT_WS_URL || 'ws://localhost:9001';
    globalBridge = new MQTTBridge(brokerUrl);
  }
  return globalBridge;
}
