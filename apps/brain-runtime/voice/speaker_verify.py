"""
Speaker Verification Module (Robust Multi-Embedding)
Checks if audio matches ANY of the enrolled owner's voice samples.

Features:
- Multiple voice embeddings for better coverage of voice variability
- Best-match scoring: passes if ANY sample matches above threshold
- Confidence scoring with adjustable sensitivity
- Easy to add new samples over time

Usage:
    from voice.speaker_verify import SpeakerVerifier
    
    verifier = SpeakerVerifier()
    if verifier.is_owner(audio_chunk):
        # Process the audio
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger("SpeakerVerify")

# Paths
VOICE_DIR = Path(__file__).parent
OWNER_EMBEDDING_PATH = VOICE_DIR / "owner_voice.npy"  # Legacy single embedding
OWNER_EMBEDDINGS_DIR = VOICE_DIR / "owner_embeddings"  # New multi-embedding directory
EMBEDDINGS_META_PATH = OWNER_EMBEDDINGS_DIR / "metadata.json"

# Verification settings
# Threshold tuning guide:
#   0.70+ = Very strict (may reject owner in noisy conditions)
#   0.60-0.70 = Balanced (recommended)  
#   0.50-0.60 = Lenient (may accept similar voices)
#   0.50- = Very lenient (low security)
DEFAULT_THRESHOLD = float(os.getenv("SPEAKER_THRESHOLD", "0.55"))  # Lowered for multi-embedding
MIN_AUDIO_LENGTH = 0.5  # Minimum seconds of audio to verify

# Adaptive settings
CONFIDENCE_BOOST_THRESHOLD = 0.70  # If best match is above this, very confident
LOW_CONFIDENCE_THRESHOLD = 0.50    # Below this, definitely not owner


class SpeakerVerifier:
    """
    Robust speaker verifier with multi-embedding support.
    
    Stores multiple voice samples to capture natural voice variability:
    - Different times of day
    - Different moods/energy levels  
    - Different mic positions
    - Different speaking volumes
    """
    
    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self.owner_embeddings: List[np.ndarray] = []
        self.embedding_labels: List[str] = []  # Labels for each embedding (e.g., "morning_sample")
        self.encoder = None
        self.enabled = False
        
        # Stats tracking for debugging
        self.recent_scores: List[float] = []
        self.max_recent_scores = 20
        
        self._load_owner_embeddings()
        
    def _load_owner_embeddings(self):
        """Load all owner voice embeddings."""
        loaded_count = 0
        
        # Load from multi-embedding directory first (preferred)
        if OWNER_EMBEDDINGS_DIR.exists():
            try:
                # Load metadata if exists
                if EMBEDDINGS_META_PATH.exists():
                    with open(EMBEDDINGS_META_PATH) as f:
                        meta = json.load(f)
                        self.embedding_labels = meta.get("labels", [])
                
                # Load all .npy files
                for npy_file in sorted(OWNER_EMBEDDINGS_DIR.glob("embedding_*.npy")):
                    try:
                        embedding = np.load(npy_file)
                        if self._is_valid_embedding(embedding):
                            self.owner_embeddings.append(embedding)
                            loaded_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to load {npy_file}: {e}")
                        
            except Exception as e:
                logger.warning(f"Error loading embeddings directory: {e}")
        
        # Fall back to legacy single embedding
        if loaded_count == 0 and OWNER_EMBEDDING_PATH.exists():
            try:
                embedding = np.load(OWNER_EMBEDDING_PATH)
                if self._is_valid_embedding(embedding):
                    self.owner_embeddings.append(embedding)
                    self.embedding_labels.append("legacy")
                    loaded_count = 1
                    logger.info("📦 Migrated legacy single embedding")
            except Exception as e:
                logger.warning(f"Failed to load legacy embedding: {e}")
        
        if loaded_count > 0:
            self.enabled = True
            logger.info(f"✅ Loaded {loaded_count} owner voiceprint(s) (threshold: {self.threshold})")
        else:
            logger.info("ℹ️  No owner voiceprint found. Speaker verification disabled.")
            logger.info("   Run './sage enroll' to enable voice-only mode.")
            self.enabled = False
    
    def _is_valid_embedding(self, embedding: np.ndarray) -> bool:
        """Check if embedding is valid."""
        if embedding is None or len(embedding) == 0:
            return False
        if np.isnan(embedding).any():
            return False
        # Resemblyzer embeddings are 256-dim normalized vectors
        if len(embedding) != 256:
            return False
        return True
            
    def _load_encoder(self):
        """Lazy load the voice encoder."""
        if self.encoder is None:
            from resemblyzer import VoiceEncoder
            self.encoder = VoiceEncoder()
            logger.debug("Voice encoder loaded")
            
    def is_owner(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        """
        Check if the audio belongs to the owner.
        
        Uses best-match scoring: passes if ANY enrolled embedding
        matches above the threshold.
        
        Args:
            audio: Audio data as float32 numpy array (-1 to 1)
            sample_rate: Sample rate of audio
            
        Returns:
            True if audio matches owner's voice, False otherwise.
            Always returns True if verification is disabled.
        """
        if not self.enabled:
            return True  # No verification = accept all
            
        # Check minimum audio length
        duration = len(audio) / sample_rate
        if duration < MIN_AUDIO_LENGTH:
            logger.debug(f"Audio too short for verification ({duration:.2f}s)")
            return True  # Can't verify short audio, let it through
            
        try:
            similarity, best_idx = self.get_best_similarity(audio, sample_rate)
            
            is_match = similarity >= self.threshold
            
            # Track for debugging
            self.recent_scores.append(similarity)
            if len(self.recent_scores) > self.max_recent_scores:
                self.recent_scores.pop(0)
            
            label = self.embedding_labels[best_idx] if best_idx < len(self.embedding_labels) else f"sample_{best_idx}"
            confidence = "HIGH" if similarity >= CONFIDENCE_BOOST_THRESHOLD else "MED" if similarity >= self.threshold else "LOW"
            
            logger.debug(
                f"Speaker similarity: {similarity:.3f} (best: {label}, threshold: {self.threshold}, "
                f"confidence: {confidence}) -> {'✓ OWNER' if is_match else '✗ NOT OWNER'}"
            )
            
            return is_match
            
        except Exception as e:
            logger.warning(f"Speaker verification error: {e}")
            return True  # On error, let audio through
            
    def get_similarity(self, audio: np.ndarray, sample_rate: int = 16000) -> float:
        """
        Get best similarity score (for compatibility).
        """
        score, _ = self.get_best_similarity(audio, sample_rate)
        return score
    
    def get_best_similarity(self, audio: np.ndarray, sample_rate: int = 16000) -> Tuple[float, int]:
        """
        Get similarity score against all embeddings, return best match.
        
        Returns:
            Tuple of (best_similarity_score, index_of_best_matching_embedding)
        """
        if not self.enabled or not self.owner_embeddings:
            return 1.0, 0
            
        try:
            self._load_encoder()
            from resemblyzer import preprocess_wav
            
            processed = preprocess_wav(audio, source_sr=sample_rate)
            
            if len(processed) < sample_rate * MIN_AUDIO_LENGTH:
                return 1.0, 0  # Too short, assume owner
            
            test_embedding = self.encoder.embed_utterance(processed)
            
            # Compare against all enrolled embeddings
            similarities = []
            for owner_emb in self.owner_embeddings:
                sim = float(np.dot(owner_emb, test_embedding))
                similarities.append(sim)
            
            best_score = max(similarities)
            best_idx = similarities.index(best_score)
            
            return best_score, best_idx
            
        except Exception as e:
            logger.warning(f"Similarity calculation error: {e}")
            return 1.0, 0
    
    def get_all_similarities(self, audio: np.ndarray, sample_rate: int = 16000) -> List[Tuple[str, float]]:
        """
        Get similarity scores against all embeddings.
        Useful for debugging which samples match best.
        
        Returns:
            List of (label, similarity) tuples
        """
        if not self.enabled or not self.owner_embeddings:
            return []
            
        try:
            self._load_encoder()
            from resemblyzer import preprocess_wav
            
            processed = preprocess_wav(audio, source_sr=sample_rate)
            test_embedding = self.encoder.embed_utterance(processed)
            
            results = []
            for i, owner_emb in enumerate(self.owner_embeddings):
                sim = float(np.dot(owner_emb, test_embedding))
                label = self.embedding_labels[i] if i < len(self.embedding_labels) else f"sample_{i}"
                results.append((label, sim))
            
            return sorted(results, key=lambda x: x[1], reverse=True)
            
        except Exception as e:
            logger.warning(f"Error getting all similarities: {e}")
            return []
    
    def add_embedding(self, embedding: np.ndarray, label: str = None) -> bool:
        """
        Add a new embedding to the owner's voiceprint collection.
        
        Args:
            embedding: 256-dim voice embedding
            label: Optional label (e.g., "evening_sample", "whisper")
            
        Returns:
            True if successfully added
        """
        if not self._is_valid_embedding(embedding):
            logger.error("Invalid embedding provided")
            return False
        
        # Create directory if needed
        OWNER_EMBEDDINGS_DIR.mkdir(exist_ok=True)
        
        # Find next available index
        existing = list(OWNER_EMBEDDINGS_DIR.glob("embedding_*.npy"))
        next_idx = len(existing)
        
        # Generate label if not provided
        if label is None:
            label = f"sample_{next_idx}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # Save embedding
        emb_path = OWNER_EMBEDDINGS_DIR / f"embedding_{next_idx:03d}.npy"
        np.save(emb_path, embedding)
        
        # Update in-memory
        self.owner_embeddings.append(embedding)
        self.embedding_labels.append(label)
        
        # Update metadata
        self._save_metadata()
        
        self.enabled = True
        logger.info(f"✅ Added new voiceprint: {label} (total: {len(self.owner_embeddings)})")
        
        return True
    
    def _save_metadata(self):
        """Save embedding metadata."""
        OWNER_EMBEDDINGS_DIR.mkdir(exist_ok=True)
        meta = {
            "labels": self.embedding_labels,
            "count": len(self.owner_embeddings),
            "updated": datetime.now().isoformat(),
            "threshold": self.threshold
        }
        with open(EMBEDDINGS_META_PATH, 'w') as f:
            json.dump(meta, f, indent=2)
    
    def get_stats(self) -> dict:
        """Get verification stats for debugging."""
        return {
            "enabled": self.enabled,
            "num_embeddings": len(self.owner_embeddings),
            "labels": self.embedding_labels,
            "threshold": self.threshold,
            "recent_scores": self.recent_scores,
            "avg_recent_score": np.mean(self.recent_scores) if self.recent_scores else None
        }
    
    def clear_embeddings(self):
        """Remove all embeddings (for re-enrollment)."""
        import shutil
        
        if OWNER_EMBEDDINGS_DIR.exists():
            shutil.rmtree(OWNER_EMBEDDINGS_DIR)
        
        if OWNER_EMBEDDING_PATH.exists():
            OWNER_EMBEDDING_PATH.unlink()
        
        self.owner_embeddings = []
        self.embedding_labels = []
        self.enabled = False
        
        logger.info("🗑️ All voiceprints cleared")


# Singleton instance for reuse
_verifier: Optional[SpeakerVerifier] = None

def get_verifier() -> SpeakerVerifier:
    """Get the shared verifier instance."""
    global _verifier
    if _verifier is None:
        _verifier = SpeakerVerifier()
    return _verifier

def reload_verifier() -> SpeakerVerifier:
    """Force reload of verifier (after adding new samples)."""
    global _verifier
    _verifier = SpeakerVerifier()
    return _verifier
