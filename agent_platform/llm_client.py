"""
LLM client for calling Azure OpenAI or Ollama
"""
from config.settings import settings
from openai import AzureOpenAI
import requests
from loguru import logger


class LLMClient:
    """Unified LLM client for Azure OpenAI and Ollama"""

    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or settings.AGENT_LLM_PROVIDER
        self.model = model  # Optional: override default model

        if self.provider == 'azure':
            self.client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 16000) -> str:
        """Generate response from LLM"""
        if self.provider == 'azure':
            return self._call_azure(prompt, temperature, max_tokens)
        elif self.provider == 'ollama':
            return self._call_ollama(prompt, temperature)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _call_azure(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Call Azure OpenAI"""
        try:
            # Use cheaper model if specified, otherwise use default
            deployment = self.model or settings.AZURE_OPENAI_DEPLOYMENT

            response = self.client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are an expert SQL query generator. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Azure OpenAI call failed: {e}")
            raise

    def _call_ollama(self, prompt: str, temperature: float) -> str:
        """Call Ollama"""
        try:
            response = requests.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()['response']
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise
