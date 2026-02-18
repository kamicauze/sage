"""
The Tester
Runs tests in the sandbox and reports results.
"""
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

import sys

@dataclass
class TestResult:
    passed: bool
    output: str
    error: Optional[str] = None
    failed_tests: List[str] = None

class ArchitectTester:
    def __init__(self, sandbox_path: str):
        self.sandbox_path = sandbox_path

    def run_tests(self, test_file: str = None) -> TestResult:
        """
        Runs pytest in the sandbox using the current Python environment.
        """
        print(f"[Tester] Running tests in {self.sandbox_path}...")
        
        # Use current python interpreter to run pytest
        cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
        if test_file:
            # path relative to sandbox root
            cmd.append(test_file)
        
        try:
            # We run pytest usually from the repo root, but targeting the sandbox
            # But the sandbox files might import 'brain.core'. 
            # We need to set PYTHONPATH to include the sandbox itself.
            
            env = os.environ.copy()
            # Prepare PYTHONPATH to include the sandbox so imports work
            current_pythonpath = env.get("PYTHONPATH", "")
            sandbox_abs = os.path.abspath(self.sandbox_path)
            if current_pythonpath:
                env["PYTHONPATH"] = f"{sandbox_abs}{os.pathsep}{current_pythonpath}"
            else:
                env["PYTHONPATH"] = sandbox_abs
            
            result = subprocess.run(
                cmd,
                cwd=sandbox_abs, # Run 'inside' the sandbox directory
                env=env,
                capture_output=True,
                text=True
            )
            
            output = result.stdout + result.stderr
            passed = (result.returncode == 0)
            
            failed_list = []
            if not passed:
                # Simple heuristic to extract failed test names
                for line in output.splitlines():
                    if line.startswith("FAILED "):
                        failed_list.append(line.split()[1])
            
            return TestResult(
                passed=passed,
                output=output,
                error=None if passed else output,
                failed_tests=failed_list
            )

        except Exception as e:
            return TestResult(
                passed=False,
                output="",
                error=f"Test Execution Failed: {str(e)}"
            )
