'use client';

import { useState, useEffect, useRef } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { useBrain } from '@/contexts/BrainContext';

export default function LiveActivity() {
  const { transcripts, isConnected, sendMessage, clearTranscripts } = useBrain();
  const [input, setInput] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastAutoScrollMsRef = useRef(0);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  useEffect(() => {
    const now = Date.now();
    if (now - lastAutoScrollMsRef.current < 120) return;
    lastAutoScrollMsRef.current = now;
    scrollToBottom();
  }, [transcripts]);

  const handleSend = () => {
    if (!input.trim()) return;
    if (!isConnected) {
      alert('Not connected to MQTT broker. Please check your connection.');
      return;
    }

    sendMessage(input);
    setInput('');
    setIsWaiting(true);

    // Reset waiting state after a timeout
    setTimeout(() => setIsWaiting(false), 30000); // 30 second timeout
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Detect when we get a response
  useEffect(() => {
    if (transcripts.length > 0) {
      const lastMessage = transcripts[transcripts.length - 1];
      if (lastMessage.type === 'assistant') {
        setIsWaiting(false);
      }
    }
  }, [transcripts]);

  return (
    <div className="p-2 md:p-6 max-w-none md:max-w-5xl mx-auto h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Live Chat</h1>
        <p className="text-gray-400">
          <span className="hidden md:inline">Direct conversation with Sage&apos;s brain</span>
          <span className="md:hidden">Chat with Sage</span>
          {!isConnected && (
            <span className="text-yellow-500 ml-2">⚠️ Not connected to MQTT</span>
          )}
        </p>
      </div>

      {/* Chat Container */}
      <div className="card flex-1 flex flex-col min-h-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto mb-4 space-y-4">
          {transcripts.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-gray-500">
                <div className="text-6xl mb-4">💬</div>
                <div className="text-lg">No messages yet</div>
                <div className="text-sm mt-2">Start a conversation with Sage</div>
              </div>
            </div>
          ) : (
            <>
              {transcripts.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] md:max-w-[70%] rounded-lg px-3 py-2 md:px-4 md:py-3 ${msg.type === 'user'
                        ? 'bg-architect-accent text-white'
                        : msg.type === 'assistant'
                          ? 'bg-architect-gray text-gray-200'
                          : 'bg-yellow-500/10 text-yellow-300'
                      }`}
                  >
                    <div className="text-sm mb-1">
                      {msg.type === 'user' ? (
                        <span className="font-semibold">You</span>
                      ) : msg.type === 'assistant' ? (
                        <span className="font-semibold text-architect-accent">Sage</span>
                      ) : (
                        <span className="font-semibold text-yellow-400">System</span>
                      )}
                      <span className="text-xs ml-2 opacity-70">{msg.timestamp}</span>
                    </div>
                    <div className="whitespace-pre-wrap">{msg.message}</div>
                  </div>
                </div>
              ))}
              {isWaiting && (
                <div className="flex justify-start">
                  <div className="bg-architect-gray text-gray-200 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-architect-accent rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-architect-accent rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-architect-accent rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-architect-border pt-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isConnected ? "Type a message..." : "Not connected to MQTT..."}
              className="flex-1 bg-architect-gray border border-architect-border rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-architect-accent"
              disabled={isWaiting || !isConnected}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isWaiting || !isConnected}
              className="btn-primary px-6 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send size={18} />
              <span className="hidden md:inline">Send</span>
            </button>
            <button
              onClick={clearTranscripts}
              className="btn-secondary px-4"
              title="Clear chat"
            >
              <Trash2 size={18} />
            </button>
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}
