"""
The Architect's Memory (ChromaDB)
Implements 'Cognitive Zone' mapping and persistent vector storage.
"""
import os
import hashlib
from typing import List, Dict, Any

MEMORY_IMPORT_ERROR = None
try:
    import chromadb
    from chromadb.utils import embedding_functions
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError as exc:  # pragma: no cover - optional dependency fallback
    chromadb = None
    embedding_functions = None
    RecursiveCharacterTextSplitter = None
    MEMORY_IMPORT_ERROR = exc

from architect.manifest import ProjectManifest

class ArchitectMemory:
    def __init__(self, persist_path=".sage_memory"):
        if chromadb is None or embedding_functions is None or RecursiveCharacterTextSplitter is None:
            raise RuntimeError(
                "Architect memory dependencies are missing. "
                "Install with: pip install chromadb sentence-transformers langchain-text-splitters"
            ) from MEMORY_IMPORT_ERROR

        print(f"[Memory] Initializing ChromaDB at {persist_path}...")
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # Use a local, efficient embedding model
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Splitter for code and text
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\nclass ", "\ndef ", "\n\n", "\n", " ", ""]
        )

    def _get_collection(self, project_id):
        """Get or create a collection for a specific project."""
        return self.client.get_or_create_collection(
            name=project_id,
            embedding_function=self.embed_fn
        )

    @staticmethod
    def _normalize_source(path: str) -> str:
        return os.path.normpath(path).replace("\\", "/")

    def _resolve_paths(self, manifest: ProjectManifest, file_path: str):
        """
        Resolve absolute file path for reading and relative source path for metadata.
        """
        repo_root = os.path.abspath(manifest.repo_path)

        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.abspath(os.path.join(repo_root, file_path))
            if not os.path.exists(abs_path):
                abs_path = os.path.abspath(file_path)

        rel_source = None
        try:
            rel = os.path.relpath(abs_path, start=repo_root)
            if not rel.startswith(".."):
                rel_source = rel
        except Exception:
            rel_source = None

        if not rel_source:
            rel_source = file_path

        return abs_path, self._normalize_source(rel_source)

    def ingest(self, manifest: ProjectManifest, file_path: str):
        """
        Ingest a file using rules from the Project Manifest.
        """
        abs_path, source = self._resolve_paths(manifest, file_path)

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"[Memory] Failed to read {abs_path}: {e}")
            return

        # 1. Determine Zone (Dynamic)
        zone = manifest.get_zone_for_file(source)
        if not zone:
            # Strict-by-default: skip files outside declared cognitive zones.
            return

        zone_name = zone.name
        role = zone.role

        print(f"[Memory] Ingesting {source} -> {zone_name} ({role})")

        # 2. Split Content
        chunks = self.splitter.split_text(content)
        
        if not chunks:
            return

        collection = self._get_collection(manifest.id)

        # Remove prior chunks for this source to avoid duplicate growth across re-ingestion.
        # We delete by both normalized relative and absolute forms for backward compatibility.
        for old_source in {
            source,
            self._normalize_source(file_path),
            self._normalize_source(abs_path),
        }:
            try:
                collection.delete(where={"source": old_source})
            except Exception:
                pass

        # 3. Prepare ChromaDB Payload
        source_hash = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
        ids = [f"{manifest.id}:{source_hash}:{i}" for i in range(len(chunks))]
        metadatas = []
        for i, chunk in enumerate(chunks):
            meta = {
                "source": source,
                "project_id": manifest.id,
                "zone_name": zone_name,
                "role": role,
                "chunk_index": i
            }
            metadatas.append(meta)

        # 4. Upsert
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )

    def query(self, project_id: str, query_text: str, n_results=5, zone_filter=None):
        """
        Recall context. Optionally filter by Cognitive Zone.
        """
        collection = self._get_collection(project_id)
        
        where_clause = {}
        if zone_filter:
            where_clause["zone_name"] = zone_filter

        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_clause if zone_filter else None
        )
        
        return results
