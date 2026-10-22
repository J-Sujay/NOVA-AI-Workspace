
"""NOVA chatbot backend: Gemini responses, document Q&A, sentiment analysis, and MySQL history."""
from __future__ import annotations

import os
import re
import string
from pathlib import Path
from typing import Any

import mysql.connector
import streamlit as st
from dotenv import load_dotenv
from google import genai

# --------------------------------------------------
# 1. Project configuration
# --------------------------------------------------

PROJECT_FOLDER = Path(__file__).resolve().parent
load_dotenv(PROJECT_FOLDER / ".env", override=False)


def _setting(name: str, default: str = "") -> str:
    """Read Streamlit Secrets first, then environment/.env values locally."""
    try:
        value = st.secrets.get(name, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    except Exception:
        # Streamlit Secrets may not exist when running outside Streamlit.
        pass

    value = os.getenv(name, "").strip()
    return value if value else default


API_KEY = _setting("GEMINI_API_KEY")
MODEL_NAME = _setting("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"
client = genai.Client(api_key=API_KEY) if API_KEY else None

MYSQL_HOST = _setting("MYSQL_HOST", "localhost")
MYSQL_PORT = int(_setting("MYSQL_PORT", "3306"))
MYSQL_USER = _setting("MYSQL_USER", "root")
MYSQL_PASSWORD = _setting("MYSQL_PASSWORD")
MYSQL_DATABASE = _setting("MYSQL_DATABASE", "nova_chatbot")
MYSQL_SSL_DISABLED = _setting(
    "MYSQL_SSL_DISABLED",
    "true" if MYSQL_HOST.lower() in {"localhost", "127.0.0.1"} else "false",
).lower() in {"1", "true", "yes"}
MYSQL_SSL_CA = _setting("MYSQL_SSL_CA")

MYSQL_CONFIG = {
    "host": MYSQL_HOST,
    "port": MYSQL_PORT,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "database": MYSQL_DATABASE,
    "connection_timeout": 10,
    "ssl_disabled": MYSQL_SSL_DISABLED,
}

# If an Aiven CA certificate path is configured, verify the server certificate
# and hostname. For production, configure MYSQL_SSL_CA with Aiven's CA file.
if MYSQL_SSL_CA and not MYSQL_SSL_DISABLED:
    MYSQL_CONFIG["ssl_ca"] = MYSQL_SSL_CA
    MYSQL_CONFIG["ssl_verify_cert"] = True
    MYSQL_CONFIG["ssl_verify_identity"] = True

# --------------------------------------------------
# 2. Knowledge document
# --------------------------------------------------

KNOWLEDGE_FILE = PROJECT_FOLDER / "nova_knowledge.txt"

try:
    document_knowledge = KNOWLEDGE_FILE.read_text(
        encoding="utf-8"
    ).strip()
except OSError:
    document_knowledge = ""

conversation_history: list[dict[str, str]] = []
MAX_HISTORY_MESSAGES = 10


# --------------------------------------------------
# 3. MySQL connection and history
# --------------------------------------------------

def _connect_database():
    """Open a MySQL connection using configured credentials."""
    return mysql.connector.connect(**MYSQL_CONFIG)


def _ensure_schema(connection) -> None:
    """Create the conversation table if it does not exist."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_message TEXT NOT NULL,
                nova_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()


def get_database_status() -> tuple[bool, str]:
    """Return connection status and a safe, human-readable message."""
    connection = None
    try:
        connection = _connect_database()
        _ensure_schema(connection)
        return True, "Connected to MySQL; the conversations table is ready."
    except mysql.connector.Error as error:
        # Details appear only in Streamlit logs; never display credentials to users.
        print(f"[NOVA MySQL] Connection check failed: {type(error).__name__}: {error}")
        return False, (
            "MySQL is unavailable. Check the cloud database connection, "
            "credentials, network access, and SSL configuration."
        )
    except (ValueError, TypeError) as error:
        print(f"[NOVA MySQL] Invalid configuration ({type(error).__name__}).")
        return False, "MySQL configuration is invalid. Check the configured port and settings."
    finally:
        if connection is not None:
            try:
                connection.close()
            except mysql.connector.Error:
                pass


def save_conversation(user_message: str, nova_response: str) -> bool:
    """Save one exchange to MySQL; return whether saving succeeded."""
    connection = None
    cursor = None

    try:
        connection = _connect_database()
        _ensure_schema(connection)
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO conversations (user_message, nova_response)
            VALUES (%s, %s)
            """,
            (str(user_message), str(nova_response)),
        )
        connection.commit()
        return True

    except mysql.connector.Error as error:
        print(f"[NOVA MySQL] Could not save conversation: {type(error).__name__}: {error}")
        return False

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except mysql.connector.Error:
                pass

        if connection is not None:
            try:
                connection.close()
            except mysql.connector.Error:
                pass


def get_recent_conversations(
    limit: int = 50,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return recent saved records and an error message, if any."""
    connection = None
    cursor = None

    try:
        safe_limit = max(1, min(int(limit), 200))
        connection = _connect_database()
        _ensure_schema(connection)
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, user_message, nova_response, created_at
            FROM conversations
            ORDER BY id DESC
            LIMIT %s
            """,
            (safe_limit,),
        )

        return cursor.fetchall(), None

    except (mysql.connector.Error, ValueError, TypeError) as error:
        print(f"[NOVA MySQL] Could not read conversation history: {type(error).__name__}: {error}")
        return [], (
            "Could not load MySQL history. Check the database connection "
            "and configuration."
        )

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except mysql.connector.Error:
                pass

        if connection is not None:
            try:
                connection.close()
            except mysql.connector.Error:
                pass


# --------------------------------------------------
# 4. Predefined chatbot responses
# --------------------------------------------------

def predefined_response(message: str) -> str | None:
    normalized = message.strip().lower().strip(string.punctuation + " ")

    responses = {
        "hi": "Hi! I'm NOVA, your AI assistant. How can I help you today?",
        "hello": "Hello! I'm NOVA. What would you like to know?",
        "hey": "Hey! How can I help you?",
        "good morning": "Good morning! What can I help you with today?",
        "good afternoon": "Good afternoon! How can I help?",
        "good evening": "Good evening! What would you like to explore?",
        "who are you": (
            "I'm NOVA, an AI chatbot built with Python, Gemini AI, "
            "Streamlit, and MySQL."
        ),
        "what is nova": (
            "NOVA is an AI chatbot project built with Python and Gemini AI. "
            "It can answer questions, use a local knowledge document, "
            "analyze simple text sentiment, and store conversations in MySQL."
        ),
        "what can you do": (
            "I can answer general questions, answer questions about NOVA's "
            "local knowledge document, perform simple word-based sentiment "
            "analysis, and save conversations in MySQL. Use the sidebar "
            "to open each tool."
        ),
        "bye": "Goodbye! Thanks for chatting with NOVA.",
        "thank you": "You're welcome! Let me know if you need anything else.",
        "thanks": "You're welcome!",
    }

    return responses.get(normalized)


# --------------------------------------------------
# 5. Document Q&A
# --------------------------------------------------

def answer_from_document(question: str) -> str:
    """Answer from nova_knowledge.txt using direct matches and keyword scoring."""
    if not document_knowledge:
        return (
            "I can't access nova_knowledge.txt. Check that the file is "
            "in the NOVA_Chatbot project folder."
        )

    question = question.strip()
    if not question:
        return "Please enter a question about NOVA's knowledge document."

    normalized = re.sub(
        r"\s+", " ", question.lower()
    ).strip(string.punctuation + " ")

    direct_answers = {
        "which database does nova use": (
            "NOVA uses MySQL to store user messages, chatbot responses, "
            "and timestamps."
        ),
        "what database does nova use": (
            "NOVA uses MySQL to store user messages, chatbot responses, "
            "and timestamps."
        ),
        "which ai does nova use": "NOVA uses Gemini AI to answer user questions.",
        "what ai does nova use": "NOVA uses Gemini AI to answer user questions.",
        "what does mysql store": (
            "MySQL stores user messages, chatbot responses, and timestamps."
        ),
        "what is nova": (
            "NOVA is an AI chatbot built using Python. "
            "It uses Gemini AI to answer user questions."
        ),
        "what language is nova built with": "NOVA is built using Python.",
    }

    if normalized in direct_answers:
        return direct_answers[normalized]

    lines = [
        line.strip()
        for line in document_knowledge.splitlines()
        if line.strip()
    ]

    if any(
        term in normalized
        for term in ("summarize", "summary", "overview", "all information")
    ):
        return (
            "Here's the information available in NOVA's knowledge document:\n\n"
            + "\n".join(f"- {line}" for line in lines)
        )

    stop_words = {
        "what", "which", "does", "this", "that", "with", "from", "have",
        "about", "tell", "show", "give", "use", "used", "the", "and",
        "for", "are", "how", "who", "why", "can", "you", "nova", "is",
        "a", "an", "to", "in", "of", "it", "do", "where", "when",
        "built", "using",
    }

    question_terms = {
        token.strip(string.punctuation)
        for token in normalized.split()
        if len(token.strip(string.punctuation)) > 2
    } - stop_words

    scored_lines = []

    for line in lines:
        line_terms = {
            token.strip(string.punctuation).lower()
            for token in line.split()
        }
        score = len(question_terms & line_terms)

        if score:
            scored_lines.append((score, line))

    if scored_lines:
        best_score = max(score for score, _ in scored_lines)
        best_lines = list(
            dict.fromkeys(
                line for score, line in scored_lines
                if score == best_score
            )
        )
        return (
            "According to NOVA's knowledge document:\n\n"
            + "\n".join(f"- {line}" for line in best_lines)
        )

    return (
        "I couldn't find a direct answer in NOVA's knowledge document.\n\n"
        "Here's the available information:\n\n"
        + "\n".join(f"- {line}" for line in lines)
    )


# --------------------------------------------------
# 6. Sentiment analysis
# --------------------------------------------------

def analyze_sentiment(text: str) -> str:
    """Simple lexicon-based sentiment estimate."""
    positive_words = {
        "good", "great", "happy", "excellent", "love", "like", "liked",
        "excited", "wonderful", "amazing", "positive", "success", "best",
        "enjoy", "helpful", "fantastic", "pleased", "awesome", "beautiful",
        "perfect", "glad", "brilliant",
    }

    negative_words = {
        "bad", "sad", "angry", "hate", "hated", "terrible", "awful",
        "negative", "problem", "poor", "worst", "upset", "disappointed",
        "fail", "failure", "difficult", "stress", "annoyed", "useless",
        "boring", "broken",
    }

    words = [
        word.lower().strip(string.punctuation)
        for word in text.split()
    ]

    positive_count = sum(word in positive_words for word in words)
    negative_count = sum(word in negative_words for word in words)

    if positive_count > negative_count:
        label = "Positive"
    elif negative_count > positive_count:
        label = "Negative"
    else:
        label = "Neutral"

    return (
        f"**Sentiment: {label}**\n\n"
        f"- Positive words detected: {positive_count}\n"
        f"- Negative words detected: {negative_count}\n\n"
        "Note: This is a simple word-based estimate, not a trained sentiment model."
    )


# --------------------------------------------------
# 7. Gemini AI response
# --------------------------------------------------

def generate_ai_response(message: str) -> str:
    if client is None:
        return (
            "Gemini is not configured. Add GEMINI_API_KEY to your "
            "local .env file or Streamlit Cloud Secrets."
        )

    history_text = "\n".join(
        f"{item['role'].capitalize()}: {item['content']}"
        for item in conversation_history[-MAX_HISTORY_MESSAGES:]
    )

    prompt = (
        "You are NOVA, a helpful, professional AI assistant. "
        "Answer clearly and accurately. If unsure, say so. "
        "Do not claim to have performed actions you did not perform.\n\n"
    )

    if history_text:
        prompt += f"Recent conversation:\n{history_text}\n\n"

    prompt += f"User: {message}\nNOVA:"

    try:
        result = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )

        answer = getattr(result, "text", None)

        if answer and answer.strip():
            return answer.strip()

        return "I couldn't generate a response just now. Please try rephrasing your question."

    except Exception as error:
        print(f"[NOVA Gemini] Request failed ({type(error).__name__}).")
        return (
            "I'm having trouble connecting to Gemini. Check your internet "
            "connection, API key, and model name, then try again."
        )


# --------------------------------------------------
# 8. Main response router
# --------------------------------------------------

def get_response(user_message: str) -> str:
    """Route a message to the right feature and persist the exchange when possible."""
    message = str(user_message).strip()

    if not message:
        return "Please enter a message so I can help."

    if message.lower() in {"clear", "clear history", "restart", "reset"}:
        conversation_history.clear()

        response = (
            "In-memory conversation context cleared. "
            "Saved MySQL records are preserved."
        )

        if not save_conversation(message, response):
            response += "\n\n⚠️ Note: This conversation could not be saved to MySQL."

        return response

    if message.lower().startswith("document:"):
        response = answer_from_document(message.split(":", 1)[1].strip())

    elif message.lower().startswith("sentiment:"):
        response = analyze_sentiment(message.split(":", 1)[1].strip())

    else:
        response = predefined_response(message)

        if response is None:
            response = generate_ai_response(message)

    conversation_history.extend([
        {"role": "user", "content": message},
        {"role": "assistant", "content": response},
    ])

    del conversation_history[:-MAX_HISTORY_MESSAGES]

    if not save_conversation(message, response):
        response += "\n\n⚠️ Note: This conversation could not be saved to MySQL."

    return response


# --------------------------------------------------
# 9. Terminal mode
# --------------------------------------------------

def main() -> None:
    print("\n🤖 NOVA Chatbot")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            message = input("You: ").strip()

        except (EOFError, KeyboardInterrupt):
            print("\nNOVA: Goodbye!")
            break

        if message.lower() in {"exit", "quit"}:
            print("NOVA: Goodbye!")
            break

        if message:
            print(f"NOVA: {get_response(message)}\n")


if __name__ == "__main__":
    main()
