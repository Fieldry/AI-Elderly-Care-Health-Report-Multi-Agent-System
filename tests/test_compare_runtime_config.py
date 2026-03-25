from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "code"))

from run_single_model_compare import configure_runtime  # noqa: E402


class CompareRuntimeConfigTestCase(unittest.TestCase):
    def test_configure_runtime_maps_openai_env_and_temperature(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dotenv_path = Path(tmp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=test-openai-key",
                        "OPENAI_BASE_URL=https://example.test/v1",
                        "OPENAI_MODEL=test-openai-model",
                    ]
                ),
                encoding="utf-8",
            )

            previous = {key: os.environ.get(key) for key in (
                "DEEPSEEK_API_KEY",
                "DEEPSEEK_BASE_URL",
                "DEEPSEEK_MODEL",
                "RAG_ENABLED",
                "RAG_INDEX_PATH",
                "RAG_TOP_K",
                "LLM_TEMPERATURE_OVERRIDE",
            )}
            try:
                configure_runtime(
                    rag_index=Path("/tmp/index.json"),
                    rag_top_k=7,
                    dotenv_path=dotenv_path,
                    llm_config="openai",
                    temperature=1.0,
                    model_override=None,
                )

                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "test-openai-key")
                self.assertEqual(os.environ["DEEPSEEK_BASE_URL"], "https://example.test/v1")
                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "test-openai-model")
                self.assertEqual(os.environ["RAG_ENABLED"], "true")
                self.assertEqual(os.environ["RAG_INDEX_PATH"], "/tmp/index.json")
                self.assertEqual(os.environ["RAG_TOP_K"], "7")
                self.assertEqual(os.environ["LLM_TEMPERATURE_OVERRIDE"], "1.0")
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
