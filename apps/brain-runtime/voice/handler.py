"""
Voice Command Handler
Processes STT transcripts and dispatches to appropriate pathway.

Flow:
    1. Receive transcript from STT service
    2. Classify intent (architect_task, brain_query, home_control)
    3. Route to appropriate handler
    4. Return response for TTS
"""
import sys
import os
import time
from typing import Callable, Awaitable, Dict, Any, Optional

# Add shared module to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.intent import classify_intent, Intent, get_task_type_from_intent
from shared.routing import UnifiedRouter, RouteDecision
from brain.ai.conversation import get_conversation
try:
    from core.response_contract import normalize_voice_response
except ImportError:
    from brain.core.response_contract import normalize_voice_response


class VoiceHandler:
    """
    Handles voice commands from STT and dispatches to Brain, Architect, or Agents.
    """

    def __init__(
        self,
        brain_callback: Callable[[Intent, Dict, str], Awaitable[Dict]],
        architect_bridge: Optional[Any] = None,
        agent_bridge: Optional[Any] = None,
        policy: Dict = None
    ):
        """
        Args:
            brain_callback: async fn(intent, context, reason) -> response
                Called for brain_query and home_control intents
            architect_bridge: ArchitectBridge instance for code tasks
            agent_bridge: AgentBridge instance for agent lifecycle
            policy: Routing policy dict (thresholds, models)
        """
        self.brain_callback = brain_callback
        self.architect = architect_bridge
        self.agent_bridge = agent_bridge
        self.router = UnifiedRouter(policy or self._default_policy())

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}
    
    def _default_policy(self) -> Dict:
        """Default routing policy if none provided."""
        return {
            'routing_thresholds': {
                'hybrid_score': 4,
                'cloud_score': 8
            },
            'models': {
                'local': 'ollama/gemma3:12b',
                'plan_hybrid': 'google/gemini-1.5-pro',
                'code_cloud': 'anthropic/claude-3-opus',
                'chat_cloud': 'xai/grok-beta',
            }
        }

    async def handle_transcript(
        self,
        transcript: str,
        context: Dict = None,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for voice commands.
        
        Args:
            transcript: Raw STT output (e.g., "Add expense tracking to brain")
            context: Optional context (room, time, user state, etc.)
        
        Returns:
            Response dict with:
                - type: 'success', 'acknowledged', 'error', 'none'
                - text: Response text for TTS
                - data: Additional response data
        """
        if context is None:
            context = {}

        print(f"[Voice] Received: '{transcript}'")

        intent = None
        try:
            # Get conversation context for intent classification
            conversation = get_conversation()
            conversation_context = conversation.get_intent_context()

            # 1. Classify Intent (Always Local, Fast, Rule-Based + Context Awareness)
            t_intent = time.time()
            intent = classify_intent(transcript, conversation_context=conversation_context)
            print(f"[Latency] intent: {int((time.time() - t_intent) * 1000)}ms")
            print(f"[Voice] Intent: type={intent.type}, project={intent.project}")
            print(f"[Voice] Signals: {intent.signals}")
            if conversation_context.get("mode") != "neutral":
                print(f"[Voice] Conversation mode: {conversation_context.get('mode')} (topic: {conversation_context.get('mode_topic')})")

            # Update conversation mode based on this message
            conversation.update_mode(transcript, intent.type)

            # 2. Dispatch based on intent type
            if intent.type == 'agent_task':
                raw_response = await self._handle_agent_task(intent, context)
            elif intent.type == 'architect_task':
                raw_response = await self._handle_architect(intent, context)
            elif intent.type == 'home_control':
                raw_response = await self._handle_home_control(intent, context)
            elif intent.type == 'smalltalk':
                raw_response = await self._handle_smalltalk(intent, context, on_token)
            else:
                raw_response = await self._handle_brain_query(intent, context, on_token)
        except Exception as e:
            fallback_intent = intent.type if intent else "brain_query"
            print(f"[Voice] Error handling intent: {e}")
            raw_response = {
                "type": "error",
                "text": f"Sorry, something went wrong: {str(e)}",
                "intent": fallback_intent,
            }
            return normalize_voice_response(
                raw_response,
                default_intent=fallback_intent,
                default_route="LOCAL",
            )

        default_intent = intent.type if intent else "brain_query"
        raw_route = self._safe_dict(raw_response).get("route", "LOCAL")
        return normalize_voice_response(
            raw_response,
            default_intent=default_intent,
            default_route=str(raw_route or "LOCAL"),
        )

    async def _handle_architect(
        self,
        intent: Intent,
        context: Dict
    ) -> Dict[str, Any]:
        """
        dispatch to Architect for code/planning tasks.
        """
        # Check for hypothetical/negative constraints
        # If user says "can you...", "don't do it", etc - treat as inquiry, not command
        q = intent.query.lower()
        is_inquiry = any(q.startswith(p) for p in ['can you', 'could you', 'are you able', 'do you know how'])
        is_negative = any(p in q for p in ['dont', "don't", 'do not', 'wait', 'stop'])
        
        if is_inquiry or is_negative:
            print(f"[Voice] Intercepted Architect command (Inquiry/Negative): {intent.query}")
            return {
                "type": "acknowledged",
                "text": "Yes, I can do that. Just say the word when you're ready to start.",
                "intent": "brain_query",
                "route": "LOCAL"
            }

        if not self.architect:
            return {
                "type": "error",
                "text": "Architect service is not available. Try again later.",
                "intent": "architect_task"
            }
        
        # Determine task type from the query
        task_type = get_task_type_from_intent(intent)
        print(f"[Voice] Architect task type: {task_type}")
        
        # Get routing decision (pre-RAG, will be refined by Architect)
        # Architect will do its own RAG retrieval and may adjust routing
        decision = self.router.route(
            query=intent.query,
            task_type=task_type,
            rag_docs=[],  # Empty - Architect will retrieve
            force_local=intent.signals.get('explicit_local', False)
        )
        
        print(f"[Voice] Pre-routing: {decision.route} ({decision.provider}/{decision.model})")
        print(f"[Voice] Reason: {decision.reason}")
        
        # Acknowledge immediately (Architect tasks can be slow)
        ack_text = self._build_ack_message(intent, decision)
        
        # Dispatch to Architect (this may take a while)
        result = await self.architect.dispatch(
            project_id=intent.project,
            query=intent.query,
            task_type=task_type,
            routing_hint=decision
        )
        result = self._safe_dict(result)
        status = str(result.get("status", "UNKNOWN")).upper()

        response_type = "acknowledged" if status == "SUCCESS" else "error"
        response_text = ack_text if status == "SUCCESS" else (
            result.get("summary") or "Architect task failed."
        )

        return {
            "type": response_type,
            "text": response_text,
            "status": status,
            "summary": result.get("summary", ""),
            "artifacts": result.get("artifacts", []),
            "intent": "architect_task",
            "route": decision.route
        }

    async def _handle_agent_task(
        self,
        intent: Intent,
        context: Dict
    ) -> Dict[str, Any]:
        """
        Handle agent lifecycle commands (start, stop, status, create).
        """
        print(f"[Voice] Agent task: '{intent.query}'")

        if not self.agent_bridge:
            return {
                "type": "error",
                "text": "Agent system is not available.",
                "intent": "agent_task",
                "route": "LOCAL",
            }

        result = await self.agent_bridge.dispatch(intent.query)
        result = self._safe_dict(result)

        return {
            **result,
            "intent": "agent_task",
            "route": "LOCAL",
        }

    async def _handle_home_control(
        self,
        intent: Intent,
        context: Dict
    ) -> Dict[str, Any]:
        """
        Handle home automation commands.
        These go through the Brain's action system.
        """
        print(f"[Voice] Home control: '{intent.query}'")
        
        # Delegate to Brain callback
        result = await self.brain_callback(intent, context, reason='home_control')
        result = self._safe_dict(result)

        return {
            **result,
            "intent": "home_control",
            "route": result.get("route", "LOCAL"),
            "text": result.get("text", "Done."),
        }

    async def _handle_brain_query(
        self,
        intent: Intent,
        context: Dict,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Handle general queries (chat, mood, info).
        These go through the Brain's AI advisor.
        """
        print(f"[Voice] Brain query: '{intent.query}'")
        
        # Determine if this needs cloud escalation
        decision = self.router.route(
            query=intent.query,
            task_type='chat',
            force_local=intent.signals.get('explicit_local', False)
        )
        
        # Add routing hint to context
        context['routing_hint'] = {
            'route': decision.route,
            'model': decision.model,
            'provider': decision.provider
        }
        
        # Delegate to Brain callback
        # Check if the callback supports the on_token argument (it should if we updated main.py)
        import inspect
        sig = inspect.signature(self.brain_callback)
        if 'on_token' in sig.parameters:
            result = await self.brain_callback(intent, context, reason='user_intent', on_token=on_token)
        else:
             # Legacy fallback
             result = await self.brain_callback(intent, context, reason='user_intent')
        result = self._safe_dict(result)
        
        return {
            **result,
            "text": result.get("text", ""),
            "intent": "brain_query",
            "route": decision.route
        }

    async def _handle_smalltalk(
        self,
        intent: Intent,
        context: Dict,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Handle smalltalk/check-ins with a fast, local path.
        """
        print(f"[Voice] Smalltalk: '{intent.query}'")

        import inspect
        sig = inspect.signature(self.brain_callback)
        if 'on_token' in sig.parameters:
            result = await self.brain_callback(intent, context, reason='smalltalk', on_token=on_token)
        else:
            result = await self.brain_callback(intent, context, reason='smalltalk')
        result = self._safe_dict(result)

        return {
            **result,
            "text": result.get("text", ""),
            "intent": "smalltalk",
            "route": "LOCAL",
        }

    def _build_ack_message(self, intent: Intent, decision: RouteDecision) -> str:
        """Build acknowledgment message for Architect tasks."""
        task_verbs = {
            'plan': 'planning',
            'code': 'coding',
            'fix': 'fixing',
            'test': 'writing tests for'
        }
        verb = task_verbs.get(decision.task_type, 'working on')
        
        route_hints = {
            'LOCAL': 'locally',
            'HYBRID': 'with some help from the cloud',
            'CLOUD': 'using cloud AI'
        }
        hint = route_hints.get(decision.route, '')
        
        project_name = intent.project.replace('_', ' ').title() if intent.project else 'the project'
        
        return f"Got it. I'm {verb} that for {project_name} {hint}. Give me a moment..."


# Convenience function for testing
async def test_handler():
    """Test the voice handler with mock callbacks."""
    
    async def mock_brain(intent, context, reason):
        return {"text": f"Brain handled: {intent.query}", "type": "suggestion"}
    
    class MockArchitect:
        async def dispatch(self, **kwargs):
            return {"status": "SUCCESS", "summary": f"Built: {kwargs.get('query')}"}
    
    handler = VoiceHandler(mock_brain, MockArchitect())
    
    tests = [
        "Add expense tracking to the brain",
        "What's the temperature?",
        "Turn off the lights",
        "Think hard and refactor the state machine",
    ]
    
    for t in tests:
        print(f"\n{'='*60}")
        result = await handler.handle_transcript(t, {"local_hour": 14})
        print(f"Result: {result}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_handler())
