"""
LangChain agent logic for chat completions.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Load environment variables
load_dotenv()

# System prompt for the AI assistant
SYSTEM_PROMPT = """You are a helpful AI assistant designed for everyday use. You can help with:
- Answering questions on various topics
- Writing and editing text
- Brainstorming ideas
- Explaining concepts clearly
- Providing suggestions and recommendations

Be friendly, concise, and helpful in your responses. If you're unsure about something, say so honestly."""


def get_llm():
    """Initialize and return the Gemini LLM."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.7,
        convert_system_message_to_human=True
    )


def format_chat_history(messages: list[dict]) -> list:
    """Convert chat history to LangChain message format."""
    formatted = [SystemMessage(content=SYSTEM_PROMPT)]
    
    for msg in messages:
        if msg["role"] == "user":
            formatted.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            formatted.append(AIMessage(content=msg["content"]))
    
    return formatted


def get_agent_response(user_message: str, chat_history: list[dict] = None) -> str:
    """
    Get a response from the AI agent.
    
    Args:
        user_message: The user's input message
        chat_history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
    
    Returns:
        The AI's response as a string
    """
    if chat_history is None:
        chat_history = []
    
    try:
        llm = get_llm()
        
        # Format the conversation history
        messages = format_chat_history(chat_history)
        messages.append(HumanMessage(content=user_message))
        
        # Get response from the model
        response = llm.invoke(messages)
        
        return response.content
    
    except Exception as e:
        error_msg = str(e)
        if "API key" in error_msg.lower():
            raise ValueError("Invalid or missing Google API key")
        raise Exception(f"Error getting response: {error_msg}")
