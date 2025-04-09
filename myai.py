from openai import OpenAI
import google.generativeai as genai
from dotenv import load_dotenv
import os
import logging
import time
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('youtube_update')

PROMPT_FILE = os.path.dirname(os.path.abspath(__file__)) + '/prompts.txt'
def load_config(config_file=PROMPT_FILE):
    """Load prompts, templates and models from XML config file."""
    try:
        tree = ET.parse(config_file)
        root = tree.getroot()
        
        # Extract prompts
        prompts = []
        for prompt in root.find('prompts').findall('prompt'):
            prompts.append(prompt.text.strip())
            
        # Extract templates
        templates = []
        for template in root.find('templates').findall('template'):
            templates.append(template.text.strip())
            
        # Extract models - dynamically assign A-Z based on count
        models = {}
        model_list = root.find('models').findall('model')
        for idx, model in enumerate(model_list):
            model_id = chr(65 + idx)  # 65 is ASCII for 'A'
            models[model_id] = model.text.strip()
            
        return prompts, templates, models
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return [], [], {}

# Load configuration from prompts.txt
prompts, templates, models = load_config()

def get_summary(text, model_id="A", pidx=0):
    model_name = models[model_id]
    prompt = prompts[pidx]
    template = templates[pidx]

    start_time = time.time()

    try:
        if model_name.startswith("gemini"):
            summary = chat_with_gemini(model_name, prompt, template, text)
        else:
            summary = chat_with_openai(model_name, prompt, template, text)

        elapsed_time = time.time() - start_time
        logger.info(f"get_summary: Model {model_id}({model_name}) took {elapsed_time:.2f} seconds")

        summary = summary.strip() + f"\n\n[model={model_name},{pidx}]\n";
        return summary
    except Exception as e:
        logger.error(f"get_summary: Error generating summary: {e}")
        return f"get_summary: Error generating summary: {e}"


def chat_with_gemini(model_name, prompt, template, message):
    try:
        # Configure the model
        load_dotenv()
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        
        # Create the model instance
        model = genai.GenerativeModel(model_name)
        
        content = template.format(text=message)
        
        # Create a chat instance
        chat = model.start_chat(history=[])
        
        # Add system prompt
        chat.send_message(prompt)
        
        # Send the content and get response
        response = chat.send_message(content)
        
        summary = response.text.strip()
        
        # Handle </think> tag if present
        if '</think>' in summary:
            last_think_pos = summary.rindex('</think>')
            summary = summary[last_think_pos + 8:].lstrip()
            
        return summary
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def chat_with_openai(model_name, prompt, template, message):
    client = OpenAI(
        api_key='ollama',
        base_url='http://solarsuna.com:34567/v1'
    )
    
    try:
        content = template.format(text=message)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=15000,
            temperature=0.7
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Handle </think> tag if present
        if '</think>' in summary:
            last_think_pos = summary.rindex('</think>')
            summary = summary[last_think_pos + 8:].lstrip()
            
        return summary
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"
