"""
Memory/ChromaDB MCP Client.
Provides unified semantic memory access for both Architect and Brain.
Wraps ChromaDB for vector storage and retrieval.
"""
import chromadb
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import hashlib


class MemoryMCPClient:
    """
    Client for semantic memory operations using ChromaDB.
    Can be used by both Architect and Brain for memory management.
    """

    def __init__(
        self,
        persist_directory: str = ".sage_memory",
        client_type: str = "persistent"
    ):
        """
        Initialize memory client.

        Args:
            persist_directory: Directory for ChromaDB persistence
            client_type: "persistent" or "ephemeral"
        """
        self.persist_directory = persist_directory

        if client_type == "persistent":
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()

    def _generate_id(self, text: str, metadata: Dict[str, Any]) -> str:
        """Generate unique ID for memory."""
        content = f"{text}_{metadata.get('timestamp', '')}_{metadata.get('type', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def remember(
        self,
        text: str,
        collection_name: str = "sage_memories",
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a memory.

        Args:
            text: Memory text
            collection_name: Collection to store in
            metadata: Optional metadata
            id: Optional custom ID

        Returns:
            Dict with storage result
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": f"Memories for {collection_name}"}
            )

            # Add timestamp if not present
            if metadata is None:
                metadata = {}
            if "timestamp" not in metadata:
                metadata["timestamp"] = datetime.now().isoformat()

            # Generate ID if not provided
            if id is None:
                id = self._generate_id(text, metadata)

            collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[id]
            )

            return {
                "success": True,
                "id": id,
                "collection": collection_name,
                "text": text,
                "metadata": metadata
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to remember: {str(e)}"
            }

    async def recall(
        self,
        query: str,
        collection_name: str = "sage_memories",
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Semantic search for memories.

        Args:
            query: Search query
            collection_name: Collection to search
            n_results: Number of results
            where: Metadata filters
            where_document: Document content filters

        Returns:
            Dict with search results
        """
        try:
            collection = self.client.get_or_create_collection(name=collection_name)

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                where_document=where_document
            )

            memories = []
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    memories.append({
                        "id": results['ids'][0][i],
                        "text": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })

            return {
                "success": True,
                "query": query,
                "collection": collection_name,
                "memories": memories,
                "count": len(memories)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to recall: {str(e)}"
            }

    async def forget(
        self,
        ids: List[str],
        collection_name: str = "sage_memories"
    ) -> Dict[str, Any]:
        """
        Delete memories by ID.

        Args:
            ids: List of memory IDs
            collection_name: Collection name

        Returns:
            Dict with deletion result
        """
        try:
            collection = self.client.get_or_create_collection(name=collection_name)
            collection.delete(ids=ids)

            return {
                "success": True,
                "collection": collection_name,
                "deleted_ids": ids,
                "count": len(ids)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to forget: {str(e)}"
            }

    async def update_memory(
        self,
        id: str,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: str = "sage_memories"
    ) -> Dict[str, Any]:
        """
        Update existing memory.

        Args:
            id: Memory ID
            text: New text (optional)
            metadata: New metadata (optional)
            collection_name: Collection name

        Returns:
            Dict with update result
        """
        try:
            collection = self.client.get_or_create_collection(name=collection_name)

            update_params = {"ids": [id]}
            if text is not None:
                update_params["documents"] = [text]
            if metadata is not None:
                update_params["metadatas"] = [metadata]

            collection.update(**update_params)

            return {
                "success": True,
                "id": id,
                "collection": collection_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to update memory: {str(e)}"
            }

    async def get_memory_by_id(
        self,
        id: str,
        collection_name: str = "sage_memories"
    ) -> Dict[str, Any]:
        """
        Get specific memory by ID.

        Args:
            id: Memory ID
            collection_name: Collection name

        Returns:
            Dict with memory
        """
        try:
            collection = self.client.get_or_create_collection(name=collection_name)
            result = collection.get(ids=[id])

            if result['ids']:
                return {
                    "success": True,
                    "memory": {
                        "id": result['ids'][0],
                        "text": result['documents'][0],
                        "metadata": result['metadatas'][0] if result['metadatas'] else {}
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Memory not found: {id}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get memory: {str(e)}"
            }

    async def list_collections(self) -> Dict[str, Any]:
        """
        List all memory collections.

        Returns:
            Dict with collections
        """
        try:
            collections = self.client.list_collections()

            return {
                "success": True,
                "collections": [
                    {
                        "name": c.name,
                        "metadata": c.metadata,
                        "count": c.count()
                    }
                    for c in collections
                ]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list collections: {str(e)}"
            }

    async def create_collection(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new memory collection.

        Args:
            name: Collection name
            metadata: Optional metadata

        Returns:
            Dict with creation result
        """
        try:
            collection = self.client.create_collection(
                name=name,
                metadata=metadata or {}
            )

            return {
                "success": True,
                "name": name,
                "metadata": collection.metadata
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create collection: {str(e)}"
            }

    async def delete_collection(self, name: str) -> Dict[str, Any]:
        """
        Delete memory collection.

        Args:
            name: Collection name

        Returns:
            Dict with deletion result
        """
        try:
            self.client.delete_collection(name=name)

            return {
                "success": True,
                "name": name,
                "deleted": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete collection: {str(e)}"
            }

    async def get_collection_stats(self, name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            name: Collection name

        Returns:
            Dict with stats
        """
        try:
            collection = self.client.get_collection(name=name)
            count = collection.count()

            # Get sample memories
            sample = collection.peek(limit=5)

            return {
                "success": True,
                "name": name,
                "count": count,
                "metadata": collection.metadata,
                "sample": [
                    {
                        "id": sample['ids'][i],
                        "text": sample['documents'][i][:100] + "..." if len(sample['documents'][i]) > 100 else sample['documents'][i]
                    }
                    for i in range(len(sample['ids']))
                ]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get stats: {str(e)}"
            }

    # Convenience methods for Sage system

    async def remember_episode(
        self,
        text: str,
        room: str,
        duration_minutes: Optional[int] = None,
        patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Remember a Brain episode.

        Args:
            text: Episode description
            room: Room name
            duration_minutes: Episode duration
            patterns: Detected patterns

        Returns:
            Dict with storage result
        """
        metadata = {
            "type": "episode",
            "room": room,
            "timestamp": datetime.now().isoformat()
        }

        if duration_minutes:
            metadata["duration_minutes"] = duration_minutes
        if patterns:
            metadata["patterns"] = patterns

        return await self.remember(
            text=text,
            collection_name="sage_episodes",
            metadata=metadata
        )

    async def remember_fact(
        self,
        text: str,
        category: str = "general",
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Remember a fact about the user.

        Args:
            text: Fact text
            category: Fact category
            confidence: Confidence level (0-1)

        Returns:
            Dict with storage result
        """
        metadata = {
            "type": "fact",
            "category": category,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }

        return await self.remember(
            text=text,
            collection_name="sage_facts",
            metadata=metadata
        )

    async def remember_preference(
        self,
        preference: str,
        value: Any,
        category: str = "general"
    ) -> Dict[str, Any]:
        """
        Remember user preference.

        Args:
            preference: Preference name
            value: Preference value
            category: Category

        Returns:
            Dict with storage result
        """
        text = f"{preference}: {value}"
        metadata = {
            "type": "preference",
            "preference": preference,
            "value": str(value),
            "category": category,
            "timestamp": datetime.now().isoformat()
        }

        return await self.remember(
            text=text,
            collection_name="sage_preferences",
            metadata=metadata
        )

    async def recall_recent_episodes(
        self,
        room: Optional[str] = None,
        hours_ago: int = 24,
        n_results: int = 10
    ) -> Dict[str, Any]:
        """
        Recall recent episodes.

        Args:
            room: Optional room filter
            hours_ago: Time range
            n_results: Number of results

        Returns:
            Dict with episodes
        """
        where = {"type": "episode"}
        if room:
            where["room"] = room

        # Calculate timestamp threshold
        threshold = (datetime.now() - timedelta(hours=hours_ago)).isoformat()

        return await self.recall(
            query=f"Recent activity in last {hours_ago} hours",
            collection_name="sage_episodes",
            n_results=n_results,
            where=where
        )

    async def recall_facts_about(
        self,
        topic: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        Recall facts about a topic.

        Args:
            topic: Topic to search
            n_results: Number of results

        Returns:
            Dict with facts
        """
        return await self.recall(
            query=topic,
            collection_name="sage_facts",
            n_results=n_results,
            where={"type": "fact"}
        )

    async def get_preference(self, preference: str) -> Dict[str, Any]:
        """
        Get specific user preference.

        Args:
            preference: Preference name

        Returns:
            Dict with preference value
        """
        result = await self.recall(
            query=preference,
            collection_name="sage_preferences",
            n_results=1,
            where={"type": "preference", "preference": preference}
        )

        if result["success"] and result["memories"]:
            return {
                "success": True,
                "preference": preference,
                "value": result["memories"][0]["metadata"].get("value"),
                "memory": result["memories"][0]
            }
        else:
            return {
                "success": False,
                "error": f"Preference not found: {preference}"
            }

    async def remember_conversation(
        self,
        messages: List[Dict[str, str]],
        summary: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Remember a conversation.

        Args:
            messages: List of message dicts
            summary: Conversation summary
            context: Optional context

        Returns:
            Dict with storage result
        """
        # Store full conversation
        text = summary
        metadata = {
            "type": "conversation",
            "message_count": len(messages),
            "timestamp": datetime.now().isoformat()
        }

        if context:
            metadata.update(context)

        return await self.remember(
            text=text,
            collection_name="sage_conversations",
            metadata=metadata
        )

    async def architect_remember_code(
        self,
        code: str,
        file_path: str,
        project_id: str,
        purpose: str
    ) -> Dict[str, Any]:
        """
        Remember generated code for future reference.

        Args:
            code: Code content
            file_path: File path
            project_id: Project ID
            purpose: Code purpose

        Returns:
            Dict with storage result
        """
        text = f"File: {file_path}\n\nPurpose: {purpose}\n\n{code[:500]}"
        metadata = {
            "type": "generated_code",
            "file_path": file_path,
            "project_id": project_id,
            "purpose": purpose,
            "timestamp": datetime.now().isoformat()
        }

        return await self.remember(
            text=text,
            collection_name="sage_architect_code",
            metadata=metadata
        )

    async def architect_recall_similar_code(
        self,
        purpose: str,
        project_id: Optional[str] = None,
        n_results: int = 3
    ) -> Dict[str, Any]:
        """
        Find similar previously generated code.

        Args:
            purpose: Code purpose to search
            project_id: Optional project filter
            n_results: Number of results

        Returns:
            Dict with similar code
        """
        where = {"type": "generated_code"}
        if project_id:
            where["project_id"] = project_id

        return await self.recall(
            query=purpose,
            collection_name="sage_architect_code",
            n_results=n_results,
            where=where
        )
