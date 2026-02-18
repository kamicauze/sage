"""
Unified Routing Logic
Shared between Brain and Architect for consistent model selection.

The routing decision is based on a composite score (0-15) from:
1. Keyword signals (complexity, persona)
2. RAG context size
3. Explicit user escalation phrases
4. Token estimate (large context needs)
"""
import hashlib
import os
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class RouteDecision:
    route: str          # LOCAL, HYBRID, CLOUD
    score: int          # 0-15
    reason: str
    provider: str       # ollama, google, anthropic, xai
    model: str          # gemma3:12b, gemini-1.5-pro, claude-3-opus, grok-beta
    task_type: str      # plan, code, chat, reflex


@dataclass
class CanaryConfig:
    enabled: bool = False
    percentage: int = 0
    model: Optional[str] = None
    routes: Optional[set] = None
    task_types: Optional[set] = None
    salt: str = "sage-canary-v1"


# Keyword weights for complexity detection
COMPLEXITY_KEYWORDS = {
    'refactor': 5,
    'architecture': 5,
    'design': 5,
    'rewrite': 5,
    'migration': 5,
    'redesign': 5,
    'overhaul': 5,
    'deploy': 2,
    'docker': 2,
    'ci': 2,
    'pipeline': 2,
    'kubernetes': 3,
    'security': 3,
    'auth': 2,
    'oauth': 3,
    'database': 2,
    'schema': 3,
}

# Keywords that suggest persona/creative tasks
PERSONA_KEYWORDS = {
    'sheng': 3,
    'personality': 3,
    'creative': 3,
    'poem': 3,
    'story': 3,
    'joke': 2,
    'roleplay': 3,
}

# Explicit user phrases to escalate/force routes
EXPLICIT_ESCALATION = {
    'think hard': 5,
    'use cloud': 5,
    'be thorough': 3,
    'take your time': 2,
    'deep analysis': 4,
    'carefully': 2,
}

EXPLICIT_LOCAL = {
    'use local': True,
    'quick': True,
    'fast': True,
    'offline': True,
}


class UnifiedRouter:
    """
    Determines optimal model route based on query complexity and context.

    Routes:
        LOCAL  (score < 4):  Free, fast, private (Ollama/Gemma3)
        HYBRID (score 4-7):  Balanced (Gemini for planning)
        CLOUD  (score >= 8): Full power (Claude for code, Grok for chat)

    Supports dynamic model loading from LLM registry (updated via `./sage update`).
    """

    def __init__(self, policy: Dict = None):
        if policy is None:
            policy = {}

        self.policy = policy
        self.thresholds = policy.get('routing_thresholds', {
            'hybrid_score': 4,
            'cloud_score': 8
        })

        # Try to load from dynamic registry first, fallback to config
        self.models = self._load_models(policy)
        self.canary = self._load_canary_config(policy)

    @staticmethod
    def _parse_bool(raw, default: bool = False) -> bool:
        if raw is None:
            return default
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_int(raw, default: int = 0) -> int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_set(raw, transform=str.upper) -> Optional[set]:
        if raw is None:
            return None
        if isinstance(raw, (list, tuple, set)):
            items = [str(x).strip() for x in raw if str(x).strip()]
        else:
            items = [part.strip() for part in str(raw).split(",") if part.strip()]
        if not items:
            return None
        return {transform(item) for item in items}

    def _load_models(self, policy: Dict) -> Dict:
        """
        Load model configuration with priority:
        1. LLM registry (from ./sage update)
        2. Policy config (from sage.yaml)
        3. Hardcoded defaults
        """
        import os
        import json

        # Check for dynamic registry
        registry_path = os.getenv("SAGE_LLM_REGISTRY_PATH")
        if not registry_path:
            try:
                from architect.paths import LLM_REGISTRY_FILE
                registry_path = str(LLM_REGISTRY_FILE)
            except Exception:
                registry_path = "architect/.cache/llm_registry.json"

        if os.path.exists(registry_path):
            try:
                with open(registry_path, 'r') as f:
                    registry = json.load(f)

                recommendations = registry.get('routing_recommendations', {})
                if recommendations:
                    # Map recommendations to model config format
                    models = {
                        'local': 'ollama/gemma3:12b',  # Always local
                    }

                    # Planning models
                    if 'planning' in recommendations:
                        models['plan_hybrid'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')
                        models['plan_cloud'] = recommendations['planning'].get('complex', 'google/gemini-1.5-pro')

                    # Code models
                    if 'code' in recommendations:
                        models['code_simple'] = recommendations['code'].get('simple', 'ollama/gemma3:12b')
                        models['code_medium'] = recommendations['code'].get('medium', 'anthropic/claude-sonnet-4.5')
                        models['code_cloud'] = recommendations['code'].get('complex', 'anthropic/claude-opus-4.5')

                    # Other models
                    if 'chat' in recommendations:
                        models['chat_cloud'] = recommendations['chat']
                    if 'testing' in recommendations:
                        models['testing'] = recommendations['testing']

                    return models
            except Exception as e:
                print(f"[Router] Warning: Failed to load registry: {e}")

        # Fallback to policy config
        return policy.get('models', {
            'local': 'ollama/gemma3:12b',
            'plan_hybrid': 'google/gemini-1.5-pro',
            'plan_cloud': 'google/gemini-1.5-pro',
            'code_cloud': 'anthropic/claude-opus-4.5',
            'chat_cloud': 'xai/grok-beta',
        })

    def _load_canary_config(self, policy: Dict) -> CanaryConfig:
        """
        Load canary routing config from policy and environment.

        Priority:
        1) policy["canary"]
        2) env vars
        3) defaults (disabled)
        """
        canary_policy = policy.get("canary", {})

        enabled = self._parse_bool(
            canary_policy.get("enabled", os.getenv("SAGE_CANARY_ENABLED")),
            default=False
        )
        percentage = self._parse_int(
            canary_policy.get("percentage", os.getenv("SAGE_CANARY_PERCENT", 0)),
            default=0
        )
        percentage = max(0, min(100, percentage))

        model = canary_policy.get("model") or os.getenv("SAGE_CANARY_MODEL")
        if model:
            model = str(model).strip()
        if not model:
            model = None

        routes = self._parse_set(
            canary_policy.get("routes", os.getenv("SAGE_CANARY_ROUTES", "LOCAL")),
            transform=str.upper
        )
        task_types = self._parse_set(
            canary_policy.get("task_types", os.getenv("SAGE_CANARY_TASK_TYPES")),
            transform=str.lower
        )

        salt = str(
            canary_policy.get("salt", os.getenv("SAGE_CANARY_SALT", "sage-canary-v1"))
        ).strip() or "sage-canary-v1"

        return CanaryConfig(
            enabled=enabled and model is not None and percentage > 0,
            percentage=percentage,
            model=model,
            routes=routes,
            task_types=task_types,
            salt=salt
        )

    @staticmethod
    def _parse_provider_model(full_model: str) -> tuple[str, str]:
        if "/" in full_model:
            return full_model.split("/", 1)
        return "ollama", full_model

    def _should_canary(self, query: str, task_type: str, route: str) -> bool:
        cfg = self.canary
        if not cfg.enabled:
            return False

        if cfg.routes and route.upper() not in cfg.routes:
            return False

        if cfg.task_types and task_type.lower() not in cfg.task_types:
            return False

        key = f"{cfg.salt}|{route.upper()}|{task_type.lower()}|{query.strip().lower()}"
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < cfg.percentage

    def score_keywords(self, query: str) -> int:
        """
        Score based on complexity/persona keywords.
        Takes the max complexity keyword (don't stack) + sum of persona keywords.
        """
        q = query.lower()
        
        # Complexity: take highest match (these are mutually exclusive complexity levels)
        complexity_score = 0
        for kw, weight in COMPLEXITY_KEYWORDS.items():
            if kw in q:
                complexity_score = max(complexity_score, weight)
        
        # Persona: additive (can have multiple persona signals)
        persona_score = 0
        for kw, weight in PERSONA_KEYWORDS.items():
            if kw in q:
                persona_score += weight
                
        return min(complexity_score + persona_score, 8)  # Cap at 8

    def score_context(self, rag_docs: List[str]) -> int:
        """
        Score based on RAG retrieval size.
        More retrieved docs = more context needed = potentially needs bigger model.
        """
        n = len(rag_docs) if rag_docs else 0
        
        if n > 20:
            return 5
        if n > 10:
            return 3
        if n > 5:
            return 2
        return 0

    def score_explicit(self, query: str) -> int:
        """
        Score based on explicit user escalation phrases.
        e.g., "think hard", "use cloud", "be thorough"
        """
        q = query.lower()
        
        for phrase, weight in EXPLICIT_ESCALATION.items():
            if phrase in q:
                return weight
        return 0

    def check_force_local(self, query: str) -> bool:
        """Check if user explicitly wants local processing."""
        q = query.lower()
        return any(phrase in q for phrase in EXPLICIT_LOCAL.keys())

    def score_token_estimate(self, query: str, rag_docs: List[str]) -> int:
        """
        Estimate if the task will need large context window.
        Large context benefits from cloud models with bigger windows.
        """
        docs = rag_docs or []
        total_chars = len(query) + sum(len(d) for d in docs)
        
        # Rough estimate: 4 chars ≈ 1 token
        est_tokens = total_chars // 4
        
        if est_tokens > 8000:
            return 2  # Needs large context → prefer cloud
        if est_tokens > 4000:
            return 1
        return 0

    def route(
        self,
        query: str,
        task_type: str,  # 'plan', 'code', 'chat', 'reflex'
        rag_docs: List[str] = None,
        force_local: bool = False
    ) -> RouteDecision:
        """
        Determine the optimal route for a request.
        
        Args:
            query: The user's request text
            task_type: Type of task (plan, code, chat, reflex)
            rag_docs: Retrieved context documents from RAG
            force_local: Override to always use local
            
        Returns:
            RouteDecision with route, model, and reasoning
        """
        if rag_docs is None:
            rag_docs = []

        # Check explicit local override
        if force_local or self.check_force_local(query):
            return self._build_decision(
                route="LOCAL",
                score=0,
                reason="Forced local (user request or flag)",
                task_type=task_type,
                query=query
            )

        # Calculate composite score
        kw_score = self.score_keywords(query)
        ctx_score = self.score_context(rag_docs)
        exp_score = self.score_explicit(query)
        tok_score = self.score_token_estimate(query, rag_docs)
        
        total = kw_score + ctx_score + exp_score + tok_score
        
        # Build reason string for debugging
        reason_parts = []
        if kw_score > 0:
            reason_parts.append(f"keywords={kw_score}")
        if ctx_score > 0:
            reason_parts.append(f"context={ctx_score}")
        if exp_score > 0:
            reason_parts.append(f"explicit={exp_score}")
        if tok_score > 0:
            reason_parts.append(f"tokens={tok_score}")
        
        # Determine route based on thresholds
        hybrid_th = self.thresholds['hybrid_score']
        cloud_th = self.thresholds['cloud_score']
        
        if total >= cloud_th:
            route = "CLOUD"
            reason = f"High complexity (score={total} >= {cloud_th}): {', '.join(reason_parts)}"
        elif total >= hybrid_th:
            route = "HYBRID"
            reason = f"Moderate complexity (score={total} >= {hybrid_th}): {', '.join(reason_parts)}"
        else:
            route = "LOCAL"
            reason = f"Simple task (score={total} < {hybrid_th})"

        return self._build_decision(route, total, reason, task_type, query=query)

    def _build_decision(
        self,
        route: str,
        score: int,
        reason: str,
        task_type: str,
        query: str
    ) -> RouteDecision:
        """Build the final decision with provider/model selection."""
        
        # Select model based on route and task type
        if route == "LOCAL":
            full_model = self.models.get('local', 'ollama/gemma3:12b')
            
        elif route == "HYBRID":
            # Hybrid: use cloud for planning, medium model for code
            if task_type in ('plan', 'design'):
                full_model = self.models.get('plan_hybrid', 'google/gemini-1.5-pro')
            elif task_type == 'code':
                # Use medium-tier model (Sonnet) for moderate complexity code
                full_model = self.models.get('code_medium', 'anthropic/claude-sonnet-4.5')
            else:
                full_model = self.models.get('local', 'ollama/gemma3:12b')

        else:  # CLOUD
            if task_type == 'code':
                full_model = self.models.get('code_cloud', 'anthropic/claude-opus-4.5')
            elif task_type == 'chat':
                full_model = self.models.get('chat_cloud', 'xai/grok-beta')
            else:
                full_model = self.models.get('plan_cloud', 'google/gemini-1.5-pro')

        provider, model = self._parse_provider_model(full_model)

        # Canary override: route a stable percentage to a candidate model.
        if self._should_canary(query=query, task_type=task_type, route=route):
            canary_provider, canary_model = self._parse_provider_model(self.canary.model or "")
            provider, model = canary_provider, canary_model
            reason = (
                f"{reason} | canary override: {self.canary.percentage}% -> {provider}/{model}"
            )

        return RouteDecision(
            route=route,
            score=score,
            reason=reason,
            provider=provider,
            model=model,
            task_type=task_type
        )


# Convenience function for quick routing
def quick_route(query: str, task_type: str = 'chat', policy: Dict = None) -> RouteDecision:
    """
    Quick routing without RAG context.
    Useful for simple intent-based routing.
    """
    router = UnifiedRouter(policy)
    return router.route(query, task_type)
