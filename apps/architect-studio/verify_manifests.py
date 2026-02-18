"""
Verification: Multi-Project & Manifests
"""
import sys
import os
sys.path.append(os.getcwd())
from architect.memory import ArchitectMemory
from architect.manifest import ProjectManifest

def test():
    print("\n--- Multi-Project Verification ---")
    mem = ArchitectMemory()
    
    # 1. Verify SAGE (Mapping: brain/core -> Truth)
    print("\n[Project: Sage] Query: 'sleep thresholds'")
    r1 = mem.query("sage_brain", "sleep thresholds", n_results=1, zone_filter="layer:deterministic")
    if r1['ids'] and r1['ids'][0]:
        print(f"✅ Found in: {r1['metadatas'][0][0]['source']}")
        print(f"   Role: {r1['metadatas'][0][0]['role']} (Expected: truth)")
    else:
        print("❌ Failed Sage Query")

    # 2. Verify FLIGHT REVIEW (Mapping: backend/physics -> Truth)
    print("\n[Project: Flight Review] Query: 'stall speed'")
    # Note: In flight_review.yaml, we named the zone "Physics Engine", which maps to role "truth"
    # The memory.query filters by 'zone' metadata if passed, but our ingest saves 
    # 'zone_name' as metadata. Let's rely on simple text search first to see metadata.
    
    r2 = mem.query("flight_review", "stall speed calculation", n_results=1)
    
    if r2['ids'] and r2['ids'][0]:
        meta = r2['metadatas'][0][0]
        print(f"✅ Found in: {meta['source']}")
        print(f"   Zone Name: {meta['zone_name']}")
        print(f"   Role: {meta['role']} (Expected: truth)")
    else:
        print("❌ Failed Flight Review Query")

if __name__ == "__main__":
    test()
