"""
Intent Classifier (Hybrid)
Combines fast rule-based classification with LLM fallback for ambiguous cases.

Intent Types:
    - architect_task: Code planning, building, debugging
    - agent_task: Agent lifecycle (start, stop, status, create agents)
    - brain_query: IoT queries, mood, general chat
    - smalltalk: Greetings, check-ins, low-risk chat
    - home_control: Direct device control (lights, timers)

Strategy:
    1. Rule-based classification (microseconds, free)
    2. If confidence < threshold, use local LLM (200ms-2s, free with Ollama)
"""
import re
import os
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

# Confidence threshold for rule-based classification
# Below this, we fall back to LLM
CONFIDENCE_THRESHOLD = float(os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.7"))

# Whether to use LLM fallback at all (module default).
# Runtime calls can override this via env / parameters.
USE_LLM_FALLBACK = os.getenv("INTENT_USE_LLM", "true").lower() == "true"

# Fast-path ambiguous brain queries to avoid LLM fallback latency.
INTENT_FAST_BRAIN = os.getenv("INTENT_FAST_BRAIN", "true").lower() in {"1", "true", "yes", "on"}


@dataclass
class Intent:
    type: str                       # 'architect_task', 'agent_task', 'brain_query', 'smalltalk', 'home_control'
    project: Optional[str]          # Target project ID (e.g., 'sage_brain')
    query: str                      # Cleaned query for processing
    original: str                   # Original transcript
    confidence: float = 1.0         # Classification confidence (0-1)
    method: str = 'rule'            # 'rule' or 'llm'
    signals: Dict[str, Any] = field(default_factory=dict)


# Project aliases: voice-friendly names → manifest project IDs
PROJECT_ALIASES = {
    'brain': 'sage_brain',
    'sage brain': 'sage_brain',
    'the brain': 'sage_brain',
    'sage': 'sage_brain',
    'flight review': 'flight_review',
    'flight': 'flight_review',
    'review app': 'flight_review',
}

# Architect trigger patterns (regex)
# These indicate the user wants to modify code/architecture
ARCHITECT_TRIGGERS = [
    # Action + target patterns
    r'\b(add|create|build|implement|write|make)\b.{0,20}\b(feature|function|class|module|pattern|endpoint|api)\b',
    r'\b(fix|debug|repair|solve)\b.{0,20}\b(bug|error|issue|problem|crash)\b',
    r'\b(refactor|rewrite|redesign|restructure|optimize)\b',
    r'\b(delete|remove|drop)\b.{0,20}\b(feature|function|class|module)\b',
    r'\b(update|modify|change|edit)\b.{0,20}\b(code|function|class|logic)\b',
    
    # Explicit project targeting
    r'\b(add|create|build|implement)\b.{0,30}\bto\s+(the\s+)?(brain|sage|flight|project)\b',
    
    # Planning triggers
    r'\bplan\b.{0,10}\b(for|to|out)\b',
    r'\bbuild\b.{0,10}\bplan\b',
    r'\bdesign\b.{0,20}\b(system|architecture|flow)\b',
    
    # Test triggers
    r'\b(write|create|add)\b.{0,10}\btests?\b',
    r'\btest\b.{0,10}\b(coverage|suite)\b',
]

# Agent lifecycle patterns
AGENT_TRIGGERS = [
    r'\b(start|run|launch|spin up|kick off)\b.{0,20}\b(agent|pipeline|factory|workflow)\b',
    r'\b(what|how).{0,10}(is|are).{0,10}\b(agent|pipeline|factory)\b.{0,10}(doing|status|progress)\b',
    r'\b(stop|pause|kill|cancel)\b.{0,10}\b(agent|pipeline|factory|task)\b',
    r'\b(build|create|make)\s+me\s+(an?\s+)?agent\b',
    r'\bagent\b.{0,10}\b(status|report|update)\b',
    r'\b(list|show)\b.{0,10}\b(agent|agents|pipeline|pipelines)\b',
]

# Home control patterns
HOME_TRIGGERS = [
    r'\b(turn|switch)\b.{0,10}\b(on|off)\b.{0,20}\b(light|lights|lamp|fan|ac|heater)\b',
    r'\b(set|start|stop|cancel)\b.{0,10}\b(timer|alarm|reminder)\b',
    r'\bwhat.{0,10}(is|the).{0,10}(temperature|humidity|motion|time)\b',
    r'\b(dim|brighten)\b.{0,10}\b(light|lights)\b',
    r'\b(lock|unlock)\b.{0,10}\b(door|doors)\b',
]

# Status/info queries (stay in brain, don't trigger architect)
INFO_TRIGGERS = [
    r'\b(what|how|when|where|why|who)\b.{0,5}\b(is|are|was|were|do|does)\b',
    r'\btell me about\b',
    r'\bexplain\b',
    r'\bstatus\b',
    r'\bhow.{0,5}(am i|are you)\b',
]


def classify_intent(
    transcript: str,
    use_llm_fallback: bool = None,
    conversation_context: Dict[str, Any] = None
) -> Intent:
    """
    Classify a voice transcript into an intent using hybrid approach.

    Strategy:
        1. Try rule-based classification (fast)
        2. Apply conversation context biasing (if in emotional/technical mode)
        3. If confidence < threshold, use LLM fallback (if enabled)

    Args:
        transcript: Raw STT output
        use_llm_fallback: Override for LLM fallback (None = use env var)
        conversation_context: Optional context from ConversationHistory.get_intent_context()
            - mode: "neutral", "emotional", "technical", "playful"
            - emotional_mode: bool
            - recent_intents: List of last 3 intent types
            - turns_in_mode: How many turns we've been in this mode

    Returns:
        Intent with type, project, query, confidence, and method
    """
    if use_llm_fallback is None:
        env_use_llm = os.getenv("INTENT_USE_LLM", "true").lower() == "true"
        force_cloud_reasoning = os.getenv("SAGE_FORCE_CLOUD_REASONING", "false").lower() in {
            "1", "true", "yes", "on"
        }
        # In cloud-only reasoning mode, disable local Ollama intent fallback
        # to avoid competing for GPU memory with Qwen TTS.
        use_llm_fallback = env_use_llm and not force_cloud_reasoning

    # Phase 1: Rule-based classification
    rule_intent = _rule_based_classify(transcript)

    print(f"[Intent] Rule-based: type={rule_intent.type}, confidence={rule_intent.confidence:.2f}")

    # Phase 1.5: Apply conversation context biasing
    if conversation_context:
        rule_intent = _apply_context_bias(rule_intent, conversation_context)

    # If high confidence, return immediately
    if rule_intent.confidence >= CONFIDENCE_THRESHOLD:
        return rule_intent

    # Optional fast path: for plain conversational inputs, skip LLM fallback.
    if (
        INTENT_FAST_BRAIN
        and rule_intent.type == "brain_query"
        and _should_fast_path_brain_query(rule_intent.original)
    ):
        boosted_confidence = max(rule_intent.confidence, 0.78)
        print(
            f"[Intent] Fast-path brain_query (skip LLM fallback), "
            f"confidence boosted to {boosted_confidence:.2f}"
        )
        return Intent(
            type=rule_intent.type,
            project=rule_intent.project,
            query=rule_intent.query,
            original=rule_intent.original,
            confidence=boosted_confidence,
            method="fast_rule",
            signals={**rule_intent.signals, "fast_path_brain": True},
        )

    # Phase 2: LLM fallback for ambiguous cases
    if use_llm_fallback:
        print(f"[Intent] Low confidence ({rule_intent.confidence:.2f}), trying LLM fallback...")
        llm_intent = _llm_classify(transcript, hint=rule_intent)
        if llm_intent is not None:
            return llm_intent
        print("[Intent] LLM fallback failed, using rule-based result")

    # Return rule-based result if LLM disabled or failed
    return rule_intent


def _apply_context_bias(intent: Intent, context: Dict[str, Any]) -> Intent:
    """
    Apply conversation context to bias intent classification.

    When we're in an emotional conversation, ambiguous inputs should stay in that flow.
    When we're in a technical conversation, "fix that" means code, not feelings.
    """
    mode = context.get("mode", "neutral")
    emotional_mode = context.get("emotional_mode", False)
    turns_in_mode = context.get("turns_in_mode", 0)
    recent_intents = context.get("recent_intents", []) or []

    # If we're in emotional mode and confidence is low, bias toward brain_query
    if emotional_mode and intent.confidence < CONFIDENCE_THRESHOLD:
        # Short/ambiguous responses in emotional context stay in conversation
        if len(intent.original.split()) <= 6:  # Short message
            print(f"[Intent] Context bias: emotional mode + short message -> brain_query")
            return Intent(
                type="brain_query",
                project=None,
                query=intent.original,
                original=intent.original,
                confidence=0.85,  # Boost confidence
                method="context",
                signals={**intent.signals, "context_biased": True, "emotional_context": True}
            )

    # If we're in technical mode and get ambiguous architect-like input
    if mode == "technical" and intent.type == "brain_query" and intent.confidence < 0.5:
        # Check for technical action words
        tech_actions = ["fix", "change", "update", "add", "remove", "make", "do"]
        if any(word in intent.original.lower() for word in tech_actions):
            print(f"[Intent] Context bias: technical mode + action word -> architect_task")
            return Intent(
                type="architect_task",
                project=intent.project or "sage_brain",
                query=intent.original,
                original=intent.original,
                confidence=0.80,
                method="context",
                signals={**intent.signals, "context_biased": True, "technical_context": True}
            )

    # Conversational continuity: short follow-ups in an active chat should
    # stay on the fast local path without LLM intent fallback.
    conversational_recent = any(i in ("smalltalk", "brain_query") for i in recent_intents)
    if (
        conversational_recent
        and intent.type == "brain_query"
        and intent.confidence < CONFIDENCE_THRESHOLD
        and _looks_like_conversational_followup(intent.original)
    ):
        print("[Intent] Context bias: conversational follow-up -> brain_query")
        return Intent(
            type="brain_query",
            project=None,
            query=intent.original,
            original=intent.original,
            confidence=0.82,
            method="context",
            signals={**intent.signals, "context_biased": True, "conversation_continuity": True},
        )

    return intent


def _looks_like_conversational_followup(text: str) -> bool:
    """
    Fast heuristic for short, non-command follow-up utterances.
    Example: "niko fiti, just trying to make dinner", "chicken salad".
    """
    if not text:
        return False

    lowered = text.lower().strip()
    if not lowered or "?" in lowered:
        return False

    words = re.findall(r"[a-z0-9']+", lowered)
    if not words or len(words) > 10:
        return False

    command_starters = {
        "add", "create", "build", "implement", "write", "fix", "debug", "repair",
        "refactor", "rewrite", "redesign", "delete", "remove", "update", "change",
        "turn", "switch", "set", "start", "stop", "cancel", "lock", "unlock",
        "dim", "brighten", "plan", "design", "test", "deploy",
    }
    if words[0] in command_starters:
        return False

    command_topics = {
        "feature", "function", "class", "module", "api", "code", "bug", "error",
        "lights", "light", "lamp", "fan", "ac", "heater", "timer", "alarm",
        "temperature", "humidity", "door", "doors",
    }
    if any(w in command_topics for w in words):
        return False

    return True


def _should_fast_path_brain_query(text: str) -> bool:
    """
    Decide whether an ambiguous brain_query should skip expensive LLM fallback.
    We keep fallback for command-like utterances that might be architect/home tasks.
    """
    if not text:
        return False

    lowered = text.lower().strip()
    words = re.findall(r"[a-z0-9']+", lowered)
    if not words:
        return False

    command_starters = {
        "add", "create", "build", "implement", "write", "make",
        "fix", "debug", "repair", "refactor", "rewrite", "redesign",
        "delete", "remove", "update", "change", "edit", "test",
        "turn", "switch", "set", "start", "stop", "cancel",
        "lock", "unlock", "dim", "brighten", "plan", "deploy",
        "launch", "run", "kick", "spin",
    }
    if words[0] in command_starters:
        return False

    task_terms = {
        "feature", "function", "class", "module", "api", "endpoint", "code",
        "bug", "error", "issue", "crash", "timer", "alarm", "lights", "light",
        "fan", "heater", "temperature", "humidity", "door", "doors",
        "agent", "pipeline", "factory", "workflow",
    }
    if any(w in task_terms for w in words):
        return False

    return True


def _rule_based_classify(transcript: str) -> Intent:
    """
    Fast rule-based classification with confidence scoring.
    """
    original = transcript
    text = transcript.lower().strip()
    signals = _extract_signals(text)
    
    # Track best match
    best_type = 'brain_query'
    best_confidence = 0.3  # Default confidence for fallback
    matched_pattern = None
    
    # 0. Check Agent lifecycle triggers (highest priority for agent commands)
    agent_patterns = [
        (r'\b(start|run|launch|spin up|kick off)\b.{0,20}\b(agent|pipeline|factory|workflow)\b', 0.95),
        (r'\b(stop|pause|kill|cancel)\b.{0,20}\b(the\s+)?\w+\s+(agent|pipeline)\b', 0.95),
        (r'\b(stop|pause|kill|cancel)\b.{0,10}\b(agent|pipeline|factory|task)\b', 0.95),
        (r'\b(build|create|make)\s+me\s+(an?\s+)?agent\b', 0.95),
        (r'\bagent\b.{0,10}\b(status|report|update)\b', 0.90),
        (r'\b(list|show)\b.{0,10}\b(agents?|pipelines?)\b', 0.90),
        (r'\bwhat\b.{0,15}\bagents?\b.{0,10}\b(doing|running|status)\b', 0.90),
        (r'\bhow\b.{0,10}\b(is|are)\b.{0,10}\b(the\s+)?(agents?|pipelines?|factory)\b', 0.85),
    ]

    for pattern, confidence in agent_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            if confidence > best_confidence:
                best_type = 'agent_task'
                best_confidence = confidence
                matched_pattern = pattern
            break

    # 1. Check Architect triggers with confidence levels
    architect_patterns = [
        # High confidence (0.95) - explicit code actions
        (r'\b(add|create|build|implement|write)\s+\w+\s+(feature|function|class|module|pattern|endpoint)\b', 0.95),
        (r'\b(fix|debug|repair)\s+\w+\s+(bug|error|issue|crash)\b', 0.95),
        (r'\brefactor\b.*\b(code|function|class|module)\b', 0.95),
        
        # Medium-high confidence (0.85) - project targeting
        (r'\b(add|create|build|implement)\b.{0,30}\bto\s+(the\s+)?(brain|sage|flight|project)\b', 0.85),
        (r'\bplan\s+(for|to|out)\b', 0.85),
        
        # Medium confidence (0.70) - could be ambiguous
        (r'\b(add|create|build)\b.{0,15}\b(feature|function)\b', 0.70),
        (r'\b(fix|update|change)\b.{0,15}\b(code|logic)\b', 0.70),
        
        # Low confidence (0.50) - needs LLM verification
        (r'\brefactor\b', 0.50),  # "refactor my thinking" ≠ code
        (r'\b(add|create)\b', 0.40),  # Very ambiguous
    ]
    
    for pattern, confidence in architect_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            if confidence > best_confidence:
                best_type = 'architect_task'
                best_confidence = confidence
                matched_pattern = pattern
            break  # Take first (most specific) match
    
    # 2. Check Home Control triggers
    home_patterns = [
        # High confidence
        (r'\b(turn|switch)\s+(on|off)\b.{0,15}\b(light|lights|lamp|fan|ac)\b', 0.95),
        (r'\bset\s+(a\s+)?timer\b', 0.90),
        (r'\bwhat.{0,5}(is|the).{0,5}temperature\b', 0.90),
        
        # Medium confidence
        (r'\b(dim|brighten)\b', 0.70),
    ]
    
    for pattern, confidence in home_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            if confidence > best_confidence:
                best_type = 'home_control'
                best_confidence = confidence
                matched_pattern = pattern
            break
    
    # 3. Check for smalltalk/check-in patterns (fast path, avoid LLM fallback)
    smalltalk_patterns = [
        (r'^(hi|hey|hello|yo|sup|sasa|niaje)\b', 0.90),
        (r'\bhow are you\b', 0.90),
        (r'\bwhat\'?s up\b', 0.85),
        (r'\bchecking in\b', 0.85),
        (r'\b(just|quick) (checking|check-in)\b', 0.85),
        (r'\b(i\'?m|i am|am)\s+back\b', 0.90),
        (r'\bback again\b', 0.90),
        (r'\b(are you|you) (there|awake)\b', 0.85),
        (r'\bgood (morning|night|evening)\b', 0.85),
    ]

    if best_type == 'brain_query':
        for pattern, confidence in smalltalk_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                best_type = 'smalltalk'
                best_confidence = confidence
                matched_pattern = pattern
                break

    # 4. Check for emotional support patterns (grief, loss, personal struggles)
    # These should be high confidence to avoid LLM fallback delay
    emotional_patterns = [
        # Grief and loss - highest priority
        (r'\b(died|death|passed away|suicide|funeral|burial)\b', 0.95),
        (r'\b(miss my|miss him|miss her|missing my|i miss)\b', 0.90),
        (r'\b(lost my|lost his|lost her|losing my)\b.{0,20}\b(mom|dad|mother|father|sister|brother|friend|wife|husband|son|daughter|baby|pet|dog|cat)\b', 0.95),
        (r'\b(grief|grieving|mourning)\b', 0.95),
        (r'\b(haven\'t healed|sijaheal|can\'t heal|still hurts)\b', 0.90),
        (r'\b(anniversary of|year since|years since)\b.{0,15}\b(death|died|passed|lost)\b', 0.95),

        # Personal struggles and emotional states
        (r'\b(i\'?m|i am|feeling)\s+(so\s+)?(sad|depressed|lonely|anxious|scared|worried|stressed|overwhelmed|empty|broken|lost)\b', 0.90),
        (r'\b(struggling with|going through|dealing with)\b', 0.85),
        (r'\b(can\'t cope|can\'t handle|can\'t take)\b', 0.90),
        (r'\blife is (hard|tough|difficult)\b', 0.85),

        # Opening up / vulnerability markers
        (r'\bi need to (talk|vent|share)\b', 0.90),
        (r'\bcan i tell you something\b', 0.90),
        (r'\bsomething happened\b', 0.85),
    ]

    if best_type == 'brain_query':
        for pattern, confidence in emotional_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if confidence > best_confidence:
                    best_confidence = confidence
                    matched_pattern = pattern
                break

    # 5. Check for conversation feedback patterns (about previous response)
    feedback_patterns = [
        (r'\b(soulless|robotic|generic|cold|stiff|weird)\s+(response|answer|reply)?\b', 0.90),
        (r'\bthat.{0,10}(was|is|sounds?)\s+(soulless|robotic|generic|cold|weird|off|strange)\b', 0.90),
        (r'\b(redo|try again|say it again|rephrase)\b', 0.85),
        (r'\bwith more (soul|heart|feeling|emotion|warmth)\b', 0.90),
        (r'\bbe more (human|natural|warm|genuine)\b', 0.85),
        (r'\bthat didn\'t (help|feel right|sound right)\b', 0.85),
    ]

    if best_type == 'brain_query':
        for pattern, confidence in feedback_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if confidence > best_confidence:
                    best_confidence = confidence
                    matched_pattern = pattern
                break

    # 6. Check for clear brain/chat patterns (boosts default confidence)
    brain_patterns = [
        (r'\b(how|what|why|when|where|who)\s+(am|are|is|do|does|did|know)\b', 0.85),
        (r'\btell\s+me\s+about\b', 0.85),
        (r'\bhow.{0,5}(am i|are you)\b', 0.90),
        (r'\bdo you (know|remember)\b', 0.85),  # "do you know who I am"
        (r'\b(feeling|mood|vibe)\b', 0.80),
    ]

    for pattern, confidence in brain_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            if best_type == 'brain_query' and confidence > best_confidence:
                best_confidence = confidence
                matched_pattern = pattern
            break
    
    # Build result
    project = _extract_project(text) if best_type == 'architect_task' else None
    query = _clean_query(text, project) if best_type in ('architect_task',) else text
    
    return Intent(
        type=best_type,
        project=project,
        query=query,
        original=original,
        confidence=best_confidence,
        method='rule',
        signals=signals
    )


def _llm_classify(transcript: str, hint: Intent = None) -> Optional[Intent]:
    """
    Use local LLM for intent classification when rules are uncertain.
    
    This is the slow path - only called for ambiguous cases.
    """
    try:
        import requests
        
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL_FAST", "gemma3:4b")  # Use smallest model
        
        # Build prompt with hint from rule-based classification
        hint_text = ""
        if hint:
            hint_text = f"\nThe rule-based system guessed: {hint.type} (confidence: {hint.confidence:.0%})"
        
        prompt = f'''Classify this voice command into exactly one category.

Voice command: "{transcript}"{hint_text}

Categories:
- architect_task: User wants to modify code, add features, fix bugs, plan development
- agent_task: User wants to start/stop/check agents, pipelines, or create new agents
- home_control: User wants to control home devices (lights, temperature, timers)
- smalltalk: Greeting/check-in/casual short social chat ("hi", "hey", "what's up", "you there?")
- brain_query: User is chatting, sharing personal feelings, asking questions, or giving feedback about the conversation

IMPORTANT: Personal/emotional statements like "i miss my sister", "she died", "i'm feeling sad", or feedback like "that was soulless" are brain_query with HIGH confidence (0.9+).

Also extract the target project if mentioned (brain, sage, flight_review).

Respond with ONLY valid JSON:
{{"intent": "architect_task"|"brain_query"|"smalltalk"|"home_control", "project": "sage_brain"|"flight_review"|null, "confidence": 0.0-1.0}}'''

        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 100}
            },
            timeout=5  # 5 second timeout
        )
        
        if response.status_code != 200:
            return None
        
        result_text = response.json().get("response", "")
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        result = json.loads(result_text.strip())
        
        intent_type = result.get("intent", "brain_query")
        project = result.get("project")
        confidence = float(result.get("confidence", 0.8))
        
        # Validate intent type
        if intent_type not in ('architect_task', 'agent_task', 'brain_query', 'smalltalk', 'home_control'):
            # Keep fallback deterministic for short social utterances.
            intent_type = 'smalltalk' if _looks_like_smalltalk(transcript) else 'brain_query'
        
        signals = _extract_signals(transcript.lower())
        query = _clean_query(transcript.lower(), project) if intent_type == 'architect_task' else transcript
        
        return Intent(
            type=intent_type,
            project=project,
            query=query,
            original=transcript,
            confidence=confidence,
            method='llm',
            signals=signals
        )
        
    except Exception as e:
        print(f"[Intent] LLM classification failed: {e}")
        return None


def _looks_like_smalltalk(text: str) -> bool:
    """
    Fast guard for short casual utterances.
    Used as a safe fallback when LLM output is malformed/unknown.
    """
    if not text:
        return False

    lowered = text.lower().strip()
    smalltalk_patterns = [
        r'^(hi|hey|hello|yo|sup|sasa|niaje)\b',
        r'\bhow are you\b',
        r'\bwhat\'?s up\b',
        r'\b(good morning|good night|good evening)\b',
        r'\b(you there|are you there|you awake|are you awake)\b',
        r'\b(i\'?m back|i am back|back again)\b',
    ]
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in smalltalk_patterns)


def _extract_signals(text: str) -> Dict[str, Any]:
    """Extract routing signals from text."""
    return {
        'explicit_cloud': any(phrase in text for phrase in [
            'use cloud', 'think hard', 'be thorough', 'deep analysis',
            'ask grok', 'use grok', 'grok', 'switch to cloud', 'ask cloud'
        ]),
        'explicit_local': any(phrase in text for phrase in [
            'use local', 'quick', 'fast', 'offline'
        ]),
        'urgent': any(phrase in text for phrase in [
            'urgent', 'asap', 'right now', 'immediately'
        ]),
    }


def _extract_project(text: str) -> Optional[str]:
    """
    Extract project name from text using aliases.
    
    Examples:
        "add a feature to the brain" → 'sage_brain'
        "fix a bug in flight review" → 'flight_review'
    """
    # Check for explicit "to/in/for PROJECT" patterns
    for alias, project_id in PROJECT_ALIASES.items():
        patterns = [
            rf'\bto\s+(the\s+)?{re.escape(alias)}\b',
            rf'\bin\s+(the\s+)?{re.escape(alias)}\b',
            rf'\bfor\s+(the\s+)?{re.escape(alias)}\b',
            rf'\b{re.escape(alias)}\s+project\b',
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return project_id
    
    # Check for standalone mentions
    for alias, project_id in PROJECT_ALIASES.items():
        if alias in text:
            return project_id
    
    # Default project
    return 'sage_brain'


def _clean_query(text: str, project: Optional[str]) -> str:
    """
    Remove project mentions and common filler words from query.
    
    This produces a cleaner query for the Architect.
    """
    result = text
    
    # Remove project targeting phrases
    for alias in PROJECT_ALIASES.keys():
        patterns = [
            rf'\bto\s+(the\s+)?{re.escape(alias)}\b',
            rf'\bin\s+(the\s+)?{re.escape(alias)}\b',
            rf'\bfor\s+(the\s+)?{re.escape(alias)}\b',
            rf'\b{re.escape(alias)}\s+project\b',
        ]
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Remove explicit routing phrases
    routing_phrases = [
        'use cloud', 'use local', 'think hard', 'be thorough',
        'quick', 'fast', 'offline'
    ]
    for phrase in routing_phrases:
        result = result.replace(phrase, '')
    
    # Clean up whitespace
    result = ' '.join(result.split())
    
    return result.strip()


def get_task_type_from_intent(intent: Intent) -> str:
    """
    Determine the task type from an architect intent.
    
    Returns:
        'plan', 'code', 'fix', or 'test'
    """
    q = intent.query.lower()
    
    if any(kw in q for kw in ['fix', 'bug', 'error', 'debug', 'repair']):
        return 'fix'
    if any(kw in q for kw in ['test', 'tests', 'coverage']):
        return 'test'
    if any(kw in q for kw in ['refactor', 'rewrite', 'implement', 'build', 'create']):
        return 'code'
    
    # Default to planning
    return 'plan'


# For testing
if __name__ == "__main__":
    test_cases = [
        # High confidence architect
        ("Add expense tracking feature to the brain", "architect_task", 0.85),
        ("Fix the bug in the state machine", "architect_task", 0.95),
        ("Refactor the routing module code", "architect_task", 0.95),

        # High confidence home control
        ("Turn off the lights", "home_control", 0.95),
        ("Set a timer for 10 minutes", "home_control", 0.90),
        ("What's the temperature?", "home_control", 0.90),

        # High confidence brain query
        ("How am I doing today?", "brain_query", 0.90),
        ("Tell me about my sleep patterns", "brain_query", 0.85),

        # Emotional support (should be high confidence, no LLM fallback)
        ("i miss my sister", "brain_query", 0.90),
        ("she died by suicide last year", "brain_query", 0.95),
        ("i'm feeling really sad today", "brain_query", 0.90),
        ("na bado sijaheal", "brain_query", 0.90),
        ("i lost my mom last month", "brain_query", 0.95),
        ("i'm struggling with anxiety", "brain_query", 0.85),
        ("can i tell you something", "brain_query", 0.90),

        # Conversation feedback (should be high confidence)
        ("thats a bit of a soulless response", "brain_query", 0.90),
        ("redo it with more soul", "brain_query", 0.90),
        ("be more human about it", "brain_query", 0.85),
        ("that didn't help", "brain_query", 0.85),

        # Ambiguous (should trigger LLM if enabled)
        ("Add that thing we talked about", "architect_task", 0.40),
        ("Yo hook up the tracking", "architect_task", 0.40),
        ("Make it better", "brain_query", 0.30),
    ]

    # Context-aware test cases
    print("\n" + "=" * 70)
    print("CONTEXT-AWARE INTENT CLASSIFICATION")
    print("=" * 70)

    emotional_ctx = {
        'mode': 'emotional',
        'mode_topic': 'grief',
        'emotional_mode': True,
        'turns_in_mode': 2,
        'recent_intents': ['brain_query', 'brain_query'],
        'turn_count': 3,
    }

    context_tests = [
        # In emotional context, short/ambiguous should stay as brain_query
        ("yeah", "brain_query", 0.85, emotional_ctx),
        ("tell me more", "brain_query", 0.85, emotional_ctx),
        ("okay", "brain_query", 0.85, emotional_ctx),
        ("i dont know", "brain_query", 0.85, emotional_ctx),
    ]

    for tc, expected_type, expected_conf, ctx in context_tests:
        intent = classify_intent(tc, use_llm_fallback=False, conversation_context=ctx)
        status = "✓" if intent.type == expected_type and intent.confidence >= expected_conf else "✗"
        print(f"\n{status} '{tc}' (in {ctx['mode']} mode)")
        print(f"  type={intent.type}, confidence={intent.confidence:.2f}, method={intent.method}")
        if intent.signals.get('context_biased'):
            print(f"  ✓ Context bias applied")
    
    print("=" * 70)
    print("INTENT CLASSIFIER TEST (Hybrid Mode)")
    print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}")
    print(f"LLM Fallback: {USE_LLM_FALLBACK}")
    print("=" * 70)
    
    for tc, expected_type, expected_min_conf in test_cases:
        # Test without LLM to see rule-based confidence
        intent = classify_intent(tc, use_llm_fallback=False)
        
        status = "✓" if intent.type == expected_type else "✗"
        llm_needed = "→ LLM" if intent.confidence < CONFIDENCE_THRESHOLD else ""
        
        print(f"\n{status} '{tc}'")
        print(f"  type={intent.type}, confidence={intent.confidence:.2f}, method={intent.method} {llm_needed}")
        print(f"  project={intent.project}, query='{intent.query[:40]}...'")
        
        if intent.type != expected_type:
            print(f"  ⚠️  Expected: {expected_type}")
