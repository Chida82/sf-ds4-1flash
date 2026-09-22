#!/usr/bin/env python3
"""Offline checks for download.sh.

The interesting property is not that a download works -- the Hugging Face CLI
owns that -- but that this repository never ends up holding model data: every
path the script creates must be a symlink into the shared cache, and the root
default-model link must point at the component link rather than at the cache
(SPEC.md C).  A stub `hf` on PATH makes all of that testable without network.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "download.sh"
DEFAULT_LINK = "deepseek-v4.1-flash.gguf"
Q2 = "DeepSeek-V4.1-Flash-Q2.gguf"
VISION = "DeepSeek-V4.1-Flash-Vision.gguf"


def run(args, env=None, cwd=None):
    return subprocess.run([str(SCRIPT)] + args, capture_output=True, text=True,
                          env=env, cwd=cwd)


class DownloadScript(unittest.TestCase):
    def test_lists_components_without_arguments(self):
        r = run([])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("q2", r.stdout)
        self.assertIn("vision", r.stdout)
        # The Q4 release is deliberately not offered: joining its two parts
        # would put a multi-gigabyte real file in the repository.
        self.assertIn("Q4", r.stdout)

    def test_unknown_component_is_rejected(self):
        r = run(["q8"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown component", r.stderr)

    def test_creates_symlinks_and_never_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cache = tmp / "cache"
            cache.mkdir()
            # A stub `hf` that reports a cached file in the shape the real CLI
            # uses ("path=<absolute path>" on stdout).
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "hf"
            stub.write_text(
                "#!/bin/sh\n"
                'file="$3"\n'
                f'mkdir -p "{cache}"\n'
                f'printf \'model bytes\\n\' > "{cache}/$file"\n'
                f'echo "path={cache}/$file"\n')
            stub.chmod(0o755)

            # Run the real script inside a copy of the repo root, so the links
            # it makes land in the sandbox rather than in the working tree.
            work = tmp / "repo"
            work.mkdir()
            (work / "download.sh").write_bytes(SCRIPT.read_bytes())
            (work / "download.sh").chmod(0o755)

            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
            r = subprocess.run([str(work / "download.sh"), "q2"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)

            component = work / "gguf" / Q2
            default = work / DEFAULT_LINK
            self.assertTrue(component.is_symlink(), "gguf/ entry must be a symlink")
            self.assertEqual(os.readlink(component), str(cache / Q2))
            self.assertTrue(default.is_symlink(), "default model must be a symlink")
            self.assertEqual(os.readlink(default), f"gguf/{Q2}")
            self.assertTrue(default.resolve().is_file())

            # The vision encoder gets a component link but must not steal the
            # default-model link.
            r = subprocess.run([str(work / "download.sh"), "vision"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((work / "gguf" / VISION).is_symlink())
            self.assertEqual(os.readlink(default), f"gguf/{Q2}")

            # Nothing in the repository may be a regular file holding model data.
            reals = [p for p in work.rglob("*")
                     if p.is_file() and not p.is_symlink() and p.suffix == ".gguf"]
            self.assertEqual(reals, [], "download.sh must not materialise GGUFs")

    def test_reports_a_missing_cli(self):
        # A PATH with the system tools but no `hf`.  Emptying PATH entirely
        # would make the shell itself fail with 127 and prove nothing.
        env = dict(os.environ, PATH="/usr/bin:/bin")
        if subprocess.run(["sh", "-c", "command -v hf"], env=env,
                          capture_output=True).returncode == 0:
            self.skipTest("hf is installed in /usr/bin")
        r = run(["q2"], env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Hugging Face CLI", r.stderr)


if __name__ == "__main__":
    unittest.main()
