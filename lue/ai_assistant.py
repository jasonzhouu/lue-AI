"""
AI Assistant module for Lue e-book reader.
Integrates with Google Gemini API to provide reading assistance.
"""

import os
import asyncio
import logging
from typing import List, Dict, Optional, Tuple

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from . import content_parser

logger = logging.getLogger(__name__)

class AIAssistant:
    """AI Assistant for reading comprehension and analysis."""
    
    def __init__(self):
        self.model = None
        self.api_key = None
        self.initialized = False
        
    async def initialize(self) -> bool:
        """Initialize the AI assistant with Gemini API."""
        if not GEMINI_AVAILABLE:
            logger.error("google-generativeai package not installed. Please install it with: pip install google-generativeai")
            return False
            
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("GEMINI_API_KEY environment variable not set")
            return False
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('models/gemini-2.0-flash-exp')
            self.initialized = True
            logger.info("AI Assistant initialized successfully with Gemini")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AI Assistant: {e}")
            return False
    
    def _get_current_context(self, reader) -> str:
        """Get the current reading context (current sentence and chapter)."""
        try:
            current_chapter = reader.chapters[reader.ui_chapter_idx]
            current_paragraph = current_chapter[reader.ui_paragraph_idx]
            sentences = content_parser.split_into_sentences(current_paragraph)
            current_sentence = sentences[reader.ui_sentence_idx] if reader.ui_sentence_idx < len(sentences) else ""
            
            # Get chapter title if available
            chapter_titles = content_parser.extract_chapter_titles(reader.chapters)
            chapter_title = ""
            for idx, title in chapter_titles:
                if idx == reader.ui_chapter_idx:
                    chapter_title = title
                    break
            
            context = f"Current Chapter: {chapter_title}\n" if chapter_title else ""
            context += f"Current Sentence: \"{current_sentence}\"\n"
            context += f"Current Paragraph: \"{current_paragraph[:200]}{'...' if len(current_paragraph) > 200 else ''}\""
            
            return context
        except (IndexError, AttributeError) as e:
            logger.error(f"Error getting current context: {e}")
            return "Unable to get current reading context"
    
    async def ask_question(self, reader, question: str) -> str:
        """Ask a question about the current reading context."""
        if not self.initialized:
            return "AI assistant not initialized. Please check if GEMINI_API_KEY environment variable is set."
        
        try:
            context = self._get_current_context(reader)
            
            # Construct the prompt
            prompt = f"""You are a professional reading assistant that helps users understand and analyze text content.

Reading Context:
{context}

User Question: {question}

Please answer the user's question based on the provided context. If the question is related to the current text content, provide detailed analysis and explanation. If the question goes beyond the current text scope, please indicate this and try to provide useful information.

Answer Requirements:
1. Be concise and clear, highlighting key points
2. If involving text analysis, quote specific content
3. Provide valuable insights and explanations
4. Answer in English"""

            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error asking question: {e}")
            return f"Sorry, an error occurred while processing your question: {str(e)}"
    
    def get_suggested_questions(self, reader) -> List[str]:
        """Get suggested questions based on current context."""
        return [
            "What does this sentence mean?",
            "What is the main point of this content?",
            "Is there any deeper meaning here?",
            "How does this connect to previous content?",
            "What is the author trying to express?"
        ]

# Global AI assistant instance
ai_assistant = AIAssistant()

async def initialize_ai_assistant() -> bool:
    """Initialize the global AI assistant instance."""
    return await ai_assistant.initialize()

async def ask_ai_question(reader, question: str) -> str:
    """Ask a question to the AI assistant."""
    return await ai_assistant.ask_question(reader, question)

def get_ai_suggestions(reader) -> List[str]:
    """Get suggested questions from the AI assistant."""
    return ai_assistant.get_suggested_questions(reader)
