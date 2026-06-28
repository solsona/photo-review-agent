import os
import json
import base64
import urllib.request
import urllib.error
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

# The schema helps enforce the structured output
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

def get_ollama_models(host="http://localhost:11434"):
    """
    Fetches the list of available models from the local Ollama server.
    """
    url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            return sorted(models)
    except Exception:
        return []

def analyze_photo_ollama(image_path, model_name="gemma4:12b", host="http://localhost:11434", style="Any", photographers=None):
    """
    Sends the image to a local Ollama Vision API for evaluation.
    """
    try:
        with open(image_path, "rb") as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error reading image {image_path}: {e}")
        return {
            "score": 0,
            "is_promising": False,
            "critique_bullets": [f"Error reading image: {e}"]
        }
        
    style_instruction = "Consider both color and black & white street photography styles."
    if style == "Color":
        style_instruction = "Focus heavily on color street photography aesthetics, such as color contrast, complementary colors, and distinctive color palettes."
    elif style == "Black & White (Monochrome)":
        style_instruction = "Focus heavily on black & white street photography aesthetics, such as strong contrast, tonal range, textures, and the interplay of light and shadow."
        
    fixed_photographers = photographers if photographers else ["Alex Webb", "Vivian Maier", "Saul Leiter", "Henri Cartier-Bresson", "Fan Ho"]
    photographer_instruction = f"Evaluate its stylistic resonance and potential to look like the work of: {', '.join(fixed_photographers)}."

    prompt = f"""
    You are an expert photography curator and critic, with deep knowledge of street photography masters.
    Review the following photograph. Evaluate it based on:
    1. Composition (framing, leading lines, rule of thirds, balance)
    2. Complexity (layers, cool reflections, visual interest, decisive moment)
    3. Stylistic resonance: {photographer_instruction}
    
    Overall Style Focus: {style_instruction}
    
    CRITICAL INSTRUCTION: Keep the critique bullets EXTREMELY short and to the point. Maximum 2 short sentences per bullet. This critique will be embedded into the image metadata, so brevity is essential.
    
    Provide your response in JSON format according to the schema:
    - score: Integer from 1 to 10.
    - is_promising: Boolean (true if score is 7 or higher).
    - critique_bullets: Array of strings. Each string is a brief, plain text bullet point describing your artistic critique and specific editing recommendations.
    """
    
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_base64]
            }
        ],
        "format": response_schema,
        "options": {
            "temperature": 0.4
        },
        "stream": False
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        # Long timeout for local model execution as vision can take time (increased to 240s)
        with urllib.request.urlopen(req, timeout=240) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data["message"]["content"].strip()
            # Clean markdown JSON block formatting if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            return json.loads(content)
    except urllib.error.URLError as e:
        print(f"Connection to Ollama failed at {host}: {e}")
        return {
            "score": 0,
            "is_promising": False,
            "critique_bullets": [
                f"Error: Connection to local Ollama server at {host} failed.",
                "1. Make sure Ollama is running (`ollama serve`).",
                f"2. Make sure you have downloaded the model using `ollama pull {model_name}`."
            ]
        }
    except Exception as e:
        print(f"Error during Ollama analysis for {image_path}: {e}")
        return {
            "score": 0,
            "is_promising": False,
            "critique_bullets": [
                f"Error analyzing with model '{model_name}': {e}",
                "Ensure the model is vision-compatible (e.g., gemma4:12b or llama3.2-vision)."
            ]
        }

def analyze_photo(image_path, model_name="gemini-2.5-flash", style="Any", photographers=None, provider="gemini", ollama_host="http://localhost:11434"):
    """
    Sends the image to the specified API provider (Gemini or Ollama) for evaluation.
    Returns a dictionary parsed from the JSON response.
    """
    if provider.lower() == "ollama":
        return analyze_photo_ollama(image_path, model_name=model_name, host=ollama_host, style=style, photographers=photographers)
        
    # Gemini (cloud) workflow
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
        
    fixed_photographers = photographers if photographers else ["Alex Webb", "Vivian Maier", "Saul Leiter", "Henri Cartier-Bresson", "Fan Ho"]
    photographer_instruction = f"Evaluate its stylistic resonance and potential to look like the work of: {', '.join(fixed_photographers)}."

    prompt = f"""
    You are an expert photography curator and critic, with deep knowledge of street photography masters.
    Review the following photograph. Evaluate it based on:
    1. Composition (framing, leading lines, rule of thirds, balance)
    2. Complexity (layers, cool reflections, visual interest, decisive moment)
    3. Stylistic resonance: {photographer_instruction}
    
    Overall Style Focus: {style_instruction}
    
    CRITICAL INSTRUCTION: Keep the critique bullets EXTREMELY short and to the point. Maximum 2 short sentences per bullet. This critique will be embedded into the image metadata, so brevity is essential.
    
    Provide your response in JSON format according to the schema:
    - score: Integer from 1 to 10.
    - is_promising: Boolean (true if score is 7 or higher).
    - critique_bullets: Array of strings. Each string is a brief, plain text bullet point describing your artistic critique and specific editing recommendations.
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

