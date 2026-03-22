"""Chat routes: synchronous and streaming."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from .. import crud, schemas, database, agent, auth
from .deps import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    chat_request: schemas.ChatRequest,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Send a message and get AI response."""
    session = crud.get_session(db, chat_request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found"})

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    messages = crud.get_session_messages(db, chat_request.session_id)
    chat_history = [{"role": msg.role, "content": msg.content} for msg in messages]

    user_message = crud.save_message(
        db, chat_request.session_id, "user", chat_request.message,
        image_url=chat_request.image_url,
    )

    if len(messages) == 0:
        title = chat_request.message[:50]
        if len(chat_request.message) > 50:
            title += "..."
        crud.update_session_title(db, chat_request.session_id, title)

    try:
        ai_response, trace_data = await agent.get_agent_response(
            chat_request.message, chat_history, chat_request.image_url,
            user_id=str(current_user.id),
            user_name=current_user.name,
        )

        assistant_message = crud.save_message(
            db, chat_request.session_id, "assistant", ai_response,
            trace_json=trace_data,
        )

        return schemas.ChatResponse(
            session_id=chat_request.session_id,
            user_message=user_message,
            assistant_message=assistant_message,
            trace=trace_data,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "CHAT_AGENT_ERROR", "message": f"AI agent failed: {e}"})


@router.post("/stream")
@limiter.limit("20/minute")
async def chat_stream(
    request: Request,
    chat_request: schemas.ChatRequest,
    current_user: database.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Send a message and stream the AI response token-by-token via SSE.

    Events:
      - event: token   -> {"token": "..."}
      - event: done    -> {"user_message": {...}, "assistant_message": {...}}
      - event: error   -> {"error": {"code": "...", "message": "..."}}
    """
    session = crud.get_session(db, chat_request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found"})
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "ACCESS_DENIED", "message": "You do not have permission to access this resource"})

    messages = crud.get_session_messages(db, chat_request.session_id)
    chat_history = [{"role": msg.role, "content": msg.content} for msg in messages]

    user_message = crud.save_message(
        db, chat_request.session_id, "user", chat_request.message,
        image_url=chat_request.image_url,
    )

    if len(messages) == 0:
        title = chat_request.message[:50] + ("..." if len(chat_request.message) > 50 else "")
        crud.update_session_title(db, chat_request.session_id, title)

    user_msg_dict = schemas.MessageResponse.model_validate(user_message).model_dump(mode="json")

    # Extract values before request-scoped db session closes
    _user_id = str(current_user.id)
    _user_name = current_user.name
    _session_id = chat_request.session_id
    _message = chat_request.message
    _image_url = chat_request.image_url

    async def event_generator():
        import json as _json

        full_response = []
        trace_data = None
        try:
            async for token in agent.stream_agent_response(
                _message, chat_history, _image_url,
                user_id=_user_id,
                user_name=_user_name,
            ):
                # Intercept trace marker from the agent stream
                if isinstance(token, str) and token.startswith("__TRACE__:"):
                    try:
                        trace_data = _json.loads(token[len("__TRACE__:"):])
                    except _json.JSONDecodeError:
                        pass
                    continue
                full_response.append(token)
                yield {"event": "token", "data": _json.dumps({"token": token})}

            complete_text = "".join(full_response)
            try:
                gen_db = database.SessionLocal()
                try:
                    assistant_message = crud.save_message(
                        gen_db, _session_id, "assistant", complete_text,
                        trace_json=trace_data,
                    )
                    asst_msg_dict = schemas.MessageResponse.model_validate(assistant_message).model_dump(mode="json")
                finally:
                    gen_db.close()

                yield {
                    "event": "done",
                    "data": _json.dumps({"user_message": user_msg_dict, "assistant_message": asst_msg_dict}),
                }
                if trace_data:
                    yield {"event": "trace", "data": _json.dumps(trace_data)}
            except Exception as db_err:
                logger.error("Failed to save streamed response for session %s: %s", _session_id, db_err)
                yield {
                    "event": "done",
                    "data": _json.dumps({
                        "user_message": user_msg_dict,
                        "assistant_message": None,
                        "save_error": "Response was generated but could not be saved.",
                    }),
                }
                if trace_data:
                    yield {"event": "trace", "data": _json.dumps(trace_data)}

        except Exception as e:
            logger.exception("Streaming chat error for session %s: %s", _session_id, e)
            yield {
                "event": "error",
                "data": _json.dumps({"error": {"code": "CHAT_AGENT_ERROR", "message": str(e)}}),
            }

    return EventSourceResponse(event_generator())
