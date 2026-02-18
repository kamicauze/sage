"""
Sage Memory - Persistent Vector Storage
Stores episodic memories, learned facts, and user preferences using ChromaDB.

Three collections:
- sage_episodes: Conversation summaries (what happened)
- sage_facts: Learned information about the user (what I know)
- sage_preferences: Communication preferences (how to interact)
"""

import os
import sys
import uuid
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions


# Memory storage path (same as Architect for shared embeddings)
MEMORY_PATH = os.getenv("SAGE_MEMORY_PATH", ".sage_memory")

# Collection names
COLLECTION_EPISODES = "sage_episodes"
COLLECTION_FACTS = "sage_facts"
COLLECTION_PREFERENCES = "sage_preferences"


class SageMemory:
    """
    Persistent memory for Sage's personal knowledge.
    
    Uses ChromaDB with sentence-transformers embeddings for semantic search.
    Stores:
    - Episodic memories: Summaries of past conversations
    - Facts: Learned information about the user
    - Preferences: Communication style preferences
    """
    
    def __init__(self, persist_path: str = MEMORY_PATH, preload_embeddings: bool = True):
        import time as time_module
        init_start = time_module.time()
        print(f"[Memory] Initializing Sage Memory at {persist_path}...")

        self.persist_path = persist_path

        t0 = time_module.time()
        self.client = chromadb.PersistentClient(path=persist_path)
        print(f"[Memory] ChromaDB client init: {int((time_module.time() - t0) * 1000)}ms")

        # Use same embedding model as Architect for consistency
        t1 = time_module.time()
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        print(f"[Memory] Embedding function init: {int((time_module.time() - t1) * 1000)}ms")

        # Preload the embedding model to avoid first-query latency
        if preload_embeddings:
            print("[Memory] Preloading sentence-transformer model...")
            t2 = time_module.time()
            try:
                # Trigger model loading by encoding a dummy text
                _ = self.embed_fn(["warmup"])
                print(f"[Memory] ✓ Embedding model preloaded in {int((time_module.time() - t2) * 1000)}ms")
            except Exception as e:
                print(f"[Memory] Warning: Failed to preload embeddings: {e}")

        # Initialize collections
        t3 = time_module.time()
        self.episodes = self._get_collection(COLLECTION_EPISODES)
        self.facts = self._get_collection(COLLECTION_FACTS)
        self.preferences = self._get_collection(COLLECTION_PREFERENCES)
        print(f"[Memory] Collections loaded: {int((time_module.time() - t3) * 1000)}ms")

        total_time = int((time_module.time() - init_start) * 1000)
        print(f"[Memory] Loaded: {self.episodes.count()} episodes, "
              f"{self.facts.count()} facts, {self.preferences.count()} preferences (total: {total_time}ms)")
    
    def _get_collection(self, name: str):
        """Get or create a collection."""
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embed_fn
        )
    
    # ==================== EPISODIC MEMORY ====================
    
    def remember_conversation(
        self,
        summary: str,
        emotional_arc: str = None,
        topics: List[str] = None,
        outcome: str = None,
        user_mood_start: str = None,
        user_mood_end: str = None,
        duration_min: float = None,
        turn_count: int = None
    ) -> str:
        """
        Store a conversation summary as an episodic memory.
        
        Args:
            summary: Natural language summary of what happened
            emotional_arc: e.g., "stressed -> calmer"
            topics: List of topics discussed
            outcome: What was the result (suggestion followed, etc.)
            user_mood_start: Detected mood at start
            user_mood_end: Detected mood at end
            duration_min: How long the conversation lasted
            turn_count: Number of exchanges
            
        Returns:
            ID of the stored memory
        """
        memory_id = f"ep_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        now = datetime.now()
        metadata = {
            "type": "episode",
            "timestamp": time.time(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "day_of_week": now.strftime("%A"),
            "hour": now.hour,
            "emotional_arc": emotional_arc or "",
            "topics": ",".join(topics) if topics else "",
            "outcome": outcome or "",
            "user_mood_start": user_mood_start or "",
            "user_mood_end": user_mood_end or "",
            "duration_min": duration_min or 0,
            "turn_count": turn_count or 0
        }
        
        self.episodes.add(
            ids=[memory_id],
            documents=[summary],
            metadatas=[metadata]
        )
        
        print(f"[Memory] Stored episode: {summary[:50]}...")
        return memory_id
    
    def recall_episodes(
        self,
        query: str,
        n_results: int = 5,
        time_filter: Dict = None
    ) -> List[Dict]:
        """
        Recall episodic memories relevant to a query.
        
        Args:
            query: Search query (semantic search)
            n_results: Max results to return
            time_filter: Optional filter like {"hour": 2} for late-night memories
            
        Returns:
            List of memory dicts with content and metadata
        """
        where_filter = None
        if time_filter:
            where_filter = time_filter
            
        results = self.episodes.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        return self._format_results(results)
    
    # ==================== SEMANTIC MEMORY (FACTS) ====================
    
    def learn_fact(
        self,
        fact: str,
        category: str = "general",
        source: str = "conversation",
        confidence: float = 0.8
    ) -> str:
        """
        Store a learned fact about the user.
        
        Args:
            fact: The fact to remember (e.g., "User has a cat named Luna")
            category: Category like "personal", "work", "preferences", "health"
            source: Where this was learned from
            confidence: How confident we are (0-1)
            
        Returns:
            ID of the stored fact
        """
        fact_id = f"fact_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        metadata = {
            "type": "fact",
            "category": category,
            "source": source,
            "confidence": confidence,
            "timestamp": time.time(),
            "date_learned": datetime.now().strftime("%Y-%m-%d"),
            "times_referenced": 0,
            "last_referenced": 0
        }
        
        # Check for similar existing facts to avoid duplicates
        existing = self.facts.query(
            query_texts=[fact],
            n_results=1
        )
        
        if existing['distances'] and existing['distances'][0]:
            # If very similar fact exists (distance < 0.3), update instead
            if existing['distances'][0][0] < 0.3:
                existing_id = existing['ids'][0][0]
                existing_meta = existing['metadatas'][0][0]
                # Update confidence if new source
                new_confidence = min(1.0, existing_meta.get('confidence', 0.5) + 0.1)
                self.facts.update(
                    ids=[existing_id],
                    metadatas=[{**existing_meta, "confidence": new_confidence}]
                )
                print(f"[Memory] Updated existing fact (confidence: {new_confidence})")
                return existing_id
        
        self.facts.add(
            ids=[fact_id],
            documents=[fact],
            metadatas=[metadata]
        )
        
        print(f"[Memory] Learned fact: {fact}")
        return fact_id
    
    def recall_facts(
        self,
        query: str = None,
        category: str = None,
        n_results: int = 10,
        min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Recall facts about the user.
        
        Args:
            query: Optional semantic search query
            category: Filter by category
            n_results: Max results
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of fact dicts
        """
        # ChromaDB requires $and for multiple conditions
        conditions = [{"confidence": {"$gte": min_confidence}}]
        if category:
            conditions.append({"category": category})

        # Use $and wrapper if multiple conditions, otherwise single condition
        if len(conditions) > 1:
            where_filter = {"$and": conditions}
        else:
            where_filter = conditions[0]

        if query:
            results = self.facts.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
        else:
            # Get all facts above confidence threshold
            results = self.facts.get(
                where=where_filter,
                limit=n_results
            )
            # Reformat to match query results
            results = {
                'ids': [results['ids']] if results['ids'] else [[]],
                'documents': [results['documents']] if results['documents'] else [[]],
                'metadatas': [results['metadatas']] if results['metadatas'] else [[]]
            }
        
        return self._format_results(results)
    
    def get_all_facts(self) -> List[Dict]:
        """Get all stored facts."""
        results = self.facts.get()
        if not results['ids']:
            return []
        return [
            {
                "id": results['ids'][i],
                "content": results['documents'][i],
                "metadata": results['metadatas'][i]
            }
            for i in range(len(results['ids']))
        ]
    
    # ==================== PREFERENCE MEMORY ====================
    
    def update_preference(
        self,
        pref_type: str,
        value: str,
        signal: str = "explicit",
        strength: float = 0.5
    ) -> str:
        """
        Store or update a user preference.
        
        Args:
            pref_type: Type like "communication_style", "humor", "language"
            value: The preference value (e.g., "prefers Sheng", "likes humor")
            signal: How we learned this ("explicit", "implicit_positive", "implicit_negative")
            strength: How strong the preference is (0-1)
            
        Returns:
            ID of the preference
        """
        pref_id = f"pref_{pref_type}_{uuid.uuid4().hex[:8]}"
        
        # Check for existing preference of same type
        existing = self.preferences.get(
            where={"pref_type": pref_type}
        )
        
        if existing['ids']:
            # Update existing preference
            existing_id = existing['ids'][0]
            existing_meta = existing['metadatas'][0]
            
            # Adjust strength based on signal
            old_strength = existing_meta.get('strength', 0.5)
            if signal == "explicit":
                new_strength = strength  # Explicit overrides
            elif signal == "implicit_positive":
                new_strength = min(1.0, old_strength + 0.1)
            elif signal == "implicit_negative":
                new_strength = max(0.0, old_strength - 0.15)
            else:
                new_strength = old_strength
            
            self.preferences.update(
                ids=[existing_id],
                documents=[value],
                metadatas=[{
                    **existing_meta,
                    "value": value,
                    "strength": new_strength,
                    "last_signal": signal,
                    "last_updated": time.time()
                }]
            )
            print(f"[Memory] Updated preference: {pref_type} = {value} (strength: {new_strength})")
            return existing_id
        
        # Create new preference
        metadata = {
            "type": "preference",
            "pref_type": pref_type,
            "value": value,
            "strength": strength,
            "signal": signal,
            "timestamp": time.time(),
            "last_updated": time.time()
        }
        
        self.preferences.add(
            ids=[pref_id],
            documents=[value],
            metadatas=[metadata]
        )
        
        print(f"[Memory] Stored preference: {pref_type} = {value}")
        return pref_id
    
    def get_preferences(self, pref_type: str = None) -> List[Dict]:
        """
        Get user preferences.
        
        Args:
            pref_type: Optional filter by type
            
        Returns:
            List of preference dicts
        """
        where_filter = None
        if pref_type:
            where_filter = {"pref_type": pref_type}
        
        results = self.preferences.get(where=where_filter)
        
        if not results['ids']:
            return []
            
        return [
            {
                "id": results['ids'][i],
                "content": results['documents'][i],
                "metadata": results['metadatas'][i]
            }
            for i in range(len(results['ids']))
        ]
    
    # ==================== UTILITIES ====================
    
    def _format_results(self, results: Dict) -> List[Dict]:
        """Format ChromaDB results into list of dicts."""
        if not results['ids'] or not results['ids'][0]:
            return []
        
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results.get('distances', [[]])[0][i] if results.get('distances') else None
            })
        
        return formatted
    
    def get_stats(self) -> Dict:
        """Get memory statistics."""
        return {
            "episodes": self.episodes.count(),
            "facts": self.facts.count(),
            "preferences": self.preferences.count(),
            "path": self.persist_path
        }
    
    def clear_all(self):
        """Clear all memories (use with caution!)."""
        self.client.delete_collection(COLLECTION_EPISODES)
        self.client.delete_collection(COLLECTION_FACTS)
        self.client.delete_collection(COLLECTION_PREFERENCES)
        
        # Recreate empty collections
        self.episodes = self._get_collection(COLLECTION_EPISODES)
        self.facts = self._get_collection(COLLECTION_FACTS)
        self.preferences = self._get_collection(COLLECTION_PREFERENCES)
        
        print("[Memory] All memories cleared")
    
    def clear_episodes(self):
        """Clear only episodic memories."""
        self.client.delete_collection(COLLECTION_EPISODES)
        self.episodes = self._get_collection(COLLECTION_EPISODES)
        print("[Memory] Episodes cleared")


# Singleton instance
_memory: Optional[SageMemory] = None

# Prevent duplicate module singletons when imported as brain.memory.* vs memory.*
_CANONICAL_MODULE = "brain.memory.sage_memory"
_ALIAS_MODULE = "memory.sage_memory"
if __name__ == _CANONICAL_MODULE:
    sys.modules.setdefault(_ALIAS_MODULE, sys.modules[__name__])
elif __name__ == _ALIAS_MODULE:
    sys.modules.setdefault(_CANONICAL_MODULE, sys.modules[__name__])


def get_memory() -> SageMemory:
    """Get the shared memory instance."""
    global _memory
    if _memory is None:
        _memory = SageMemory()
        print(f"[Memory] get_memory: pid={os.getpid()} id={id(_memory)} reused=False")
    else:
        print(f"[Memory] get_memory: pid={os.getpid()} id={id(_memory)} reused=True")
    return _memory
