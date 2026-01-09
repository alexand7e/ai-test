from openai import AsyncOpenAI
from typing import AsyncIterator, List, Dict, Any, Optional
from app.config import settings
import logging
import math

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Cliente OpenAI assíncrono para embeddings e chat completions (compatível com APIs OpenAI)"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    def estimate_chat_tokens(self, messages: List[Dict[str, str]], completion_text: str) -> int:
        prompt_text = "\n".join([m.get("content", "") for m in messages if m.get("content")])
        return self.estimate_tokens(prompt_text) + self.estimate_tokens(completion_text or "")
    
    async def get_embedding(self, text: str, model: str = "BAAI/bge-m3") -> List[float]:
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
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream de tokens da OpenAI com suporte a tool calls"""
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
                tools=tools
            )
            
            tool_calls_accumulated = []
            current_tool_call = None
            
            async for chunk in stream:
                delta = chunk.choices[0].delta
                
                # Processa conteúdo
                if delta.content:
                    yield {"type": "content", "data": delta.content}
                
                # Processa tool calls
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        index = tool_call_delta.index
                        
                        # Inicia novo tool call
                        if index >= len(tool_calls_accumulated):
                            tool_calls_accumulated.append({
                                "id": tool_call_delta.id or "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                }
                            })
                        
                        # Atualiza tool call
                        if tool_call_delta.id:
                            tool_calls_accumulated[index]["id"] = tool_call_delta.id
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                tool_calls_accumulated[index]["function"]["name"] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                tool_calls_accumulated[index]["function"]["arguments"] += tool_call_delta.function.arguments
                
                # Se chunk.choices[0].finish_reason indica tool calls, retorna todos
                if chunk.choices[0].finish_reason == "tool_calls":
                    yield {"type": "tool_calls", "data": tool_calls_accumulated}
                    
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
            tokens_used = response.usage.total_tokens if getattr(response, "usage", None) else None
            if not tokens_used:
                tokens_used = self.estimate_chat_tokens(messages, message.content or "")
            
            return {
                'content': message.content,
                'tool_calls': tool_calls,
                'tokens_used': tokens_used
            }
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise
