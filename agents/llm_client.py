"""
LLM Client Wrapper - Supports Azure OpenAI and Ollama
"""
from typing import List, Dict, Optional
from openai import AzureOpenAI
import ollama
from loguru import logger
from config.settings import settings


class LLMClient:
    """Universal LLM client that supports multiple providers"""

    def __init__(self, provider: str = "azure"):
        """
        Initialize LLM client

        Args:
            provider: "azure" or "ollama"
        """
        self.provider = provider.lower()

        if self.provider == "azure":
            self.client = AzureOpenAI(
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY
            )
            self.model = settings.AZURE_OPENAI_DEPLOYMENT
            logger.info(f"Initialized Azure OpenAI client with model: {self.model}")

        elif self.provider == "ollama":
            self.client = None  # Ollama uses direct function calls
            self.model = settings.OLLAMA_MODEL
            logger.info(f"Initialized Ollama client with model: {self.model}")

        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'azure' or 'ollama'")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """
        Generate response from LLM

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            Generated text response
        """
        try:
            if self.provider == "azure":
                return self._generate_azure(messages, temperature, max_tokens, stream)
            elif self.provider == "ollama":
                return self._generate_ollama(messages, temperature, max_tokens, stream)
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            raise

    def _generate_azure(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> str:
        """Generate response using Azure OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                # Handle streaming response
                full_response = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                return full_response
            else:
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Azure OpenAI API error: {e}")
            raise

    def _generate_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> str:
        """Generate response using Ollama"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens
                },
                stream=stream
            )

            if stream:
                # Handle streaming response
                full_response = ""
                for chunk in response:
                    if 'message' in chunk and 'content' in chunk['message']:
                        full_response += chunk['message']['content']
                return full_response
            else:
                return response['message']['content']

        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def test_connection(self) -> bool:
        """Test LLM connection"""
        try:
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' if you can read this."}
            ]

            response = self.generate(test_messages, temperature=0.0, max_tokens=10)
            logger.info(f"LLM connection test successful. Response: {response}")
            return True

        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False


def get_agent_llm() -> LLMClient:
    """Get LLM client for agents"""
    return LLMClient(provider=settings.AGENT_LLM_PROVIDER)


def get_evaluator_llm() -> LLMClient:
    """Get LLM client for evaluator"""
    return LLMClient(provider=settings.EVALUATOR_LLM_PROVIDER)


# Test function
if __name__ == "__main__":
    logger.add("logs/llm_client_test.log")

    print("Testing Azure OpenAI client...")
    client = LLMClient(provider="azure")

    if client.test_connection():
        print("✅ Azure OpenAI connection successful!")

        # Test SQL generation
        messages = [
            {"role": "system", "content": "You are a SQL expert."},
            {"role": "user", "content": "Write a SQL query to get total sales from orders table"}
        ]
        response = client.generate(messages, temperature=0.0)
        print(f"\nTest query response:\n{response}")
    else:
        print("❌ Azure OpenAI connection failed!")
