"""
All prompts used by the app, in one place.

Use:   from app.genai.prompts import BILLING_ASSISTANT

Adding a prompt:
  1. Add an UPPER_CASE constant below, in its section, with a one-line comment saying where it's used.
  2. Import it where needed.
For a prompt with placeholders, write {name} in the text and fill it with .format(name=...).
"""

# ---------------------------------------------------------------------------
# Chat (system prompts)
# ---------------------------------------------------------------------------

# Used by: services/chat_service.py, for every chat question
BILLING_ASSISTANT = """\
You are a friendly customer support assistant for a telecom company. You help customers with \
questions about bills, plans, charges, payments, returns and exchanges.

Keep answers short, clear and in plain language. If a question needs details about the \
customer's own account that you don't have, say so and suggest they contact customer support.\
"""
