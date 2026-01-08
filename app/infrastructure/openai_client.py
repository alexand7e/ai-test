from openai import AsyncOpenAI
from typing import AsyncIterator, List, Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Cliente OpenAI assíncrono para embeddings e chat completions (compatível com APIs OpenAI)"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
    
    async def get_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """Gera embedding para um texto"""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "Qwen/Qwen2.5-3B-Instruct",
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[str]:
        """Stream de tokens da OpenAI"""
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
                tools=tools
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error in chat completion stream: {e}")
            raise
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "Qwen/Qwen2.5-3B-Instruct",
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """Completação de chat sem streaming"""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice
            )
            
            message = response.choices[0].message
            tool_calls = message.tool_calls if hasattr(message, 'tool_calls') and message.tool_calls else None
            
            return {
                'content': message.content,
                'tool_calls': tool_calls,
                'tokens_used': response.usage.total_tokens if response.usage else None
            }
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise

