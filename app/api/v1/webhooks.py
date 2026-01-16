from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.dependencies import get_container
from app.core.container import Container

from app.schemas.webhook import MessageChannel, WebhookMessage

from app.utils.logging import logger

import bleach
import time
import json

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@webhook_router.post("/{webhook_name}")
async def webhook_entry_by_name(webhook_name: str, request: Request, container: Container = Depends(get_container)):
    """Endpoint de webhook usando nome personalizado"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agent_config = container.agent_loader.get_agent_by_webhook_name(webhook_name)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_name} not found")
    
    return await webhook_entry(agent_config.id, request, container)


@webhook_router.post("/agent/{agent_id}")
async def webhook_entry(agent_id: str, request: Request, container: Container = Depends(get_container)):
    """Endpoint de webhook para receber mensagens"""
    
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    start_time = time.time()
    success = False
    tokens_used = None
    
    try:
        body = await request.json()
        
        def sanitize_input(value):
            """Sanitiza entrada de dados usando Bleach"""
            if value is None:
                return None
            if isinstance(value, str):
                return bleach.clean(
                    value, 
                    tags=['b', 'i', 'u', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre'],
                    attributes={'a': ['href', 'title', 'target']},
                    strip=True
                )
            elif isinstance(value, dict):
                return {k: sanitize_input(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_input(item) for item in value]
            return value
        
        history = body.get("history", [])
        if history:
            history = sanitize_input(history)
        
        sanitized_text = sanitize_input(body.get("text", ""))
        sanitized_user_id = sanitize_input(body.get("user_id", "unknown"))
        sanitized_metadata = sanitize_input(body.get("metadata", {}))
        sanitized_conversation_id = sanitize_input(body.get("conversation_id"))
        
        message = WebhookMessage(
            user_id=sanitized_user_id, # type: ignore
            channel=MessageChannel(body.get("channel", "web")),
            text=sanitized_text, # type: ignore
            metadata=sanitized_metadata if isinstance(sanitized_metadata, dict) else {},
            conversation_id=sanitized_conversation_id # type: ignore
        )
        
        stream = body.get("stream", False)
        
        if stream:
            async def generate():
                nonlocal success
                try:
                    async for token in container.agent_service.process_message(
                        agent_config, message, stream=True, history=history # type: ignore
                    ):
                        yield f"data: {json.dumps(token, ensure_ascii=False)}\n\n"
                    success = True
                except Exception as e:
                    logger.error(f"Error in stream: {e}", exc_info=True)
                    yield f"data: {json.dumps(f'[ERRO: {str(e)}]', ensure_ascii=False)}\n\n"
                    success = False
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        else:
            job_data = {
                "agent_id": agent_id,
                "message": message.model_dump(),
                "history": history,
                "stream": False,
                "webhook_output_url": agent_config.webhook_output_url
            }
            
            job_id = await container.redis_client.enqueue_job(job_data)
            success = True
            
            return JSONResponse({
                "status": "enqueued",
                "job_id": job_id,
                "agent_id": agent_id
            })
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        success = False
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if container.metrics_service and not stream: # type: ignore
            response_time = time.time() - start_time
            await container.metrics_service.record_message(
                agent_id=agent_id,
                user_id=message.user_id if 'message' in locals() else "unknown", # type: ignore
                channel=message.channel.value if 'message' in locals() else "web", # type: ignore
                response_time=response_time,
                tokens_used=tokens_used,
                success=success
            )
