import os
import asyncio
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class HybridMemory:
    def __init__(self, window_size=4, summary_threshold=6):
        """
        window_size: how many recent messages to keep in full
        summary_threshold: how many messages before we summarize old ones
        
        Example with window_size=4, summary_threshold=10:
        - Turns 1-10 accumulate
        - At turn 11, turns 1-2 get summarized
        - Turns 3-10 stay in full (window of 4)
        - Turn 11 added to window
        """
        self.window_size = window_size
        self.summary_threshold = summary_threshold
        self.recent_messages = []
        self.summary = ""
        self.total_turns = 0

    def add_message(self, role: str, content: str):
        """Add a new message to memory."""
        self.recent_messages.append({
            "role": role,
            "content": content
        })
        self.total_turns += 1

    async def maybe_summarize(self):
        """
        If recent messages exceed summary_threshold,
        summarize the oldest ones and keep only window_size recent ones.
        Called after every assistant response.
        """
        if len(self.recent_messages) <= self.summary_threshold:
            return  # Not enough messages yet

        # Split: messages to summarize vs messages to keep
        messages_to_summarize = self.recent_messages[:-self.window_size]
        print(f"[MEMORY DEBUG] Messages being summarized:")
        for m in messages_to_summarize:
            print(f"  {m['role']}: {m['content']}")
        self.recent_messages = self.recent_messages[-self.window_size:]

        print(f"[MEMORY] Summarizing {len(messages_to_summarize)} old messages...")

        # Build text of messages to summarize
        conversation_text = "\n".join([
            f"{m['role'].upper()}: {m['content']}"
            for m in messages_to_summarize
        ])

        # If we already have a summary, include it
        if self.summary:
            conversation_text = f"Previous summary: {self.summary}\n\n{conversation_text}"

        # Call Groq to summarize
        def _summarize():
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        
                        "role": "system",
                        "content": """You are summarizing a real estate leasing conversation.
                                        You MUST capture ALL of these if mentioned:
                                        - Budget/price range
                                        - Pet requirements (has pets or not)
                                        - Preferred neighborhoods or areas
                                        - Unit type (bachelor, 1 bed, 2 bed)
                                        - Parking requirements
                                        - Utilities requirements
                                        - Any specific properties discussed or shown interest in
                                        Be concise but capture every important detail. Max 3 sentences."""

                    },
                    {
                        "role": "user",
                        "content": f"Summarize this conversation:\n\n{conversation_text}"
                    }
                ],
                max_tokens=150,
                temperature=0.0
            )
            return response.choices[0].message.content

        loop = asyncio.get_event_loop()
        self.summary = await loop.run_in_executor(None, _summarize)
        print(f"[MEMORY] Summary: {self.summary}")

    def get_context(self) -> list:
        """
        Returns messages to send to Groq.
        Format: summary (if exists) + recent messages in full
        """
        messages = []

        # Add summary as system context if it exists
        if self.summary:
            messages.append({
                "role": "user",
                "content": f"[Context from earlier in conversation: {self.summary}]"
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I have context from our earlier conversation."
            })

        # Add recent messages in full
        messages.extend(self.recent_messages)

        return messages

    def clear(self):
        """Reset memory when conversation ends."""
        self.recent_messages = []
        self.summary = ""
        self.total_turns = 0
        print("[MEMORY] Conversation ended - memory cleared")

    def status(self):
        """Print current memory state - useful for debugging."""
        print(f"[MEMORY] Total turns: {self.total_turns}")
        print(f"[MEMORY] Recent messages: {len(self.recent_messages)}")
        print(f"[MEMORY] Has summary: {bool(self.summary)}")
        if self.summary:
            print(f"[MEMORY] Summary: {self.summary}")