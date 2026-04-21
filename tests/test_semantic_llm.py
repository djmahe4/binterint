import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import json
from binterint.semantic import SemanticAnalyzer, DetectedElement

class TestSemanticLLM(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.analyzer = SemanticAnalyzer()

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "fake_gemini_key"})
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    async def test_analyze_with_gemini_mock(self, mock_configure, mock_model_class):
        # Setup mock model
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"type": "button", "label": "Submit", "x": 500, "y": 800, "confidence": 0.95}
        ])
        # Model.generate_content is actually sync in the SDK for non-streaming? No, it depends.
        # But our semantic.py calls it normally. 
        mock_model.generate_content.return_value = mock_response

        # Execute
        results = await self.analyzer.analyze_screenshot("fake_path.png")

        # Verify
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, "Submit")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_openai_key"})
    @patch.dict(os.environ, {"GOOGLE_API_KEY": ""}) 
    @patch("openai.resources.chat.completions.Completions.create") # More specific patch for OpenAI
    @patch("openai.OpenAI")
    async def test_analyze_with_openai_mock(self, mock_openai_class, mock_create):
        # Mock client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create = mock_create
        
        # Mock completion
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content=json.dumps([
                {"type": "input", "label": "Username", "x": 200, "y": 300, "confidence": 0.88}
            ])))
        ]
        mock_create.return_value = mock_completion

        # Execute
        results = await self.analyzer.analyze_screenshot("fake_path.png")

        # Verify
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].type, "input")

    def test_map_to_grid(self):
        # 0-1000 normalized to 80x24 grid
        coords = self.analyzer.map_to_grid(500, 500, 80, 24)
        self.assertEqual(coords["col"], 40)
        self.assertEqual(coords["row"], 12)

        coords_corner = self.analyzer.map_to_grid(1000, 1000, 80, 24)
        self.assertEqual(coords_corner["col"], 80)
        self.assertEqual(coords_corner["row"], 24)

if __name__ == "__main__":
    unittest.main()
