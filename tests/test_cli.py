
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import subprocess

# Ensure we can import sage.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sage

class TestSageCLI(unittest.TestCase):
    
    @patch('subprocess.call')
    def test_ensure_mosquitto_running_already_active(self, mock_call):
        """Test that nothing happens if mosquitto is already running."""
        # Setup: subprocess.call returns 0 (success/found) for pgrep
        mock_call.return_value = 0
        
        proc, success = sage.ensure_mosquitto_running()
        
        self.assertTrue(success)
        self.assertIsNone(proc)
        mock_call.assert_called_with(["pgrep", "-f", "mosquitto.*mosquitto.conf"], stdout=subprocess.DEVNULL)

    @patch('subprocess.Popen')
    @patch('subprocess.run')
    @patch('subprocess.call')
    def test_ensure_mosquitto_running_starts_new(self, mock_call, mock_run, mock_popen):
        """Test that mosquitto is started if not running."""
        # Setup: pgrep returns 1 (not found)
        mock_call.return_value = 1
        
        # Setup: Popen returns a process mock that is still running (poll() is None)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None 
        mock_popen.return_value = mock_proc
        
        proc, success = sage.ensure_mosquitto_running()
        
        self.assertTrue(success)
        self.assertEqual(proc, mock_proc)
        
        # Check that pkill was called
        mock_run.assert_called_with(["pkill", "mosquitto"], stderr=subprocess.DEVNULL)
        
        # Check that Popen was called with correct args
        mock_popen.assert_called_with(
            ["mosquitto", "-c", "mosquitto.conf"],
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    @patch('sage.ensure_mosquitto_running')
    @patch('subprocess.run')
    def test_cmd_brain_starts_mosquitto(self, mock_run, mock_ensure):
        """Test that ensure_mosquitto_running is called before starting brain."""
        # Setup: ensure_mosquitto returns success
        mock_ensure.return_value = (None, True)
        
        args = MagicMock()
        sage.cmd_brain(args)
        
        mock_ensure.assert_called_once()
        # Verify brain was started
        mock_run.assert_called_with([sys.executable, "-u", "brain/main.py"])

    @patch('sage.ensure_mosquitto_running')
    @patch('subprocess.run')
    def test_cmd_brain_abort_on_mqtt_fail(self, mock_run, mock_ensure):
        """Test that brain does not start if MQTT fails to start."""
        # Setup: ensure_mosquitto returns failure
        mock_ensure.return_value = (None, False)
        
        args = MagicMock()
        sage.cmd_brain(args)
        
        mock_ensure.assert_called_once()
        # Verify brain was NOT started
        mock_run.assert_not_called()

    @patch.dict(os.environ, {"SAGE_FORCE_CLOUD_REASONING": "true", "SAGE_CLOUD_PROVIDER": "openai"}, clear=False)
    @patch("sage.kill_processes")
    @patch("subprocess.check_output")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("sage.run_process_async")
    @patch("sage.ensure_mosquitto_running")
    def test_cmd_pwa_clears_inherited_cloud_env_without_flag(
        self,
        mock_ensure,
        mock_run_process_async,
        mock_exists,
        mock_popen,
        mock_run,
        mock_check_output,
        mock_kill_processes,
    ):
        """./sage pwa should not inherit cloud-only env overrides unless --cloud-only is set."""
        mock_ensure.return_value = (None, True)
        mock_exists.return_value = True
        mock_check_output.return_value = b"127.0.0.1\n"

        # Brain process from run_process_async
        mock_brain = MagicMock()
        mock_brain.poll.return_value = None
        mock_run_process_async.return_value = (mock_brain, None)

        # Next.js process should fail immediately so cmd_pwa exits quickly
        mock_next = MagicMock()
        mock_next.poll.return_value = 1
        mock_popen.return_value = mock_next

        args = MagicMock(
            no_brain=False,
            no_stt=True,
            no_tts=True,
            cloud_only=False,
            cloud_provider="grok",
            cloud_model=None,
            brain_logs=False,
        )

        sage.cmd_pwa(args)

        _, kwargs = mock_run_process_async.call_args
        brain_env = kwargs.get("env", {})
        self.assertNotIn("SAGE_FORCE_CLOUD_REASONING", brain_env)
        self.assertNotIn("SAGE_CLOUD_PROVIDER", brain_env)
        self.assertNotIn("SAGE_CLOUD_MODEL", brain_env)

    @patch("sage.kill_processes")
    @patch("subprocess.check_output")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch("os.path.exists")
    @patch("sage.run_process_async")
    @patch("sage.ensure_mosquitto_running")
    def test_cmd_pwa_sets_cloud_env_with_flag(
        self,
        mock_ensure,
        mock_run_process_async,
        mock_exists,
        mock_popen,
        mock_run,
        mock_check_output,
        mock_kill_processes,
    ):
        """./sage pwa --cloud-only should set explicit cloud overrides for Brain."""
        mock_ensure.return_value = (None, True)
        mock_exists.return_value = True
        mock_check_output.return_value = b"127.0.0.1\n"

        mock_brain = MagicMock()
        mock_brain.poll.return_value = None
        mock_run_process_async.return_value = (mock_brain, None)

        mock_next = MagicMock()
        mock_next.poll.return_value = 1
        mock_popen.return_value = mock_next

        args = MagicMock(
            no_brain=False,
            no_stt=True,
            no_tts=True,
            cloud_only=True,
            cloud_provider="openai",
            cloud_model="gpt-4o-mini",
            brain_logs=False,
        )

        sage.cmd_pwa(args)

        _, kwargs = mock_run_process_async.call_args
        brain_env = kwargs.get("env", {})
        self.assertEqual(brain_env.get("SAGE_FORCE_CLOUD_REASONING"), "true")
        self.assertEqual(brain_env.get("SAGE_CLOUD_PROVIDER"), "openai")
        self.assertEqual(brain_env.get("SAGE_CLOUD_MODEL"), "gpt-4o-mini")
        self.assertEqual(brain_env.get("INTENT_USE_LLM"), "false")

if __name__ == '__main__':
    unittest.main()
