"""
Streaming Text-to-Speech Pipeline
Accumulates LLM tokens and triggers TTS on sentence boundaries for low-latency response.

Usage:
    streamer = TTSStreamer(mqtt_client)
    
    # As LLM tokens arrive:
    await streamer.feed("Hello")
    await streamer.feed(" there!")
    await streamer.feed(" How are you?")
    
    # When LLM is done:
    await streamer.flush()
"""

import re
import asyncio
import json
import logging
import os
from typing import Optional
import paho.mqtt.client as mqtt

logger = logging.getLogger("TTSStreamer")

# Sentence boundary patterns
SENTENCE_ENDS = re.compile(r'[.!?]\s*$')
SENTENCE_ENDS_MID = re.compile(r'[.!?]\s+')

# Minimum characters before we'll send to TTS (avoids tiny fragments)
MIN_CHUNK_SIZE = int(os.getenv("TTS_STREAM_MIN_CHARS", "14"))


class TTSStreamer:
    """
    Accumulates streaming LLM output and sends complete sentences to TTS.
    Reduces perceived latency by speaking as soon as possible.
    """
    
    def __init__(self, mqtt_client: mqtt.Client, topic: str = "sage/voice/response"):
        self.mqtt_client = mqtt_client
        self.topic = topic
        self.buffer = ""
        self.sent_chunks = []
        self.min_chunk_size = MIN_CHUNK_SIZE
        
    def reset(self):
        """Reset the streamer for a new response."""
        self.buffer = ""
        self.sent_chunks = []
        
    async def feed(self, token: str):
        """
        Feed a token from the LLM.
        Will automatically send complete sentences to TTS.
        """
        if not token:
            return
            
        self.buffer += token
        
        # Check for sentence boundaries
        await self._try_send_sentences()
        
    async def _try_send_sentences(self):
        """Check if we have complete sentences to send."""
        # Look for sentence-ending punctuation followed by space or end
        match = SENTENCE_ENDS_MID.search(self.buffer)
        
        if match and match.end() >= self.min_chunk_size:
            # We have at least one complete sentence
            sentence = self.buffer[:match.end()].strip()
            self.buffer = self.buffer[match.end():]
            
            if sentence:
                await self._send_to_tts(sentence)
                
    async def flush(self):
        """
        Flush any remaining text to TTS.
        Call this when the LLM response is complete.
        """
        if self.buffer.strip():
            await self._send_to_tts(self.buffer.strip())
        self.buffer = ""
        
    async def _send_to_tts(self, text: str):
        """Send text chunk to TTS via MQTT."""
        if not text:
            return
            
        self.sent_chunks.append(text)
        
        payload = json.dumps({
            "text": text,
            "stream": True,  # Indicate this is part of a stream
            "chunk_index": len(self.sent_chunks) - 1
        })
        
        logger.debug(f"Sending to TTS: '{text[:50]}...'")
        self.mqtt_client.publish(self.topic, payload)
        
    def get_full_response(self) -> str:
        """Get the complete response text that was sent."""
        return " ".join(self.sent_chunks)


class SentenceBuffer:
    """
    Simple sentence accumulator for use with async generators.
    Yields complete sentences as they become available.
    """
    
    def __init__(self, min_chunk_size: int = MIN_CHUNK_SIZE):
        self.buffer = ""
        self.min_chunk_size = min_chunk_size
        
    def add(self, token: str) -> Optional[str]:
        """
        Add a token and return a complete sentence if available.
        Returns None if no complete sentence yet.
        """
        if not token:
            return None
            
        self.buffer += token
        
        # Check for sentence boundary
        match = SENTENCE_ENDS_MID.search(self.buffer)
        
        if match and match.end() >= self.min_chunk_size:
            sentence = self.buffer[:match.end()].strip()
            self.buffer = self.buffer[match.end():]
            return sentence
            
        return None
        
    def flush(self) -> Optional[str]:
        """Get any remaining text in the buffer."""
        if self.buffer.strip():
            result = self.buffer.strip()
            self.buffer = ""
            return result
        return None
