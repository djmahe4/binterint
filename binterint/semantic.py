from typing import List, Dict, Any, Optional
import os
import io
import json
import base64
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environmental variables from .env if it exists
load_dotenv()

class DetectedElement(BaseModel):
    """
    Represents a logically identified UI element in a TUI screenshot.
    """
    type: str = Field(description="The category of the element (e.g., button, input, checkbox, status_bar, progress_bar)")
    label: str = Field(description="The text label or content associated with the element")
    x: int = Field(description="The normalized x-coordinate (0-1000) of the element's center", ge=0, le=1000)
    y: int = Field(description="The normalized y-coordinate (0-1000) of the element's center", ge=0, le=1000)
    confidence: float = Field(description="Confidence score of the detection (0.0 - 1.0)", ge=0.0, le=1.0)

class SemanticAnalyzer:
    """
    Extracts logical UI elements from terminal states using rule-based parsing
    or advanced Vision LLMs (Gemini/OpenAI).
    """
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id
        
    def extract_from_screen(self, text_content: str) -> List[Dict[str, Any]]:
        """
        Naive rule-based extraction from text buffer.
        """
        import re
        elements = []
        # Find buttons like [ Ok ]
        for match in re.finditer(r'\[\s*([^\]]+?)\s*\]', text_content):
            elements.append({
                "type": "button",
                "label": match.group(1),
                "pos": match.span()
            })
        return elements

    async def analyze_screenshot(self, image_path: str, cols: int = 80, rows: int = 24) -> List[DetectedElement]:
        """
        Uses Vision LLM to perform spatial understanding and element detection.
        Prioritizes Gemini 2.5 Flash over OpenAI GPT-5.4.
        """
        google_api_key = os.getenv("GOOGLE_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if google_api_key:
            return await self._analyze_with_gemini(image_path)
        elif openai_api_key:
            return await self._analyze_with_openai(image_path)
        else:
            return []

    async def _analyze_with_gemini(self, image_path: str) -> List[DetectedElement]:
        """
        Implementation for Gemini 2.5 Flash Vision.
        """
        import google.generativeai as genai
        from PIL import Image
        
        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        
        # Use GA model gemini-2.5-flash
        model_name = self.model_id or "gemini-2.5-flash"
        model = genai.GenerativeModel(model_name)
        
        prompt = """
        Analyze this Terminal UI (TUI) screenshot. Identify all interactive elements such as buttons, 
        input fields, checkboxes, and menu items. 
        For each element, provide:
        1. Type (button, input, checkbox, etc.)
        2. Label (the exact text content)
        3. Coordinates (normalized 0-1000 for center x and y)
        
        Return the result strictly as a valid JSON array of objects.
        Format: [{"type": "...", "label": "...", "x": 0..1000, "y": 0..1000, "confidence": 0.0..1.0}]
        """
        
        img = Image.open(image_path)
        response = model.generate_content([prompt, img])
        
        return self._parse_llm_json(response.text)

    async def _analyze_with_openai(self, image_path: str) -> List[DetectedElement]:
        """
        Implementation for OpenAI GPT-5.4 Vision.
        """
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        prompt = """
        You are a specialized UI analysis model. Detect all interactive elements in this TUI screenshot.
        Return a JSON array of objects containing 'type', 'label', 'x', 'y' (0-1000 normalized), and 'confidence'.
        """
        
        # Use gpt-5.4 with 'original' detail for best computer use spatial accuracy
        response = client.chat.completions.create(
            model=self.model_id or "gpt-5.4",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "original"
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        return self._parse_llm_json(content)

    def _parse_llm_json(self, json_str: str) -> List[DetectedElement]:
        """
        Helps safely parse and validate LLM output into Pydantic models.
        """
        # Strip potential markdown code blocks
        clean_json = json_str.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        try:
            data = json.loads(clean_json)
            # Handle if LLM wraps the array in an object like {"elements": [...]}
            if isinstance(data, dict):
                for key in ["elements", "items", "detected_elements"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
            
            if not isinstance(data, list):
                return []
                
            return [DetectedElement(**item) for item in data]
        except Exception:
            return []

    @staticmethod
    def map_to_grid(norm_x: int, norm_y: int, cols: int, rows: int) -> Dict[str, int]:
        """
        Maps 0-1000 normalized coordinates back to terminal grid coordinates.
        """
        return {
            "col": int((norm_x / 1000) * cols),
            "row": int((norm_y / 1000) * rows)
        }
