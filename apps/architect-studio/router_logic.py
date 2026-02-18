"""
The Deterministic Router Logic
Decides: LOCAL | HYBRID | CLOUD
Based on: Score (0-15) from keywords, context, and explicit signals.

This module wraps the shared/routing.py UnifiedRouter for backward compatibility.
"""
import sys
import os
from typing import List

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.routing import UnifiedRouter, RouteDecision

# Re-export RouteDecision for backward compatibility
__all__ = ['RouteDecision', 'RouterScorer']


class RouterScorer:
    """
    Wrapper around UnifiedRouter for Architect compatibility.
    
    This maintains the existing API while using the shared routing logic.
    """
    
    def __init__(self, manifest_policy):
        self.policy = manifest_policy
        self.thresholds = manifest_policy.get('routing_thresholds', {
            'hybrid_score': 4,
            'cloud_score': 8
        })
        self.models = manifest_policy.get('models', {})
        
        # Build policy dict for UnifiedRouter
        unified_policy = {
            'routing_thresholds': self.thresholds,
            'models': {
                'local': self.models.get('plan_local', 'ollama/gemma3:12b'),
                'plan_hybrid': self.models.get('plan_deep', 'google/gemini-1.5-pro'),
                'plan_cloud': self.models.get('plan_deep', 'google/gemini-1.5-pro'),
                'code_cloud': self.models.get('code_cloud', 'anthropic/claude-3-opus'),
                'chat_cloud': self.models.get('chat_cloud', 'xai/grok-beta'),
            }
        }
        
        self._router = UnifiedRouter(unified_policy)

    def score_request(self, query: str, context_files: List[str]) -> int:
        """
        Score a request based on keywords and context.
        Delegates to UnifiedRouter's scoring methods.
        """
        kw_score = self._router.score_keywords(query)
        ctx_score = self._router.score_context(context_files)
        exp_score = self._router.score_explicit(query)
        tok_score = self._router.score_token_estimate(query, context_files)
        
        return kw_score + ctx_score + exp_score + tok_score

    def determine_route(
        self,
        query: str,
        task_type: str,
        context_files: List[str] = None
    ) -> RouteDecision:
        """
        Determine the optimal route for a request.
        
        Args:
            query: The user's request text
            task_type: 'plan', 'code', 'chat', etc.
            context_files: RAG-retrieved context documents
            
        Returns:
            RouteDecision with route, model, provider, and reasoning
        """
        if context_files is None:
            context_files = []
            
        return self._router.route(
            query=query,
            task_type=task_type,
            rag_docs=context_files
        )
