"""
MQTT MCP Client.
Provides MQTT broker integration with subscribe/publish capabilities.
Critical for Brain's sensor communication and system orchestration.
"""
import asyncio
import json
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from datetime import datetime
import aiomqtt


class MQTTMCPClient:
    """
    Client for MQTT operations.
    Wraps aiomqtt for both Architect and Brain.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None
    ):
        """
        Initialize MQTT client.

        Args:
            host: MQTT broker host
            port: MQTT broker port
            username: Optional username
            password: Optional password
            client_id: Optional client ID
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id or f"sage_mcp_{id(self)}"
        self.client: Optional[aiomqtt.Client] = None
        self.subscriptions: Dict[str, List[Callable]] = {}
        self._listen_task: Optional[asyncio.Task] = None

    async def connect(self) -> Dict[str, Any]:
        """
        Connect to MQTT broker.

        Returns:
            Dict with connection result
        """
        try:
            self.client = aiomqtt.Client(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                identifier=self.client_id
            )

            await self.client.__aenter__()

            return {
                "success": True,
                "host": self.host,
                "port": self.port,
                "client_id": self.client_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect: {str(e)}"
            }

    async def disconnect(self) -> Dict[str, Any]:
        """
        Disconnect from MQTT broker.

        Returns:
            Dict with disconnection result
        """
        try:
            if self._listen_task:
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass

            if self.client:
                await self.client.__aexit__(None, None, None)
                self.client = None

            return {
                "success": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to disconnect: {str(e)}"
            }

    async def publish(
        self,
        topic: str,
        payload: Any,
        qos: int = 0,
        retain: bool = False
    ) -> Dict[str, Any]:
        """
        Publish message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON-encoded if dict)
            qos: Quality of Service (0, 1, or 2)
            retain: Retain message flag

        Returns:
            Dict with publish result
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Not connected to broker"
                }

            # Encode payload
            if isinstance(payload, (dict, list)):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)

            await self.client.publish(
                topic=topic,
                payload=payload_str,
                qos=qos,
                retain=retain
            )

            return {
                "success": True,
                "topic": topic,
                "payload": payload_str,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to publish: {str(e)}"
            }

    async def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], None],
        qos: int = 0
    ) -> Dict[str, Any]:
        """
        Subscribe to MQTT topic.

        Args:
            topic: MQTT topic (supports wildcards: +, #)
            callback: Function to call when message received
            qos: Quality of Service

        Returns:
            Dict with subscription result
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Not connected to broker"
                }

            await self.client.subscribe(topic, qos=qos)

            # Store callback
            if topic not in self.subscriptions:
                self.subscriptions[topic] = []
            self.subscriptions[topic].append(callback)

            # Start listening if not already
            if not self._listen_task:
                self._listen_task = asyncio.create_task(self._listen_loop())

            return {
                "success": True,
                "topic": topic,
                "qos": qos
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to subscribe: {str(e)}"
            }

    async def unsubscribe(self, topic: str) -> Dict[str, Any]:
        """
        Unsubscribe from MQTT topic.

        Args:
            topic: MQTT topic

        Returns:
            Dict with unsubscribe result
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Not connected to broker"
                }

            await self.client.unsubscribe(topic)

            # Remove callbacks
            if topic in self.subscriptions:
                del self.subscriptions[topic]

            return {
                "success": True,
                "topic": topic
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to unsubscribe: {str(e)}"
            }

    async def _listen_loop(self):
        """Internal loop to listen for messages."""
        try:
            async for message in self.client.messages:
                # Match topic to subscriptions
                for subscribed_topic, callbacks in self.subscriptions.items():
                    if self._topic_matches(str(message.topic), subscribed_topic):
                        # Parse payload
                        try:
                            payload = json.loads(message.payload.decode())
                        except:
                            payload = message.payload.decode()

                        msg_data = {
                            "topic": str(message.topic),
                            "payload": payload,
                            "qos": message.qos,
                            "retain": message.retain,
                            "timestamp": datetime.now().isoformat()
                        }

                        # Call all callbacks
                        for callback in callbacks:
                            if asyncio.iscoroutinefunction(callback):
                                asyncio.create_task(callback(msg_data))
                            else:
                                callback(msg_data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"MQTT listen loop error: {e}")

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches subscription pattern."""
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')

        if len(pattern_parts) > len(topic_parts) and '#' not in pattern:
            return False

        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part == '#':
                return True
            if i >= len(topic_parts):
                return False
            if pattern_part != '+' and pattern_part != topic_parts[i]:
                return False

        return len(topic_parts) == len(pattern_parts)

    async def get_retained_message(self, topic: str, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Get retained message for topic.

        Args:
            topic: MQTT topic
            timeout: Timeout in seconds

        Returns:
            Dict with retained message or None
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Not connected to broker"
                }

            # Subscribe and wait for retained message
            result = {"success": False, "message": None}
            event = asyncio.Event()

            async def on_message(msg: Dict[str, Any]):
                if msg.get("retain"):
                    result["success"] = True
                    result["message"] = msg
                    event.set()

            await self.subscribe(topic, on_message)

            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                result["success"] = True
                result["message"] = None

            await self.unsubscribe(topic)

            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get retained message: {str(e)}"
            }

    # Convenience methods for common Sage operations

    async def publish_state(
        self,
        room: str,
        sensor: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish sensor state.

        Args:
            room: Room name
            sensor: Sensor type
            state: Sensor state data

        Returns:
            Publish result
        """
        topic = f"sage/brain/{room}/{sensor}/state"
        return await self.publish(topic, state, retain=True)

    async def publish_command(
        self,
        room: str,
        device: str,
        command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish device command.

        Args:
            room: Room name
            device: Device name
            command: Command data

        Returns:
            Publish result
        """
        topic = f"sage/home/{room}/{device}/command"
        return await self.publish(topic, command)

    async def subscribe_to_sensor(
        self,
        room: str,
        sensor: str,
        callback: Callable
    ) -> Dict[str, Any]:
        """
        Subscribe to sensor updates.

        Args:
            room: Room name
            sensor: Sensor type
            callback: Callback function

        Returns:
            Subscribe result
        """
        topic = f"sage/brain/{room}/{sensor}/#"
        return await self.subscribe(topic, callback)

    async def subscribe_to_all_sensors(self, callback: Callable) -> Dict[str, Any]:
        """
        Subscribe to all sensor updates.

        Args:
            callback: Callback function

        Returns:
            Subscribe result
        """
        return await self.subscribe("sage/brain/#", callback)

    async def get_room_state(self, room: str) -> Dict[str, Any]:
        """
        Get current state of all sensors in a room.

        Args:
            room: Room name

        Returns:
            Dict with room state
        """
        try:
            states = {}
            sensors = ["presence", "screen", "voice", "keyboard"]

            for sensor in sensors:
                topic = f"sage/brain/{room}/{sensor}/state"
                result = await self.get_retained_message(topic, timeout=1.0)
                if result["success"] and result["message"]:
                    states[sensor] = result["message"]["payload"]

            return {
                "success": True,
                "room": room,
                "sensors": states
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get room state: {str(e)}"
            }

    async def trigger_architect_build(
        self,
        project_id: str,
        request: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trigger Architect build via MQTT.

        Args:
            project_id: Project ID
            request: Build request
            options: Build options

        Returns:
            Publish result
        """
        topic = "sage/architect/build/trigger"
        payload = {
            "project_id": project_id,
            "request": request,
            "options": options or {},
            "timestamp": datetime.now().isoformat()
        }
        return await self.publish(topic, payload)

    async def subscribe_to_architect_builds(self, callback: Callable) -> Dict[str, Any]:
        """
        Subscribe to Architect build events.

        Args:
            callback: Callback function

        Returns:
            Subscribe result
        """
        return await self.subscribe("sage/architect/build/#", callback)

    async def get_all_topics(self, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Discover all active topics.

        Args:
            timeout: Discovery timeout

        Returns:
            Dict with list of topics
        """
        try:
            topics = set()
            event = asyncio.Event()

            async def on_message(msg: Dict[str, Any]):
                topics.add(msg["topic"])

            await self.subscribe("#", on_message)

            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass

            await self.unsubscribe("#")

            return {
                "success": True,
                "topics": sorted(list(topics)),
                "count": len(topics)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to discover topics: {str(e)}"
            }


# Context manager support
class MQTTMCPClientContext:
    """Context manager for MQTTMCPClient."""

    def __init__(self, *args, **kwargs):
        self.client = MQTTMCPClient(*args, **kwargs)

    async def __aenter__(self):
        await self.client.connect()
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.disconnect()
