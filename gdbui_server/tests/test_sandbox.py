"""Tests for the sandbox module."""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSandboxDisabled(unittest.TestCase):
    """When GDBUI_DOCKER is not set, start/stop are no-ops."""

    def setUp(self):
        # Ensure env var is not set
        os.environ.pop("GDBUI_DOCKER", None)
        # Force reimport with clean env
        if "sandbox" in sys.modules:
            del sys.modules["sandbox"]

    def test_start_returns_none_when_disabled(self):
        from sandbox import start_container

        self.assertIsNone(start_container("any-sid", "/tmp"))

    def test_stop_does_nothing_when_disabled(self):
        from sandbox import stop_container

        try:
            stop_container("any-sid")
        except Exception:
            self.fail("stop_container raised unexpectedly")

    def test_container_name_ignores_env(self):
        from sandbox import _container_name

        self.assertEqual(_container_name("a1b2c3d4"), "gdbui-a1b2c3d4")
        self.assertEqual(_container_name("550e8400-e29b-41d4-a716"), "gdbui-550e8400")


class TestSandboxEnabled(unittest.TestCase):
    """When GDBUI_DOCKER=true, start/stop shell out to docker CLI."""

    @classmethod
    def setUpClass(cls):
        os.environ["GDBUI_DOCKER"] = "true"
        if "sandbox" in sys.modules:
            del sys.modules["sandbox"]
        import sandbox as sb

        cls.sb = sb

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("GDBUI_DOCKER", None)

    @patch("sandbox.subprocess.run")
    def test_start_runs_docker(self, mock_run):
        name = self.sb.start_container("550e8400-e29b-41d4-a716", "output/sid")
        self.assertEqual(name, "gdbui-550e8400")
        call_args = mock_run.call_args[0][0]
        self.assertIn("docker", call_args)
        self.assertIn("run", call_args)
        self.assertIn("gdbui-550e8400", call_args)
        self.assertIn("--read-only", call_args)
        self.assertIn("--network", call_args)
        self.assertIn("none", call_args)

    @patch("sandbox.subprocess.run")
    def test_start_mounts_output_dir(self, mock_run):
        self.sb.start_container("sid12345", "output/sid12345")
        call_args = mock_run.call_args[0][0]
        vol_idx = call_args.index("-v") + 1
        self.assertIn("output/sid12345:/workspace", call_args[vol_idx])

    @patch("sandbox.subprocess.run")
    def test_stop_runs_docker_rm(self, mock_run):
        self.sb.stop_container("550e8400-e29b-41d4-a716")
        call_args = mock_run.call_args[0][0]
        self.assertIn("docker", call_args)
        self.assertIn("rm", call_args)

    @patch("sandbox.subprocess.run")
    def test_stop_silent_on_missing(self, mock_run):
        mock_run.side_effect = Exception("container not found")
        self.sb.stop_container("missing")

    @patch("sandbox.subprocess.run")
    def test_start_returns_none_on_failure(self, mock_run):
        mock_run.side_effect = Exception("docker daemon not running")
        result = self.sb.start_container("any", "/tmp")
        self.assertIsNone(result)

    @patch("sandbox.subprocess.run")
    def test_start_idempotent_when_name_in_use(self, mock_run):
        err = subprocess.CalledProcessError(
            125, ["docker", "run"], stderr=b'Conflict. The container name "/gdbui-550e8400" is already in use'
        )
        mock_run.side_effect = err
        name = self.sb.start_container("550e8400-e29b-41d4-a716", "output/sid")
        self.assertEqual(name, "gdbui-550e8400")

    @patch("sandbox.subprocess.run")
    def test_start_returns_none_on_other_calledprocesserror(self, mock_run):
        err = subprocess.CalledProcessError(125, ["docker", "run"], stderr=b"docker daemon not reachable")
        mock_run.side_effect = err
        result = self.sb.start_container("any", "/tmp")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
