import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("release_manifests", Path(__file__).parents[1] / "create-release-manifests.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseManifestTests(unittest.TestCase):
    def test_digests_are_usable_without_a_duplicate_prefix(self):
        result = module.manifests("sha256:" + "a" * 64, "sha256:" + "b" * 64, "c" * 40)
        self.assertEqual(result["mainserver"]["BACKEND_IMAGE"], "ghcr.io/otakyooo/anicast-backend@sha256:" + "a" * 64)
        self.assertNotIn("ANICAST_ENV_FILE", result["mainserver"])

    def test_malformed_or_missing_output_cannot_become_a_release(self):
        for digest in ("", "sha256:sha256:" + "a" * 64, "sha256:short", "main", "sha256:" + "g" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                module.manifests(digest, "sha256:" + "b" * 64, "c" * 40)

    def test_revision_is_not_a_tag_or_shell_expression(self):
        with self.assertRaises(ValueError):
            module.manifests("sha256:" + "a" * 64, "sha256:" + "b" * 64, "main\nKEY=value")


if __name__ == "__main__":
    unittest.main()
