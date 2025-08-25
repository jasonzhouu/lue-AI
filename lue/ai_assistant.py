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
            
            context = f"当前章节: {chapter_title}\n" if chapter_title else ""
            context += f"当前句子: \"{current_sentence}\"\n"
            context += f"当前段落: \"{current_paragraph[:200]}{'...' if len(current_paragraph) > 200 else ''}\""
            
            return context
        except (IndexError, AttributeError) as e:
            logger.error(f"Error getting current context: {e}")
            return "无法获取当前阅读上下文"
    
    async def ask_question(self, reader, question: str) -> str:
        """Ask a question about the current reading context."""
        if not self.initialized:
            return "AI助手未初始化。请检查GEMINI_API_KEY环境变量是否设置。"
        
        try:
            context = self._get_current_context(reader)
            
            # Construct the prompt
            prompt = f"""你是一个专业的阅读助手，帮助用户理解和分析文本内容。

阅读上下文：
{context}

用户问题：{question}

请基于提供的上下文回答用户的问题。如果问题与当前文本内容相关，请提供详细的分析和解释。如果问题超出了当前文本范围，请说明这一点并尽力提供有用的信息。

回答要求：
1. 简洁明了，重点突出
2. 如果涉及文本分析，请引用具体内容
3. 提供有价值的见解和解释
4. 使用中文回答"""

            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error asking question: {e}")
            return f"抱歉，处理您的问题时出现错误：{str(e)}"
    
    def get_suggested_questions(self, reader) -> List[str]:
        """Get suggested questions based on current context."""
        return [
            "这句话是什么意思？",
            "这段内容的主要观点是什么？",
            "这里有什么深层含义吗？",
            "这与前面的内容有什么联系？",
            "作者想表达什么？"
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
