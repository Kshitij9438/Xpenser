from asyncio import wait_for, TimeoutError
from fastapi import HTTPException

from core.intent import Intent
from executors.base import BaseExecutor
from services.utils import deep_serialize


class ConversationExecutor(BaseExecutor):
    """
    Executes conversation-type intents.
    """

    async def execute(self, intent: Intent) -> dict:
        try:
            from agents.conversation_agent import handle_conversation

            try:
                conversation_result = await wait_for(
                    handle_conversation(intent.raw_input, intent.user_id),
                    timeout=30,
                )
            except TimeoutError:
                raise HTTPException(
                    status_code=504,
                    detail="Conversation timed out",
                )

            return {
                "type": "conversation",
                "data": deep_serialize(conversation_result),
                "message": conversation_result.response,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e),
            )
