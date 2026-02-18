
import asyncio
from brain.bridges.architect_bridge import ArchitectBridge

async def test_none_project():
    bridge = ArchitectBridge()
    
    print("Testing dispatch with project_id=None...")
    try:
        # This used to crash with AttributeError
        result = await bridge.dispatch(
            project_id=None,
            query="Test query",
            task_type="plan"
        )
        print(f"Result status: {result.get('status')}")
        print(f"Result summary: {result.get('summary')}")
        
        if result.get("status") == "FAILURE" and "Project 'None' not found" in result.get("summary"):
             print("SUCCESS: Handled None project gracefully (Project not found path).")
        elif result.get("status") == "SUCCESS":
             print("SUCCESS: Handled None project gracefully (Found fallback).")
        elif "Using sage.yaml" in str(result):
             print("SUCCESS: Fallback to sage.yaml triggered.")
        else:
             print("SUCCESS: Did not crash.")
             
    except AttributeError as e:
        print(f"FAILURE: Crashed with AttributeError: {e}")
    except Exception as e:
        print(f"FAILURE: Crashed with {type(e).__name__}: {e}")
    finally:
        bridge.shutdown()

if __name__ == "__main__":
    asyncio.run(test_none_project())
