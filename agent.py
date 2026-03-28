import os
import json
from google import genai
from google.genai import types

# Setup API Key
generation_config = types.GenerateContentConfig(
  temperature=0.4,
  top_p=0.95,
  top_k=40,
  max_output_tokens=8192,
  response_mime_type="application/json",
)

# The schema helps enforce the structured output from Gemini
response_schema = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "Score from 1 to 10"},
        "is_promising": {"type": "boolean", "description": "True if score >= 7 or visually exceptional"},
        "critique_bullets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Bulleted list of artistic critiques covering composition, complexity, reflections, and stylistic resemblance to masters like Alex Webb, Vivian Maier, Alan Schaller."
        }
    },
    "required": ["score", "is_promising", "critique_bullets"]
}

from dotenv import load_dotenv

def analyze_photo(image_path, model_name="gemini-2.5-flash", style="Any", photographers=None):
    """
    Sends the image to Gemini Vision API for evaluation.
    Returns a dictionary parsed from the JSON response.
    """
    load_dotenv()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set. Please set it before running.")
        
    client = genai.Client(api_key=api_key)
    
    style_instruction = "Consider both color and black & white street photography styles."
    if style == "Color":
        style_instruction = "Focus heavily on color street photography aesthetics, such as color contrast, complementary colors, and distinctive color palettes."
    elif style == "Black & White (Monochrome)":
        style_instruction = "Focus heavily on black & white street photography aesthetics, such as strong contrast, tonal range, textures, and the interplay of light and shadow."
        
    photographer_instruction = f"Evaluate its stylistic resonance and potential to look like the work of: {', '.join(photographers)}." if photographers else "Evaluate its stylistic resonance with master street photographers."

    prompt = f"""
    You are an expert photography curator and critic, with deep knowledge of street photography masters and styles.
    Review the following photograph (taken on a photowalk). Evaluate it based on:
    1. Composition (framing, leading lines, rule of thirds, balance)
    2. Complexity (layers, cool reflections, visual interest, capturing a specific decisive moment)
    3. Stylistic resonance: {photographer_instruction}
    
    Overall Style Focus: {style_instruction}
    
    Provide your response in JSON format according to the schema:
    - score: Integer from 1 to 10.
    - is_promising: Boolean (true if score is 7 or higher, or if it has exceptional potential with editing).
    - critique_bullets: Array of strings. Each string is a plain text bullet point describing your artistic critique and specific recommendations for editing.
    """
    
    try:
        sample_file = client.files.upload(file=image_path, config={'display_name': os.path.basename(image_path)})
        
        response = client.models.generate_content(
            model=model_name,
            contents=[sample_file, prompt],
            config=types.GenerateContentConfig(
                temperature=0.4,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        # Clean up the file from Gemini servers after analysis
        client.files.delete(name=sample_file.name)
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        return json.loads(text)
    except Exception as e:
        print(f"Error analyzing {image_path}: {e}")
        return {
            "score": 0,
            "is_promising": False,
            "critique_bullets": [f"Error during API call: {e}"]
        }
