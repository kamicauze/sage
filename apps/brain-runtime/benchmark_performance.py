import asyncio
import time
import json
import os
import sys

# Ensure brain is in path
sys.path.append(os.path.join(os.getcwd(), 'brain'))

# Use a dedicated memory path for benchmarks
os.environ.setdefault("SAGE_MEMORY_PATH", ".sage_memory_bench")

from ai.advisor import advise
from brain.memory.sage_memory import get_memory

async def benchmark():
    print("🚀 Running Sage Performance Benchmark...")
    print("="*40)

    # 1. Measure Memory Init (Embeddings)
    # We create a NEW instance to measure init time, ignoring the singleton
    print("\n--- 1. Memory Initialization (Embeddings on GPU) ---")
    t0 = time.time()
    mem = get_memory()
    t1 = time.time()
    print(f"✅ Memory Init Total Time: {int((t1-t0)*1000)}ms")
    # Verify device (indirectly via speed)
    t2 = time.time()
    mem.embed_fn(["benchmark test string"])
    print(f"✅ Embedding Inference (1 item): {int((time.time()-t2)*1000)}ms")

    # 2. Measure Ollama Cold Start
    print("\n--- 2. Ollama Cold Start (First Request) ---")
    context = {
        "trigger": {"type": "user_intent", "text": "Hello, are you running on GPU?"},
        "state": {},
        "local_hour": 12
    }
    
    t_called = time.time()
    response = await advise(context, {"reason": "user_intent"}, stream=False)
    t_mms = int((time.time() - t_called) * 1000)
    print(f"✅ Cold Request Latency: {t_mms}ms")
    print(f"Model used: {response.get('model')}")

    # 3. Measure Ollama Warm Request (Keep-Alive Test)
    print("\n--- 3. Ollama Warm Request (Second Request) ---")
    t_called = time.time()
    response = await advise(context, {"reason": "user_intent"}, stream=False)
    t_mms = int((time.time() - t_called) * 1000)
    print(f"✅ Warm Request Latency: {t_mms}ms")

    print("\nBenchmark Complete.")

if __name__ == "__main__":
    asyncio.run(benchmark())
