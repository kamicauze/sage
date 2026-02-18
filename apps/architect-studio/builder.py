"""
The Builder
Parses implementation plans and generates code files using the LLM.
"""
import os
import re
import json
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from architect.llm import LLMClient
from architect.manifest import ProjectManifest
from architect.diff_viewer import DiffViewer
from architect.logging_utils import log_event
from architect.paths import workspace_dir, workspace_sandbox_path, prompt_path
from shared.routing import quick_route

class BuildCache:
    """
    Tracks per-file build signatures to enable true incremental builds.
    A file is skipped only when:
    1) The current input signature matches cached input signature, and
    2) The expected sandbox output still exists and matches its cached hash.
    """
    def __init__(self, project_id: str):
        self.cache_file = str(workspace_dir(project_id) / "build_cache.json")
        self._lock = threading.Lock()
        self.cache = self._load()

    def _load(self):
        """Load cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        """Save cache to disk."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def _hash_content(self, content: str) -> str:
        """Generate SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _hash_file(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return self._hash_content(f.read())

    def _get_entry(self, target_path: str):
        with self._lock:
            entry = self.cache.get(target_path)
        if isinstance(entry, dict):
            return entry
        # Legacy cache format fallback (string hash) => treat as cache miss.
        return {}

    def _build_input_signature(self, target_path: str, plan_content: str, file_info: dict, existing_content: str, file_exists: bool) -> str:
        """
        Build a stable signature for current generation inputs.
        If this signature is unchanged, regeneration is unnecessary.
        """
        plan_hash = self._hash_content(plan_content)
        source_hash = self._hash_content(existing_content) if file_exists else "MISSING"
        payload = {
            "target_path": target_path,
            "plan_hash": plan_hash,
            "file_info": file_info or {},
            "source_exists": file_exists,
            "source_hash": source_hash,
        }
        return self._hash_content(json.dumps(payload, sort_keys=True, ensure_ascii=False))

    def should_skip(self, target_path: str, input_signature: str, sandbox_path: str) -> bool:
        """
        Returns True if cached inputs match and sandbox output is still valid.
        """
        entry = self._get_entry(target_path)
        if not entry:
            return False

        if entry.get("input_signature") != input_signature:
            return False

        if not os.path.exists(sandbox_path):
            return False

        expected_output_hash = entry.get("output_hash")
        if expected_output_hash:
            try:
                current_output_hash = self._hash_file(sandbox_path)
            except Exception:
                return False
            if current_output_hash != expected_output_hash:
                return False

        return True

    def update(self, target_path: str, input_signature: str, output_content: str):
        """Update cache entry after generation."""
        entry = {
            "input_signature": input_signature,
            "output_hash": self._hash_content(output_content),
            "updated_at": int(time.time()),
        }
        with self._lock:
            self.cache[target_path] = entry
            self._save()

class ArchitectBuilder:
    def __init__(
        self,
        manifest: ProjectManifest,
        interactive: bool = False,
        incremental: bool = True,
        parallel: bool = True,
        max_workers: int = 3,
        stream: bool = False,
        correlation_id: str | None = None,
    ):
        self.manifest = manifest
        self.llm = LLMClient()
        self.sandbox_dir = str(workspace_sandbox_path(manifest.id))
        self.interactive = interactive
        self.incremental = incremental
        self.parallel = parallel and not interactive  # Disable parallel in interactive mode
        self.max_workers = max_workers
        self.stream = stream and not parallel  # Streaming only works in sequential mode
        self.diff_viewer = DiffViewer() if interactive else None
        self.build_cache = BuildCache(manifest.id) if incremental else None
        self.files_planned = []
        self.files_built = []  # Track which files were actually generated
        self.files_skipped = []  # List[{"path": str, "reason": str}]
        self.files_failed = []  # List[{"path": str, "error": str}]
        self.correlation_id = correlation_id
        log_event(
            "builder",
            "initialized",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            sandbox_dir=self.sandbox_dir,
            interactive=self.interactive,
            incremental=self.incremental,
            parallel=self.parallel,
        )

    def _correlation_id(self) -> str | None:
        return getattr(self, "correlation_id", None)

    def _project_id(self) -> str | None:
        manifest = getattr(self, "manifest", None)
        return getattr(manifest, "id", None)

    def build_from_plan(self, plan_path: str):
        print(f"[Builder] Reading plan from {plan_path}...")
        log_event(
            "builder",
            "build_from_plan_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            plan_path=plan_path,
        )

        with open(plan_path, "r") as f:
            plan_content = f.read()

        # Strategy: Ask LLM to convert Plan -> JSON list of files first (safer)
        files_to_edit = self._extract_file_list(plan_content)
        self.files_planned = [
            os.path.normpath(item.get("path", ""))
            for item in files_to_edit
            if item.get("path")
        ]
        self.files_built = []
        self.files_skipped = []
        self.files_failed = []

        print(f"[Builder] Found {len(files_to_edit)} files to build.")
        log_event(
            "builder",
            "plan_parsed",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            file_count=len(files_to_edit),
        )

        if self.parallel and len(files_to_edit) > 1:
            # Parallel generation for multiple files
            self._build_parallel(files_to_edit, plan_content)
        else:
            # Sequential generation (interactive mode or single file)
            for file_info in files_to_edit:
                self._generate_file(file_info, plan_content)

        log_event(
            "builder",
            "build_from_plan_completed",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            planned_count=len(self.files_planned),
            built_count=len(self.files_built),
            skipped_count=len(self.files_skipped),
            failed_count=len(self.files_failed),
        )

    def _build_parallel(self, files_to_edit, plan_content):
        """Generate multiple files in parallel using ThreadPoolExecutor."""
        print(f"[Builder] Using parallel generation with {self.max_workers} workers...")
        log_event(
            "builder",
            "parallel_generation_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            workers=self.max_workers,
            file_count=len(files_to_edit),
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all file generation tasks
            future_to_file = {
                executor.submit(self._generate_file, file_info, plan_content): file_info
                for file_info in files_to_edit
            }

            # Process results as they complete
            completed = 0
            total = len(files_to_edit)
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                completed += 1
                try:
                    future.result()
                    print(f"[Builder] Progress: {completed}/{total} files completed")
                except Exception as e:
                    path = file_info.get('path', 'unknown')
                    self.files_failed.append({"path": path, "error": str(e)})
                    print(f"[Builder] Error generating {path}: {e}")
                    log_event(
                        "builder",
                        "parallel_file_failed",
                        level="error",
                        correlation_id=self._correlation_id(),
                        project_id=self._project_id(),
                        path=path,
                        error=str(e),
                    )

    def _extract_file_list(self, plan_content: str):
        """
        Uses LLM to parse the markdown plan into a structured list of files to edit.
        """
        prompt = f"""
        Extract the list of files to be created or modified from this plan.
        Return a JSON list of objects with 'path' and 'context' (briefly what to do).

        PLAN:
        {plan_content}

        JSON OUTPUT:
        """
        print("[Builder] Parsing plan structure...")
        log_event(
            "builder",
            "plan_structure_parsing_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
        )

        # Simple parsing task → Use LOCAL (Ollama)
        decision = quick_route(prompt, task_type='code')
        print(f"[Router] Using {decision.provider}/{decision.model} for plan parsing (score: {decision.score})")
        log_event(
            "builder",
            "plan_structure_route_selected",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
        )

        response = self.llm.chat(
            [{"role": "user", "content": prompt}],
            provider=decision.provider,
            model=decision.model
        )
        
        # Clean up code blocks if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
             response = response.split("```")[1].split("```")[0]
             
        try:
            import json
            parsed = json.loads(response)
            if isinstance(parsed, list):
                log_event(
                    "builder",
                    "plan_structure_parsed",
                    correlation_id=self._correlation_id(),
                    project_id=self._project_id(),
                    parser="llm_json",
                    file_count=len(parsed),
                )
                return parsed
            print("[Builder] Plan parser returned non-list JSON; falling back to heuristic parser.")
            log_event(
                "builder",
                "plan_structure_fallback",
                level="warning",
                correlation_id=self._correlation_id(),
                project_id=self._project_id(),
                reason="non_list_json",
            )
            return self._extract_file_list_heuristic(plan_content)
        except Exception as e:
            print(f"[Builder] Failed to parse file list JSON: {e}")
            log_event(
                "builder",
                "plan_structure_fallback",
                level="warning",
                correlation_id=self._correlation_id(),
                project_id=self._project_id(),
                reason="json_parse_error",
                error=str(e),
            )
            return self._extract_file_list_heuristic(plan_content)

    def _extract_file_list_heuristic(self, plan_content: str):
        """
        Fallback parser when JSON extraction fails.
        Looks for path-like tokens in markdown/backticks and returns a de-duped list.
        """
        print("[Builder] Using heuristic file extraction fallback...")

        # Prefer backticked paths first, then loose path-like tokens.
        candidates = []
        candidates.extend(re.findall(r"`([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)`", plan_content))
        candidates.extend(re.findall(r"\b([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)\b", plan_content))

        # Keep plausible project file paths only.
        skip_prefixes = ("http://", "https://")
        allowed_exts = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
            ".md", ".sh", ".sql", ".go", ".rs", ".java", ".kt", ".rb",
            ".toml", ".ini", ".cfg", ".env"
        }

        seen = set()
        file_list = []
        for raw in candidates:
            if raw.startswith(skip_prefixes):
                continue
            path = os.path.normpath(raw).replace("\\", "/").lstrip("./")
            _, ext = os.path.splitext(path)
            if ext.lower() not in allowed_exts:
                continue
            if "/" not in path and ext in {".md", ".txt"}:
                # Ignore broad doc mentions like README.md unless path-qualified.
                continue
            if path in seen:
                continue
            seen.add(path)
            file_list.append({
                "path": path,
                "context": "Implement changes described in the plan."
            })

        print(f"[Builder] Heuristic parser found {len(file_list)} files.")
        log_event(
            "builder",
            "heuristic_plan_parse_completed",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            file_count=len(file_list),
        )
        return file_list

    def _generate_file(self, file_info, plan_content):
        path = file_info.get('path')
        if not path: return

        # Normalize path
        target_path = os.path.normpath(path)
        # Sandbox path
        sandbox_path = os.path.join(self.sandbox_dir, target_path)

        # Load existing content if file exists in repo
        existing_content = ""
        repo_file = os.path.join(self.manifest.repo_path, target_path)
        file_exists = os.path.exists(repo_file)
        if file_exists:
            with open(repo_file, "r") as f:
                existing_content = f.read()

        # Check if incremental build can skip this file
        if self.incremental and self.build_cache:
            input_signature = self.build_cache._build_input_signature(
                target_path=target_path,
                plan_content=plan_content,
                file_info=file_info,
                existing_content=existing_content,
                file_exists=file_exists,
            )
            if self.build_cache.should_skip(target_path, input_signature, sandbox_path):
                print(f"[Builder] Skipping {target_path} (unchanged)")
                self.files_skipped.append({
                    "path": target_path,
                    "reason": "input_signature_unchanged",
                })
                log_event(
                    "builder",
                    "file_skipped",
                    correlation_id=self._correlation_id(),
                    project_id=self._project_id(),
                    path=target_path,
                    reason="input_signature_unchanged",
                )
                return
        else:
            input_signature = None

        print(f"[Builder] Generating: {target_path}...")

        # Decide: surgical edit vs full rewrite
        if file_exists and len(existing_content) > 100:
            # Use surgical edit for existing files
            final_content = self._surgical_edit(target_path, existing_content, file_info, plan_content)
        else:
            # Generate new file from scratch
            final_content = self._full_generate(target_path, existing_content, file_info, plan_content)

        # Interactive mode: Show diff and ask for approval
        if self.interactive and self.diff_viewer and file_exists:
            print(f"\n{'='*60}")
            print(f"DIFF: {target_path}")
            print('='*60)

            # Write temp file for diff comparison
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                tmp.write(final_content)
                tmp_path = tmp.name

            try:
                self.diff_viewer.show_diff(repo_file, tmp_path, context_lines=3)
                print('='*60)

                response = input(f"\nApply changes to {target_path}? [y/n] (default: y): ").strip().lower()
                if response and response not in ['y', 'yes']:
                    print(f"[Builder] Skipped {target_path}")
                    os.unlink(tmp_path)
                    return
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        # Save to Sandbox
        os.makedirs(os.path.dirname(sandbox_path), exist_ok=True)
        with open(sandbox_path, "w") as f:
            f.write(final_content)

        print(f"[Builder] Wrote {len(final_content)} bytes to {sandbox_path}")
        log_event(
            "builder",
            "file_generated",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=target_path,
            bytes_written=len(final_content),
        )

        # Update build cache
        if self.incremental and self.build_cache:
            self.build_cache.update(
                target_path=target_path,
                input_signature=input_signature,
                output_content=final_content,
            )

        # Track that this file was built
        self.files_built.append(target_path)

    def _surgical_edit(self, target_path, existing_content, file_info, plan_content):
        """
        Makes targeted edits to existing file instead of full rewrite.
        Returns the modified content.
        """
        print(f"[Builder] Using surgical edit for {target_path}...")
        log_event(
            "builder",
            "surgical_edit_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=target_path,
        )

        with open(prompt_path("coding.txt"), "r") as f:
            system_prompt = f.read()

        user_prompt = f"""
        TASK: Make targeted edits to the existing file. Only modify what's necessary.

        PLAN EXCERPT:
        {plan_content[:2000]}

        TARGET FILE: {target_path}
        CHANGES NEEDED: {file_info.get('context')}

        EXISTING CONTENT:
        {existing_content}

        INSTRUCTIONS:
        1. Identify the exact sections that need to change
        2. Make ONLY the necessary edits
        3. Preserve all existing imports, formatting, and unrelated code
        4. Return the complete updated file content
        5. Do NOT add unnecessary refactoring or comments

        OUTPUT: The complete updated file (not a diff, not partial - the full file with your edits applied)
        """

        if self.stream:
            print(f"\n[Builder] Streaming surgical edit for {target_path}...\n")

        # Route based on edit complexity
        decision = quick_route(user_prompt, task_type='code')
        print(f"[Router] Using {decision.provider}/{decision.model} for surgical edit (score: {decision.score})")
        log_event(
            "builder",
            "surgical_edit_route_selected",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=target_path,
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
        )

        code = self.llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], provider=decision.provider, model=decision.model, stream=self.stream)

        # Strip markdown syntax if LLM ignored instructions
        return self._clean_code_response(code)

    def _full_generate(self, target_path, existing_content, file_info, plan_content):
        """
        Generates complete new file from scratch.
        Used for new files or very small existing files.
        """
        print(f"[Builder] Generating new file: {target_path}...")
        log_event(
            "builder",
            "full_generate_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=target_path,
        )

        with open(prompt_path("coding.txt"), "r") as f:
            system_prompt = f.read()

        user_prompt = f"""
        PLAN:
        {plan_content}

        TARGET FILE: {target_path}
        CONTEXT: {file_info.get('context')}

        EXISTING CONTENT:
        {existing_content}

        Generate the Full New Content for {target_path}.
        """

        if self.stream:
            print(f"\n[Builder] Streaming generation for {target_path}...\n")

        # Route based on generation complexity
        decision = quick_route(user_prompt, task_type='code')
        print(f"[Router] Using {decision.provider}/{decision.model} for full generation (score: {decision.score})")
        log_event(
            "builder",
            "full_generate_route_selected",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=target_path,
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
        )

        code = self.llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], provider=decision.provider, model=decision.model, stream=self.stream)

        return self._clean_code_response(code)

    def _clean_code_response(self, code):
        """
        Strips markdown code blocks from LLM response.
        """
        clean_code = code
        if clean_code.startswith("```"):
            clean_code = "\n".join(clean_code.split("\n")[1:])
        if clean_code.endswith("```"):
            clean_code = "\n".join(clean_code.split("\n")[:-1])
        return clean_code

    def generate_tests(self, file_path: str):
        """
        Generates a unit test file for the given source file.
        """
        sandbox_path = os.path.join(self.sandbox_dir, file_path)
        if not os.path.exists(sandbox_path):
            print(f"[Builder] Cannot generate tests. File not found: {sandbox_path}")
            log_event(
                "builder",
                "test_generation_skipped",
                level="warning",
                correlation_id=self._correlation_id(),
                project_id=self._project_id(),
                path=file_path,
                reason="sandbox_file_missing",
            )
            return None
            
        with open(sandbox_path, "r") as f:
            code_content = f.read()

        print(f"[Builder] Generating tests for {file_path}...")
        log_event(
            "builder",
            "test_generation_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
        )
        
        with open(prompt_path("testing.txt"), "r") as f:
            system_prompt = f.read()
            
        user_prompt = f"""
        Generate pytest unit tests for the following code:
        PATH: {file_path}

        CODE:
        {code_content}
        """

        # Test generation → Use LOCAL (cheaper, good enough for tests)
        decision = quick_route(user_prompt, task_type='code')
        print(f"[Router] Using {decision.provider}/{decision.model} for test generation (score: {decision.score})")
        log_event(
            "builder",
            "test_generation_route_selected",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
        )

        test_code = self.llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], provider=decision.provider, model=decision.model)
        
        # Cleanup
        if test_code.startswith("```"):
            test_code = "\n".join(test_code.split("\n")[1:])
        if test_code.endswith("```"):
             test_code = "\n".join(test_code.split("\n")[:-1])
             
        # Determine test path (e.g. brain/patterns/test_gaming_mode.py)
        # For simplicity, we just prefix the filename with test_
        dirname = os.path.dirname(file_path)
        basename = os.path.basename(file_path)
        test_path = os.path.join(dirname, f"test_{basename}")
        
        full_test_path = os.path.join(self.sandbox_dir, test_path)
        
        with open(full_test_path, "w") as f:
            f.write(test_code)
            
        print(f"[Builder] Generated tests at {test_path}")
        log_event(
            "builder",
            "test_generated",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
            test_path=test_path,
        )
        return test_path

    def fix_code(self, file_path: str, error_log: str):
        """
        Attempts to fix the code based on the error log.
        """
        sandbox_path = os.path.join(self.sandbox_dir, file_path)
        with open(sandbox_path, "r") as f:
            code_content = f.read()
            
        print(f"[Builder] Self-Healing {file_path}...")
        log_event(
            "builder",
            "self_heal_started",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
        )
        
        with open(prompt_path("fixing.txt"), "r") as f:
            system_prompt = f.read()
            
        user_prompt = f"""
        BROKEN CODE ({file_path}):
        {code_content}

        ERROR LOG:
        {error_log}

        Please provide the fixed code.
        """

        # Bug fixing → Use routing based on error complexity
        decision = quick_route(user_prompt, task_type='code')
        print(f"[Router] Using {decision.provider}/{decision.model} for bug fixing (score: {decision.score})")
        log_event(
            "builder",
            "self_heal_route_selected",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
            provider=decision.provider,
            model=decision.model,
            score=decision.score,
        )

        fixed_code = self.llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], provider=decision.provider, model=decision.model)
        
        # Cleanup
        if fixed_code.startswith("```"):
            fixed_code = "\n".join(fixed_code.split("\n")[1:])
        if fixed_code.endswith("```"):
             fixed_code = "\n".join(fixed_code.split("\n")[:-1])

        # Overwrite
        with open(sandbox_path, "w") as f:
            f.write(fixed_code)
            
        print(f"[Builder] Applied fix to {file_path}")
        log_event(
            "builder",
            "self_heal_applied",
            correlation_id=self._correlation_id(),
            project_id=self._project_id(),
            path=file_path,
        )
