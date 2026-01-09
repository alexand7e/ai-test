from typing import List, Dict, Any, AsyncIterator, Optional
from app.models import AgentConfig, WebhookMessage, AgentResponse, RAGContext
from app.domain.rag_service import RAGService
from app.infrastructure.openai_client import OpenAIClient
from app.infrastructure.redis_client import RedisClient
import uuid
import logging
import json

logger = logging.getLogger(__name__)


class AgentService:
    """Serviço de orquestração de agentes"""
    
    def __init__(
        self,
        redis_client: RedisClient,
        openai_client: OpenAIClient,
        rag_service: RAGService,
        data_analysis_service: Optional[Any] = None
    ):
        self.redis = redis_client
        self.openai = openai_client
        self.rag = rag_service
        self.data_analysis = data_analysis_service
    
    async def process_message(
        self,
        agent_config: AgentConfig,
        message: WebhookMessage,
        stream: bool = False,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[str]:
        """Processa uma mensagem com o agente e retorna resposta em stream"""
        
        conversation_id = message.conversation_id or str(uuid.uuid4())
        history = history or []
        
        try:
            # Recupera contextos RAG se configurado (apenas para a última mensagem)
            contexts: List[RAGContext] = []
            if agent_config.rag:
                contexts = await self.rag.retrieve_context(
                    query=message.text,
                    agent_config=agent_config
                )
            
            # Constrói conteúdo da mensagem do usuário com RAG (se houver contextos)
            if contexts:
                # Se houver RAG, enriquece apenas a última mensagem com contexto
                # Monta prompt com contextos, mas sem system prompt (já está no início)
                def _format_metadata(md: Optional[Dict[str, Any]]) -> str:
                    if not md:
                        return ""
                    source_file = md.get("source_file") or md.get("source") or ""
                    chunk_index = md.get("chunk_index")
                    total_chunks = md.get("total_chunks")
                    file_type = md.get("file_type") or ""
                    parts = []
                    if source_file:
                        parts.append(f"Fonte: {source_file}")
                    if chunk_index is not None and total_chunks is not None:
                        parts.append(f"Chunk: {int(chunk_index) + 1}/{int(total_chunks)}")
                    if file_type:
                        parts.append(f"Tipo: {file_type}")
                    return " | ".join(parts)

                context_text = "\n\n".join(
                    [
                        "\n".join(
                            [
                                f"[Contexto {i+1}] (score={ctx.score:.3f})",
                                _format_metadata(ctx.metadata),
                                ctx.content,
                            ]
                        ).strip()
                        for i, ctx in enumerate(contexts)
                    ]
                )
                
                user_content = f"""Contextos relevantes:
{context_text}

Com base nos contextos acima, responda à seguinte pergunta:

Pergunta: {message.text}"""
            else:
                user_content = f"""Nenhum contexto foi recuperado da base de conhecimento (RAG) deste agente.

Pergunta: {message.text}

Instrução: se a resposta depender de documentos internos, informe que não há trechos recuperados e oriente como melhorar a consulta ou acionar a carga de documentos."""
            
            # Prepara mensagens para OpenAI com histórico completo
            messages = [{"role": "system", "content": agent_config.system_prompt}]
            
            # Adiciona histórico de mensagens anteriores
            for hist_msg in history:
                if hist_msg.get("role") in ["user", "assistant"]:
                    messages.append({
                        "role": hist_msg["role"],
                        "content": hist_msg.get("content", "")
                    })
            
            # Adiciona a mensagem atual do usuário
            messages.append({"role": "user", "content": user_content})
            
            # Prepara tools se houver
            tools = None
            if agent_config.tools or (agent_config.data_analysis and agent_config.data_analysis.enabled):
                tools = self._prepare_tools(agent_config)
            
            # Stream resposta
            if stream:
                tool_calls_received = None
                async for chunk in self.openai.chat_completion_stream(
                    messages=messages,
                    model=agent_config.model,
                    tools=tools
                ):
                    if chunk.get("type") == "content":
                        yield chunk["data"]
                    elif chunk.get("type") == "tool_calls":
                        tool_calls_received = chunk["data"]
                
                # Se houver tool calls, processa
                if tool_calls_received:
                    # Adiciona mensagem do assistente
                    assistant_message = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls_received
                    }
                    messages.append(assistant_message)
                    
                    # Executa cada tool call
                    for tool_call in tool_calls_received:
                        function_name = tool_call.get("function", {}).get("name", "")
                        function_args_str = tool_call.get("function", {}).get("arguments", "{}")
                        tool_call_id = tool_call.get("id", "")
                        
                        try:
                            function_args = json.loads(function_args_str)
                        except:
                            function_args = {}
                        
                        # Executa função
                        if function_name == "query_data" and self.data_analysis:
                            query_result = await self.execute_data_query(agent_config.id, function_args.get('query', ''))
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(query_result, ensure_ascii=False, default=str)
                            })
                        else:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps({"success": False, "error": f"Tool {function_name} not implemented"})
                            })
                    
                    # Faz segunda chamada com resultados das tools e streama resposta final
                    async for chunk in self.openai.chat_completion_stream(
                        messages=messages,
                        model=agent_config.model,
                        tools=tools
                    ):
                        if chunk.get("type") == "content":
                            yield chunk["data"]
            else:
                response = await self.openai.chat_completion(
                    messages=messages,
                    model=agent_config.model,
                    tools=tools
                )
                yield response['content']
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            yield f"Erro ao processar mensagem: {str(e)}"
    
    async def process_message_sync(
        self,
        agent_config: AgentConfig,
        message: WebhookMessage,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AgentResponse:
        """Processa uma mensagem de forma síncrona (para worker)"""
        
        conversation_id = message.conversation_id or str(uuid.uuid4())
        tokens_used = None
        
        try:
            # Recupera contextos RAG se configurado
            contexts: List[RAGContext] = []
            if agent_config.rag:
                contexts = await self.rag.retrieve_context(
                    query=message.text,
                    agent_config=agent_config
                )
            
            # Constrói conteúdo da mensagem do usuário com RAG (se houver contextos)
            if contexts:
                def _format_metadata(md: Optional[Dict[str, Any]]) -> str:
                    if not md:
                        return ""
                    source_file = md.get("source_file") or md.get("source") or ""
                    chunk_index = md.get("chunk_index")
                    total_chunks = md.get("total_chunks")
                    file_type = md.get("file_type") or ""
                    parts = []
                    if source_file:
                        parts.append(f"Fonte: {source_file}")
                    if chunk_index is not None and total_chunks is not None:
                        parts.append(f"Chunk: {int(chunk_index) + 1}/{int(total_chunks)}")
                    if file_type:
                        parts.append(f"Tipo: {file_type}")
                    return " | ".join(parts)

                context_text = "\n\n".join(
                    [
                        "\n".join(
                            [
                                f"[Contexto {i+1}] (score={ctx.score:.3f})",
                                _format_metadata(ctx.metadata),
                                ctx.content,
                            ]
                        ).strip()
                        for i, ctx in enumerate(contexts)
                    ]
                )
                
                user_content = f"""Contextos relevantes:
{context_text}

Com base nos contextos acima, responda à seguinte pergunta:

Pergunta: {message.text}"""
            else:
                user_content = f"""Nenhum contexto foi recuperado da base de conhecimento (RAG) deste agente.

Pergunta: {message.text}

Instrução: se a resposta depender de documentos internos, informe que não há trechos recuperados e oriente como melhorar a consulta ou acionar a carga de documentos."""
            
            # Prepara mensagens para OpenAI com histórico completo
            messages = [{"role": "system", "content": agent_config.system_prompt}]
            
            # Adiciona histórico de mensagens anteriores
            for hist_msg in (history or []):
                if hist_msg.get("role") in ["user", "assistant"]:
                    messages.append({
                        "role": hist_msg["role"],
                        "content": hist_msg.get("content", "")
                    })
            
            # Adiciona a mensagem atual do usuário
            messages.append({"role": "user", "content": user_content})
            
            # Prepara tools se houver
            tools = None
            if agent_config.tools or (agent_config.data_analysis and agent_config.data_analysis.enabled):
                tools = self._prepare_tools(agent_config)
            
            # Chama API diretamente para capturar tokens
            response = await self.openai.chat_completion(
                messages=messages,
                model=agent_config.model,
                tools=tools
            )
            
            # Processa tool calls se houver
            tool_calls = response.get('tool_calls')
            if tool_calls:
                # Adiciona mensagem do assistente com tool calls
                assistant_message = {
                    "role": "assistant",
                    "content": response.get('content'),
                    "tool_calls": []
                }
                
                # Executa cada tool call
                for tool_call in tool_calls:
                    # Converte tool_call para dict se necessário
                    if hasattr(tool_call, 'function'):
                        function_name = tool_call.function.name
                        function_args_str = tool_call.function.arguments
                        tool_call_id = tool_call.id
                    else:
                        # Se já for dict
                        function_name = tool_call.get('function', {}).get('name', '')
                        function_args_str = tool_call.get('function', {}).get('arguments', '{}')
                        tool_call_id = tool_call.get('id', '')
                    
                    # Adiciona tool call à mensagem
                    assistant_message["tool_calls"].append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": function_args_str
                        }
                    })
                    
                    # Parse dos argumentos
                    try:
                        function_args = json.loads(function_args_str)
                    except:
                        function_args = {}
                    
                    # Executa função
                    if function_name == "query_data" and self.data_analysis:
                        query_result = await self.execute_data_query(agent_config.id, function_args.get('query', ''))
                        # Adiciona resultado como mensagem de tool
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(query_result, ensure_ascii=False, default=str)
                        })
                    else:
                        # Para outras tools, retorna erro
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"success": False, "error": f"Tool {function_name} not implemented"})
                        })
                
                # Adiciona mensagem do assistente
                messages.append(assistant_message)
                
                # Faz segunda chamada com resultados das tools
                final_response = await self.openai.chat_completion(
                    messages=messages,
                    model=agent_config.model,
                    tools=tools
                )
                response_text = final_response.get('content', '')
                tokens_used = (response.get('tokens_used', 0) or 0) + (final_response.get('tokens_used', 0) or 0)
            else:
                response_text = response.get('content', '')
                tokens_used = response.get('tokens_used')
        
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            response_text = f"Erro ao processar mensagem: {str(e)}"
        
        return AgentResponse(
            agent_id=agent_config.id,
            conversation_id=conversation_id,
            response=response_text,
            contexts=contexts if 'contexts' in locals() else [],
            tokens_used=tokens_used
        )
    
    def _prepare_tools(self, agent_config: AgentConfig) -> List[Dict[str, Any]]:
        """Prepara tools para function calling da OpenAI"""
        openai_tools = []
        
        # Adiciona tools configuradas do agente
        for tool in agent_config.tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Tool: {tool.name}",
                    "parameters": tool.parameters or {}
                }
            }
            openai_tools.append(openai_tool)
        
        # Adiciona tool de análise de dados se habilitada
        if agent_config.data_analysis and agent_config.data_analysis.enabled and self.data_analysis:
            # Carrega arquivos se ainda não estiverem carregados
            if agent_config.data_analysis.files:
                self.data_analysis.load_agent_files(agent_config.id, agent_config.data_analysis.files)
            
            # Obtém informações dos DataFrames
            df_info = self.data_analysis.get_dataframe_info(agent_config.id)
            
            # Cria tool de query
            data_tool = {
                "type": "function",
                "function": {
                    "name": "query_data",
                    "description": "Executa queries em dados carregados (CSV, JSON, XLSX) usando pandas. Use esta ferramenta para analisar dados, filtrar, agregar, calcular estatísticas, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": f"Query pandas a ser executada. Dados disponíveis: {json.dumps(df_info, indent=2) if df_info.get('files') else 'Nenhum arquivo carregado'}. Exemplos: 'df.head()', 'df.describe()', 'df[df[\"coluna\"] > 10]', 'df.groupby(\"coluna\").sum()'"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
            openai_tools.append(data_tool)
        
        return openai_tools if openai_tools else None
    
    async def execute_data_query(self, agent_id: str, query: str) -> Dict[str, Any]:
        """Executa uma query de análise de dados"""
        if not self.data_analysis:
            return {"success": False, "error": "Data analysis service not available"}
        
        # Executa de forma síncrona (pandas é síncrono)
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.data_analysis.execute_query, agent_id, query)
        return result
