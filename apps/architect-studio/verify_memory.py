"""
Verification Script: Architect Recall
Tests if the Architect's memory works and respects Cognitive Zones.
"""
import sys
import os
sys.path.append(os.getcwd())
import chromadb
from architect.memory import ArchitectMemory

def test():
    print("--- Architect Memory Verification ---")
    mem = ArchitectMemory()
    
    # Test 1: Recall "Truth" (Deterministic Logic)
    print("\n[Query 1] Asming about 'sleep thresholds' (Expect: brain/core/summary_engine.py)")
    results = mem.query(
        project_id="sage_brain",
        query_text="What is the threshold for sleep variance?",
        n_results=1,
        zone_filter="layer:deterministic" 
    )
    
    if results['ids'] and results['ids'][0]:
        meta = results['metadatas'][0][0]
        print(f"✅ Found in: {meta['source']}")
        print(f"   Zone: {meta['zone']}")
        print(f"   Excerpt: {results['documents'][0][0][:100]}...")
    else:
        print("❌ Failed to recall sleep thresholds from layer:deterministic")

    # Test 2: Recall "Persona" (Inference Logic)
    print("\n[Query 2] Asking about 'persona prompts' (Expect: brain/ai/personalities.py)")
    results = mem.query(
        project_id="sage_brain",
        query_text="How is the Kenyan Babe persona defined?",
        n_results=1,
        zone_filter="layer:inference"
    )
    
    if results['ids'] and results['ids'][0]:
        meta = results['metadatas'][0][0]
        print(f"✅ Found in: {meta['source']}")
        print(f"   Zone: {meta['zone']}")
    else:
        print("❌ Failed to recall persona from layer:inference")

if __name__ == "__main__":
    test()
