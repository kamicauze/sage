#!/usr/bin/env python3
"""
Quick test script for MCP clients.
Tests all Tier 1 MCP integrations.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from shared.mcp import MCPManager


async def test_filesystem():
    """Test Filesystem MCP."""
    print("\n" + "="*60)
    print("Testing Filesystem MCP")
    print("="*60)

    from shared.mcp import FilesystemMCPClient

    fs = FilesystemMCPClient()

    # Test directory listing
    result = await fs.list_directory(".", recursive=False)
    if result["success"]:
        print(f"✅ List directory: Found {result['count']} items")
    else:
        print(f"❌ List directory failed: {result['error']}")

    # Test file read
    result = await fs.read_file("README.md")
    if result["success"]:
        print(f"✅ Read file: {result['size']} bytes")
    else:
        print(f"❌ Read file failed: {result['error']}")

    # Test file write
    test_file = ".test_mcp_write.tmp"
    result = await fs.write_file(test_file, "Test content", atomic=True)
    if result["success"]:
        print(f"✅ Write file: {test_file}")

        # Clean up
        await fs.delete_file(test_file)
        print(f"✅ Delete file: {test_file}")
    else:
        print(f"❌ Write file failed: {result['error']}")


async def test_mqtt():
    """Test MQTT MCP."""
    print("\n" + "="*60)
    print("Testing MQTT MCP")
    print("="*60)

    from shared.mcp import MQTTMCPClient

    mqtt = MQTTMCPClient("localhost", 1883)

    # Test connection
    result = await mqtt.connect()
    if result["success"]:
        print(f"✅ Connected to MQTT broker: {result['host']}:{result['port']}")

        # Test publish
        result = await mqtt.publish(
            "sage/test/mcp",
            {"test": True, "message": "MCP test"},
            retain=False
        )
        if result["success"]:
            print(f"✅ Published to topic: {result['topic']}")
        else:
            print(f"❌ Publish failed: {result['error']}")

        # Test get topics (with short timeout)
        result = await mqtt.get_all_topics(timeout=1.0)
        if result["success"]:
            print(f"✅ Discovered {result['count']} topics")
        else:
            print(f"❌ Get topics failed: {result['error']}")

        await mqtt.disconnect()
        print("✅ Disconnected from MQTT")
    else:
        print(f"⚠️  Could not connect to MQTT: {result['error']}")
        print("   (This is OK if MQTT broker is not running)")


async def test_ollama():
    """Test Ollama MCP."""
    print("\n" + "="*60)
    print("Testing Ollama MCP")
    print("="*60)

    from shared.mcp import OllamaMCPClient

    ollama = OllamaMCPClient("http://localhost:11434")

    # Test list models
    result = await ollama.list_models()
    if result["success"]:
        print(f"✅ Listed {result['count']} models")
        if result["models"]:
            for model in result["models"][:3]:
                size_gb = model["size"] / 1e9
                print(f"   - {model['name']} ({size_gb:.1f}GB)")
    else:
        print(f"⚠️  Could not list models: {result['error']}")
        print("   (This is OK if Ollama is not running)")
        return

    # Test model recommendation
    result = await ollama.recommend_model_for_task("chat")
    if result["success"]:
        print(f"✅ Recommended model for chat: {result['recommended_model']}")
    else:
        print(f"❌ Recommend model failed: {result['error']}")

    await ollama.close()


async def test_memory():
    """Test Memory MCP."""
    print("\n" + "="*60)
    print("Testing Memory MCP")
    print("="*60)

    from shared.mcp import MemoryMCPClient

    memory = MemoryMCPClient(".sage_memory_test")

    # Test remember
    result = await memory.remember(
        text="MCP integration test - this is a test memory",
        collection_name="test_memories",
        metadata={"type": "test", "purpose": "mcp_verification"}
    )
    if result["success"]:
        print(f"✅ Remembered: {result['id']}")
        test_id = result['id']

        # Test recall
        result = await memory.recall(
            query="test memory",
            collection_name="test_memories",
            n_results=1
        )
        if result["success"]:
            print(f"✅ Recalled {result['count']} memories")
        else:
            print(f"❌ Recall failed: {result['error']}")

        # Test list collections
        result = await memory.list_collections()
        if result["success"]:
            print(f"✅ Found {len(result['collections'])} collections")
        else:
            print(f"❌ List collections failed: {result['error']}")

        # Clean up
        result = await memory.forget([test_id], "test_memories")
        if result["success"]:
            print(f"✅ Forgot test memory")

    else:
        print(f"❌ Remember failed: {result['error']}")


async def test_mcp_manager():
    """Test MCP Manager."""
    print("\n" + "="*60)
    print("Testing MCP Manager")
    print("="*60)

    mcp = MCPManager({
        "git": {"repo_path": os.getcwd()},
        "memory": {"persist_directory": ".sage_memory_test"}
    })

    # Test lazy loading
    print(f"✅ Created MCP Manager")

    # Test status
    status = mcp.get_status()
    print(f"✅ Status: {status}")

    # Test Git client
    try:
        git_status = await mcp.git.get_status()
        if git_status["success"]:
            print(f"✅ Git: Repo has {len(git_status['staged'])} staged files")
        else:
            print(f"❌ Git failed: {git_status['error']}")
    except Exception as e:
        print(f"❌ Git failed: {str(e)}")

    # Close all
    await mcp.close_all()
    print("✅ Closed all MCP clients")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("MCP Integration Tests")
    print("="*60)

    await test_filesystem()
    await test_mqtt()
    await test_ollama()
    await test_memory()
    await test_mcp_manager()

    print("\n" + "="*60)
    print("All MCP tests completed!")
    print("="*60)
    print("\nNote: Some tests may show warnings if services are not running.")
    print("This is expected - the MCPs will work when the services are available.")


if __name__ == "__main__":
    asyncio.run(main())
