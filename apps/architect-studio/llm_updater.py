"""
LLM Model Updater
Uses web research + AI to discover latest models, pricing, and capabilities.
Triggered manually via `./sage update` to refresh routing configuration.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from architect.paths import (
    LLM_REGISTRY_FILE,
    project_manifest_path,
)

@dataclass
class ModelInfo:
    """Information about an LLM model."""
    name: str
    provider: str
    input_cost: float  # $ per 1M tokens
    output_cost: float  # $ per 1M tokens
    context_window: int  # tokens
    capabilities: List[str]  # ['code', 'chat', 'planning', 'reasoning']
    speed: str  # 'fast', 'medium', 'slow'
    quality: str  # 'high', 'medium', 'low'

class LLMUpdater:
    """
    Researches and updates LLM model registry.
    Uses Sage's own routing system to research itself!
    """

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = str(LLM_REGISTRY_FILE)
        self.config_path = config_path
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict:
        """Load existing registry or create new one."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "last_updated": None,
            "models": {},
            "routing_recommendations": {}
        }

    def _save_registry(self):
        """Save registry to disk."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def research_provider(self, provider: str) -> List[ModelInfo]:
        """
        Fetch latest pricing for a provider.

        For now, uses hardcoded current pricing (as of Jan 2026).
        TODO: Add real web scraping when providers update pricing.
        """
        print(f"\n[Updater] Loading {provider} models...")

        # Current pricing as of January 2026
        pricing_db = {
            "anthropic": [
                ModelInfo("claude-opus-4.5", "anthropic", 5.0, 25.0, 200000,
                         ["code", "reasoning", "chat"], "medium", "high"),
                ModelInfo("claude-sonnet-4.5", "anthropic", 3.0, 15.0, 200000,
                         ["code", "reasoning", "chat"], "fast", "high"),
                ModelInfo("claude-haiku-4.5", "anthropic", 1.0, 5.0, 200000,
                         ["code", "chat"], "fast", "medium"),
            ],
            "openai": [
                ModelInfo("gpt-4o", "openai", 2.5, 10.0, 128000,
                         ["code", "reasoning", "chat"], "medium", "high"),
                ModelInfo("gpt-4o-mini", "openai", 0.15, 0.6, 128000,
                         ["chat", "code"], "fast", "medium"),
            ],
            "google": [
                ModelInfo("gemini-1.5-pro", "google", 1.25, 5.0, 1000000,
                         ["reasoning", "planning", "code"], "medium", "high"),
                ModelInfo("gemini-1.5-flash", "google", 0.075, 0.3, 1000000,
                         ["chat", "code"], "fast", "medium"),
            ],
            "xai": [
                ModelInfo("grok-beta", "xai", 5.0, 15.0, 131072,
                         ["chat", "reasoning"], "medium", "high"),
            ]
        }

        models = pricing_db.get(provider, [])
        print(f"[Updater] Found {len(models)} models for {provider}")
        return models

    def analyze_routing_strategy(self, all_models: List[ModelInfo]) -> Dict:
        """
        Use LLM to analyze all models and recommend routing strategy.

        This is the key intelligence: Sage analyzes cost/quality tradeoffs
        and recommends which model for which task.
        """
        from architect.llm import LLMClient

        print("\n[Updater] Analyzing optimal routing strategy...")

        llm = LLMClient()

        # Build model summary (handle None values)
        model_summary = "\n".join([
            f"- {m.provider}/{m.name}: "
            f"${m.input_cost or '?'}/${m.output_cost or '?'} per 1M, "
            f"{(m.context_window/1000) if m.context_window else '?'}K context, "
            f"{m.quality or 'unknown'} quality, {m.speed or 'unknown'} speed, "
            f"capabilities: {', '.join(m.capabilities) if m.capabilities else 'unknown'}"
            for m in all_models
        ])

        analysis_prompt = f"""
        You are a budget-conscious AI system optimizer. Analyze these available LLM models
        and recommend the optimal routing strategy for a $120/month budget.

        Available models:
        {model_summary}

        Task types to optimize for:
        1. **Planning** (architecture, design docs): Needs good reasoning, large context
        2. **Code Generation** (implementation): Needs high code quality
        3. **Code Editing** (surgical edits): Needs precision, can be fast
        4. **Chat/Personality** (user interaction): Needs creativity
        5. **Testing** (test generation): Can be lower quality
        6. **Bug Fixing** (error correction): Needs reasoning

        Provide routing recommendations that:
        - Minimize cost while maintaining quality
        - Use free local models (ollama) for simple/repetitive tasks
        - Reserve expensive models for complex/critical tasks
        - Consider speed/latency for user experience

        Return ONLY valid JSON (no markdown):
        {{
          "routing": {{
            "planning": {{
              "simple": "provider/model",
              "complex": "provider/model"
            }},
            "code": {{
              "simple": "provider/model",
              "medium": "provider/model",
              "complex": "provider/model"
            }},
            "chat": "provider/model",
            "testing": "provider/model"
          }},
          "reasoning": "Brief explanation of strategy",
          "estimated_monthly_cost": 45.0,
          "budget_breakdown": {{
            "planning": 15.0,
            "code": 25.0,
            "chat": 5.0
          }}
        }}
        """

        # Use CLOUD for this analysis (it's important and one-time)
        try:
            response = llm.chat([
                {"role": "user", "content": analysis_prompt}
            ], provider="google", model="gemini-1.5-pro")

            # Parse response
            response = response.strip()
            if response.startswith("```"):
                response = "\n".join(response.split("\n")[1:-1])

            strategy = json.loads(response)

            print(f"[Updater] Strategy analysis complete")
            print(f"[Updater] Estimated monthly cost: ${strategy.get('estimated_monthly_cost', 'unknown')}")
            print(f"[Updater] Reasoning: {strategy.get('reasoning', 'N/A')[:100]}...")

            return strategy

        except Exception as e:
            print(f"[Updater] Strategy analysis failed: {e}")
            return {}

    def update_all(self) -> Dict:
        """
        Full update cycle:
        1. Research all providers
        2. Analyze optimal routing
        3. Update registry
        4. Return summary
        """
        print("="*60)
        print("SAGE LLM MODEL UPDATE")
        print("="*60)

        providers = ["anthropic", "openai", "google"]
        all_models = []

        # Research each provider
        for provider in providers:
            models = self.research_provider(provider)
            all_models.extend(models)

        # Add local models (no research needed)
        all_models.append(ModelInfo(
            name="gemma3:12b",
            provider="ollama",
            input_cost=0.0,
            output_cost=0.0,
            context_window=8192,
            capabilities=["code", "chat", "planning"],
            speed="fast",
            quality="medium"
        ))

        if not all_models:
            print("[Updater] No models found. Update failed.")
            return {"status": "failed", "reason": "No models discovered"}

        # Analyze routing strategy
        strategy = self.analyze_routing_strategy(all_models)

        # Update registry
        self.registry = {
            "last_updated": datetime.now().isoformat(),
            "models": {
                f"{m.provider}/{m.name}": asdict(m)
                for m in all_models
            },
            "routing_recommendations": strategy.get("routing", {}),
            "budget_estimate": strategy.get("estimated_monthly_cost", None),
            "reasoning": strategy.get("reasoning", "")
        }

        self._save_registry()

        print("\n" + "="*60)
        print("UPDATE COMPLETE")
        print("="*60)
        print(f"Models discovered: {len(all_models)}")
        print(f"Registry saved to: {self.config_path}")
        print(f"Estimated monthly cost: ${self.registry.get('budget_estimate', 'unknown')}")

        return {
            "status": "success",
            "models_found": len(all_models),
            "registry_path": self.config_path,
            "recommendations": strategy
        }

    def apply_recommendations(self, target_file=None):
        """
        Apply routing recommendations to project config.
        Updates sage.yaml with new model selections.
        """
        if target_file is None:
            target_file = str(project_manifest_path("sage"))

        if not self.registry.get("routing_recommendations"):
            print("[Updater] No recommendations to apply. Run update first.")
            return

        print(f"\n[Updater] Applying recommendations to {target_file}...")

        recommendations = self.registry["routing_recommendations"]

        # Load current config
        try:
            import yaml
        except ImportError:
            print("[Updater] Error: PyYAML not installed. Run: pip install pyyaml")
            return

        with open(target_file, 'r') as f:
            config = yaml.safe_load(f)

        # Update model selections
        if "policy" not in config:
            config["policy"] = {}
        if "models" not in config["policy"]:
            config["policy"]["models"] = {}

        # Map recommendations to config format
        models = config["policy"]["models"]

        # Planning models
        if "planning" in recommendations:
            models["plan_local"] = recommendations["planning"].get("simple", "ollama/gemma3:12b")
            models["plan_deep"] = recommendations["planning"].get("complex", "google/gemini-1.5-pro")

        # Code models
        if "code" in recommendations:
            models["code_simple"] = recommendations["code"].get("simple", "ollama/gemma3:12b")
            models["code_cloud"] = recommendations["code"].get("complex", "anthropic/claude-opus-4.5")

        # Chat/other
        if "chat" in recommendations:
            models["chat_cloud"] = recommendations["chat"]
        if "testing" in recommendations:
            models["testing"] = recommendations["testing"]

        # Update pricing data
        if "ai_budget" not in config["policy"]:
            config["policy"]["ai_budget"] = {}

        provider_rates = {}
        for model_key, model_info in self.registry["models"].items():
            provider_rates[model_key] = {
                "input": model_info["input_cost"],
                "output": model_info["output_cost"]
            }

        config["policy"]["ai_budget"]["provider_rates"] = provider_rates

        # Save updated config
        with open(target_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"[Updater] Config updated: {target_file}")
        print("[Updater] New model selections:")
        for key, value in models.items():
            print(f"  - {key}: {value}")

if __name__ == "__main__":
    # Test run
    updater = LLMUpdater()
    result = updater.update_all()

    if result["status"] == "success":
        # Show user the recommendations
        print("\n" + "="*60)
        print("RECOMMENDATIONS")
        print("="*60)

        routing = result["recommendations"].get("routing", {})
        print(json.dumps(routing, indent=2))

        # Ask to apply
        response = input("\nApply these recommendations to sage.yaml? [y/n]: ").strip().lower()
        if response == 'y':
            updater.apply_recommendations()
