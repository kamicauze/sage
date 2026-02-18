"""
The Architect's Router
Entry point for the "Conscious Creator".

It listens for 'BuildRequests' (files/queues), processes them,
and produces 'BuildResults'. It does NOT run 24/7 loops.
"""
import sys
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path

sys.path.append(os.getcwd())
from architect.memory import ArchitectMemory
from architect.manifest import ProjectManifest
from architect.llm import LLMClient
from architect.builder import ArchitectBuilder
from architect.tester import ArchitectTester
from architect.logging_utils import correlation_context, generate_correlation_id, log_event
from architect.paths import (
    workspace_plan_path,
    prompt_path,
    project_manifest_path,
    root_relative,
)

@dataclass
class BuildRequest:
    manifest_path: str # Path to sage.yaml
    request_type: str  # 'feature', 'bugfix', 'refactor'
    query: str         # "Add expense tracking"
    context: Dict[str, Any] = None
    correlation_id: str | None = None


@dataclass
class BuildResult:
    status: str
    artifacts: list
    summary: str
    details: Dict[str, Any] = None

class ArchitectRouter:

    def __init__(self, interactive: bool = False, lazy_memory: bool = True):
        print("[Architect] Online. Connected to Gemma 3.")
        self.llm = LLMClient()
        self._memory = None  # Lazy initialization
        self.lazy_memory = lazy_memory
        self.interactive = interactive
        log_event(
            "router",
            "initialized",
            interactive=interactive,
            lazy_memory=lazy_memory,
        )

    @property
    def memory(self):
        """Lazy-load memory only when accessed."""
        if self._memory is None:
            self._memory = ArchitectMemory()
        return self._memory

    def _prompt_user(self, question: str, default: str = "y") -> bool:
        """Prompt user for yes/no confirmation in interactive mode."""
        if not self.interactive:
            return True  # Auto-approve in batch mode

        valid_yes = ["y", "yes"]
        valid_no = ["n", "no"]

        while True:
            response = input(f"{question} [y/n] (default: {default}): ").strip().lower()
            if not response:
                response = default

            if response in valid_yes:
                return True
            elif response in valid_no:
                return False
            else:
                print("Please enter 'y' or 'n'")

    def _create_builder(self, manifest: ProjectManifest, correlation_id: str) -> ArchitectBuilder:
        """
        Create a builder while remaining compatible with older/test doubles that
        do not yet accept `correlation_id` in the constructor.
        """
        try:
            return ArchitectBuilder(
                manifest,
                interactive=self.interactive,
                correlation_id=correlation_id,
            )
        except TypeError as exc:
            if "correlation_id" not in str(exc):
                raise
            log_event(
                "router",
                "builder_missing_correlation_id_support",
                level="warning",
                correlation_id=correlation_id,
                project_id=manifest.id,
                error=str(exc),
            )
            return ArchitectBuilder(
                manifest,
                interactive=self.interactive,
            )

    def process_request(self, request: BuildRequest) -> BuildResult:
        correlation_id = request.correlation_id or generate_correlation_id("build")
        request.correlation_id = correlation_id

        with correlation_context(correlation_id):
            log_event(
                "router",
                "request_received",
                request_type=request.request_type,
                manifest_path=request.manifest_path,
                has_context=request.context is not None,
            )
            return self._process_request_with_context(request, correlation_id)

    def _process_request_with_context(self, request: BuildRequest, correlation_id: str) -> BuildResult:
        print(f"[Architect] Analyizing request for manifest: '{request.manifest_path}'")
        
        # 1. Load Manifest
        try:
            manifest = ProjectManifest.load(request.manifest_path)
            print(f"[Architect] Project Parsed: {manifest.name}")
            log_event(
                "router",
                "manifest_loaded",
                correlation_id=correlation_id,
                project_id=manifest.id,
                manifest_path=request.manifest_path,
            )
        except Exception as e:
            log_event(
                "router",
                "manifest_load_failed",
                level="error",
                correlation_id=correlation_id,
                manifest_path=request.manifest_path,
                error=str(e),
            )
            return BuildResult(
                "FAILURE",
                [],
                f"Invalid manifest: {e}",
                details={"correlation_id": correlation_id},
            )

        # --- BRANCH: BUILD vs PLAN ---
        if request.request_type == "build":
            print("[Architect] Entering BUILD mode...")
            log_event(
                "router",
                "build_mode_started",
                correlation_id=correlation_id,
                project_id=manifest.id,
            )
            builder = self._create_builder(manifest, correlation_id)
            tester = ArchitectTester(builder.sandbox_dir)
            started_at = datetime.now(timezone.utc)
            started_monotonic = time.monotonic()
            
            # Assuming Plan exists
            plan_path = workspace_plan_path(manifest.id)
            if not plan_path.exists():
                log_event(
                    "router",
                    "build_plan_missing",
                    level="warning",
                    correlation_id=correlation_id,
                    project_id=manifest.id,
                    plan_path=root_relative(plan_path),
                )
                return BuildResult(
                    "FAILURE",
                    [],
                    f"Plan not found at {root_relative(plan_path)}",
                    details={"correlation_id": correlation_id},
                )
            
            try:
                # 1. Build Code
                builder.build_from_plan(str(plan_path))

                # 2. Selective Test Generation - Only for files that were actually built
                # Use builder.files_built from Phase 2 file change tracking
                print(f"[Architect] Generating tests for {len(builder.files_built)} modified files...")

                built_files = [f for f in builder.files_built if f.endswith(".py")]

                generated_tests = []
                if not built_files:
                    print("[Architect] No Python files built, skipping test generation.")
                else:
                    for f in built_files:
                        test_path = builder.generate_tests(f)
                        if test_path:
                            generated_tests.append(test_path)
                    
                # 3. Test & Fix Loop
                max_retries = 3
                attempts = []
                details = {
                    "project_id": manifest.id,
                    "correlation_id": correlation_id,
                    "plan_path": root_relative(plan_path),
                    "sandbox_dir": root_relative(Path(builder.sandbox_dir)),
                    "files": {
                        "planned": builder.files_planned,
                        "built": builder.files_built,
                        "skipped": builder.files_skipped,
                        "failed": builder.files_failed,
                    },
                    "tests": {
                        "generated": generated_tests,
                        "attempts": attempts,
                        "max_retries": max_retries,
                        "passed": False,
                    },
                }
                for attempt in range(max_retries):
                    print(f"\n[Architect] Testing Cycle {attempt+1}/{max_retries}...")
                    log_event(
                        "router",
                        "test_cycle_started",
                        correlation_id=correlation_id,
                        project_id=manifest.id,
                        cycle=attempt + 1,
                        max_retries=max_retries,
                    )
                    result = tester.run_tests()
                    attempts.append({
                        "cycle": attempt + 1,
                        "passed": result.passed,
                        "failed_tests": result.failed_tests or [],
                        "error": result.error,
                    })
                    
                    if result.passed:
                        print("✅ All Tests Passed!")
                        log_event(
                            "router",
                            "build_succeeded",
                            correlation_id=correlation_id,
                            project_id=manifest.id,
                            built_count=len(builder.files_built),
                            skipped_count=len(builder.files_skipped),
                            failed_count=len(builder.files_failed),
                        )
                        details["tests"]["passed"] = True
                        ended_at = datetime.now(timezone.utc)
                        details["timing"] = {
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                        }
                        return BuildResult(
                            "SUCCESS",
                            [root_relative(plan_path)],
                            "Build & Tests Passed.",
                            details=details,
                        )
                    
                    print(f"❌ Tests Failed: {result.failed_tests}")
                    log_event(
                        "router",
                        "test_cycle_failed",
                        level="warning",
                        correlation_id=correlation_id,
                        project_id=manifest.id,
                        cycle=attempt + 1,
                        failed_tests=result.failed_tests or [],
                    )
                    # Attempt Self-Repair
                    if result.failed_tests:
                        # Map test name (test_foo.py) back to source (foo.py) is hard without structure.
                        # We'll just try to fix the files we know we built, filtering by error log.
                        for f in built_files:
                            builder.fix_code(f, result.output)
                ended_at = datetime.now(timezone.utc)
                details["timing"] = {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                }
                details["failure_reason"] = "tests_failed_after_max_retries"
                log_event(
                    "router",
                    "build_failed_max_retries",
                    level="error",
                    correlation_id=correlation_id,
                    project_id=manifest.id,
                    failed_tests=details["tests"]["attempts"],
                )
                return BuildResult("FAILURE", [], "Tests failed after max retries.", details=details)

            except Exception as e:
                ended_at = datetime.now(timezone.utc)
                details = {
                    "project_id": manifest.id,
                    "correlation_id": correlation_id,
                    "plan_path": root_relative(plan_path),
                    "sandbox_dir": root_relative(Path(builder.sandbox_dir)),
                    "files": {
                        "planned": getattr(builder, "files_planned", []),
                        "built": getattr(builder, "files_built", []),
                        "skipped": getattr(builder, "files_skipped", []),
                        "failed": getattr(builder, "files_failed", []),
                    },
                    "tests": {
                        "generated": [],
                        "attempts": [],
                        "max_retries": 3,
                        "passed": False,
                    },
                    "timing": {
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": int((time.monotonic() - started_monotonic) * 1000),
                    },
                    "failure_reason": "exception_during_build_or_test",
                    "exception": str(e),
                }
                log_event(
                    "router",
                    "build_exception",
                    level="error",
                    correlation_id=correlation_id,
                    project_id=manifest.id,
                    error=str(e),
                )
                return BuildResult("FAILURE", [], f"Build/Test failed: {e}", details=details)
        
        # --- BRANCH: PLAN (Default) ---
        plan_started_at = datetime.now(timezone.utc)
        plan_started_monotonic = time.monotonic()

        # --- ROUTING DECISION (Do this BEFORE expensive RAG) ---
        from architect.router_logic import RouterScorer
        scorer = RouterScorer(manifest.policy)
        # Quick preliminary score without context to decide if we need RAG
        preliminary_decision = scorer.determine_route(request.query, "plan", context_files=[])

        # Lazy Context Loading: Only fetch RAG if score >= 4 (needs code context)
        context_snippets = []
        joined_context = ""

        if preliminary_decision.score >= 4:
            # 2. RAG Retrieval (Recall Phase) - Only for complex tasks
            print("[Architect] Recalling relevant context from Memory...")
            log_event(
                "router",
                "memory_context_requested",
                correlation_id=correlation_id,
                project_id=manifest.id,
                query=request.query,
            )
            try:
                results = self.memory.query(manifest.id, request.query, n_results=3)
            except Exception as e:
                print(f"[Architect] Memory unavailable, continuing without RAG context: {e}")
                results = {"documents": [], "metadatas": []}
                log_event(
                    "router",
                    "memory_context_unavailable",
                    level="warning",
                    correlation_id=correlation_id,
                    project_id=manifest.id,
                    error=str(e),
                )

            if results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    context_snippets.append(f"File: {meta['source']} (Zone: {meta['zone_name']})\nContent:\n{doc}...")

            joined_context = "\n\n".join(context_snippets)
            print(f"[Architect] Retrieved {len(context_snippets)} snippets.")
            log_event(
                "router",
                "memory_context_retrieved",
                correlation_id=correlation_id,
                project_id=manifest.id,
                snippet_count=len(context_snippets),
            )

            # Re-score with context
            decision = scorer.determine_route(request.query, "plan", context_files=context_snippets)
        else:
            # Skip RAG for simple tasks
            print("[Architect] Skipping context retrieval (simple task)")
            decision = preliminary_decision

        print(f"[Router] Decision: {decision.route} (Score: {decision.score}). Reason: {decision.reason}")
        print(f"[Router] Selected Model: {decision.provider}/{decision.model}")
        log_event(
            "router",
            "routing_decision",
            correlation_id=correlation_id,
            project_id=manifest.id,
            route=decision.route,
            score=decision.score,
            provider=decision.provider,
            model=decision.model,
            reason=decision.reason,
        )
        
        # Approval Gate for Cloud if needed
        # (For interactive CLI, we might prompt here, but for now we log it)
        # In a real tool: if decision.route == "CLOUD" and not request.approved: ask_user()

        # 3. Augment Prompt
        with open(prompt_path("planning.txt"), "r") as f:
            system_prompt = f.read()
            
        user_prompt = f"""
        PROJECT: {manifest.name}
        QUERY: {request.query}
        
        RELEVANT CODE CONTEXT:
        {joined_context}
        
        Please draft an Implementation Plan.
        """
        
        # 4. Generate (Plan Phase)
        print(f"[Architect] Asking {decision.provider}/{decision.model} to draft a plan...")
        plan_content = self.llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], provider=decision.provider, model=decision.model)
        
        # 5. Output
        output_file = workspace_plan_path(manifest.id)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            f.write(plan_content)

        output_file_rel = root_relative(output_file)
        print(f"[Architect] Plan saved to {output_file_rel}")

        plan_details = {
            "project_id": manifest.id,
            "correlation_id": correlation_id,
            "plan_path": output_file_rel,
            "routing": {
                "route": decision.route,
                "score": decision.score,
                "provider": decision.provider,
                "model": decision.model,
            },
            "context_snippet_count": len(context_snippets),
            "timing": {
                "started_at": plan_started_at.isoformat(),
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": int((time.monotonic() - plan_started_monotonic) * 1000),
            },
        }
        log_event(
            "router",
            "plan_saved",
            correlation_id=correlation_id,
            project_id=manifest.id,
            plan_path=output_file_rel,
            route=decision.route,
            duration_ms=plan_details["timing"]["duration_ms"],
        )

        # Interactive: Show plan and ask for approval
        if self.interactive:
            print("\n" + "="*60)
            print("GENERATED PLAN:")
            print("="*60)
            # Show first 1000 chars of plan
            preview = plan_content[:1000] + ("..." if len(plan_content) > 1000 else "")
            print(preview)
            print("="*60)
            print(f"\nFull plan saved to: {output_file_rel}")

            if not self._prompt_user("\nProceed with this plan?", default="y"):
                return BuildResult(
                    status="CANCELLED",
                    artifacts=[output_file_rel],
                    summary="Plan cancelled by user.",
                    details=plan_details,
                )

        return BuildResult(
            status="SUCCESS",
            artifacts=[output_file_rel],
            summary=f"Drafted plan for '{request.query}' using {decision.route} route.",
            details=plan_details,
        )

if __name__ == "__main__":
    # Test run
    import sys
    
    # Mode switch
    mode = "plan"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    req = BuildRequest(
        manifest_path=root_relative(project_manifest_path("sage")),
        request_type=mode, # 'plan' or 'build'
        query="Add a new pattern for 'Gaming Mode' where if screen is active and user is reclined for > 2 hours, we suggest a stretch."
    )
    
    router = ArchitectRouter()
    res = router.process_request(req)
    print(res.summary)
