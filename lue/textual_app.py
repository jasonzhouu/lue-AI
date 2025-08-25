"""
Textual-based application for Lue e-book reader.
This replaces the manual input handling with Textual's robust event system.
"""

import asyncio
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, ProgressBar, Footer
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.reactive import reactive
from textual.message import Message
from textual import on
from rich.text import Text
from rich.console import Console

from . import reader as lue_reader
from .tts.base import TTSBase
from .textual_adapter import create_textual_adapter


class ReaderWidget(Static):
    """Main reader widget that displays book content."""
    
    current_position = reactive((0, 0, 0))  # (chapter, paragraph, sentence)
    
    def __init__(self, lue_instance: lue_reader.Lue):
        super().__init__()
        self.lue = lue_instance
        self.console = Console()
        
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(id="content-display")
        yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        
    def watch_current_position(self, position: tuple) -> None:
        """Update display when position changes."""
        self.update_content_display()
        self.update_progress()
        
    def update_content_display(self) -> None:
        """Update the main content display."""
        content_widget = self.query_one("#content-display", Static)
        
        # Get current content from lue instance
        if hasattr(self.lue, 'get_current_display_content'):
            display_content = self.lue.get_current_display_content()
        else:
            # Fallback to basic content display
            chapter_idx, para_idx, sent_idx = self.current_position
            if (chapter_idx < len(self.lue.chapters) and 
                para_idx < len(self.lue.chapters[chapter_idx])):
                paragraph = self.lue.chapters[chapter_idx][para_idx]
                display_content = Text(paragraph)
            else:
                display_content = Text("No content available")
                
        content_widget.update(display_content)
        
    def update_progress(self) -> None:
        """Update the progress bar."""
        progress_widget = self.query_one("#progress-bar", ProgressBar)
        
        # Calculate progress percentage
        if hasattr(self.lue, 'get_reading_progress'):
            progress = self.lue.get_reading_progress()
        else:
            # Fallback calculation
            chapter_idx, para_idx, sent_idx = self.current_position
            total_paragraphs = sum(len(chapter) for chapter in self.lue.chapters)
            current_paragraph = sum(len(self.lue.chapters[i]) for i in range(chapter_idx)) + para_idx
            progress = (current_paragraph / total_paragraphs * 100) if total_paragraphs > 0 else 0
            
        progress_widget.update(progress=progress)


class TOCModal(ModalScreen):
    """Table of Contents modal screen."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("c", "dismiss", "Close"),
        Binding("q", "quit", "Quit"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("enter", "select_chapter", "Select"),
    ]
    
    def __init__(self, lue_instance: lue_reader.Lue):
        super().__init__()
        self.lue = lue_instance
        self.selected_chapter = 0
        
    def compose(self) -> ComposeResult:
        """Create the TOC interface."""
        with Container(id="toc-container"):
            yield Static("📚 Table of Contents", id="toc-title")
            yield Static(id="toc-content")
            
    def on_mount(self) -> None:
        """Initialize TOC content when mounted."""
        self.update_toc_display()
        
    def update_toc_display(self) -> None:
        """Update the TOC content display."""
        toc_widget = self.query_one("#toc-content", Static)
        
        # Get chapter titles from lue instance
        if hasattr(self.lue, 'get_chapter_titles'):
            chapter_titles = self.lue.get_chapter_titles()
        else:
            # Fallback: generate basic chapter titles
            chapter_titles = [f"Chapter {i+1}" for i in range(len(self.lue.chapters))]
            
        # Build TOC display with selection indicators
        toc_lines = []
        current_chapter = getattr(self.lue, 'chapter_idx', 0)
        
        for i, title in enumerate(chapter_titles):
            prefix = "●" if i == current_chapter else " "
            prefix += "▶" if i == self.selected_chapter else " "
            toc_lines.append(f"{prefix} {title}")
            
        toc_content = Text("\n".join(toc_lines))
        toc_widget.update(toc_content)
        
    def action_cursor_up(self) -> None:
        """Move selection up."""
        if self.selected_chapter > 0:
            self.selected_chapter -= 1
            self.update_toc_display()
            
    def action_cursor_down(self) -> None:
        """Move selection down."""
        max_chapters = len(self.lue.chapters) - 1
        if self.selected_chapter < max_chapters:
            self.selected_chapter += 1
            self.update_toc_display()
            
    def action_select_chapter(self) -> None:
        """Jump to selected chapter."""
        # Jump to selected chapter in lue instance
        if hasattr(self.lue, 'jump_to_chapter'):
            self.lue.jump_to_chapter(self.selected_chapter)
        else:
            # Fallback: set position manually
            self.lue.chapter_idx = self.selected_chapter
            self.lue.paragraph_idx = 0
            self.lue.sentence_idx = 0
            
        self.dismiss()
        
    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class AIAssistantModal(ModalScreen):
    """AI Assistant modal screen."""
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("ctrl+u", "clear_input", "Clear"),
        Binding("enter", "send_message", "Send"),
    ]
    
    def __init__(self, lue_instance: lue_reader.Lue):
        super().__init__()
        self.lue = lue_instance
        self.input_buffer = ""
        self.conversation_history = []
        
    def compose(self) -> ComposeResult:
        """Create the AI Assistant interface."""
        with Container(id="ai-container"):
            yield Static("🤖 AI Assistant", id="ai-title")
            yield Static(id="ai-context")
            yield Static(id="ai-conversation")
            yield Static(id="ai-input-display")
            
    def on_mount(self) -> None:
        """Initialize AI Assistant when mounted."""
        self.update_context_display()
        self.update_conversation_display()
        self.update_input_display()
        
    def update_context_display(self) -> None:
        """Update the current sentence context."""
        context_widget = self.query_one("#ai-context", Static)
        
        # Get current sentence from lue instance
        if hasattr(self.lue, 'get_current_sentence'):
            current_sentence = self.lue.get_current_sentence()
        else:
            current_sentence = "No sentence available"
            
        context_content = Text(f"Current: {current_sentence}")
        context_widget.update(context_content)
        
    def update_conversation_display(self) -> None:
        """Update the conversation history."""
        conv_widget = self.query_one("#ai-conversation", Static)
        
        if self.conversation_history:
            conv_lines = []
            for entry in self.conversation_history[-5:]:  # Show last 5 exchanges
                conv_lines.append(f"Q: {entry['question']}")
                conv_lines.append(f"A: {entry['answer']}")
                conv_lines.append("")
            conv_content = Text("\n".join(conv_lines))
        else:
            conv_content = Text("Ask a question about the current text...")
            
        conv_widget.update(conv_content)
        
    def update_input_display(self) -> None:
        """Update the input buffer display."""
        input_widget = self.query_one("#ai-input-display", Static)
        input_content = Text(f"❯ {self.input_buffer}█")
        input_widget.update(input_content)
        
    def on_key(self, event) -> None:
        """Handle key input for the AI assistant."""
        if event.key == "backspace":
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                self.update_input_display()
        elif event.character and event.character.isprintable():
            self.input_buffer += event.character
            self.update_input_display()
            
    def action_clear_input(self) -> None:
        """Clear the input buffer."""
        self.input_buffer = ""
        self.update_input_display()
        
    async def action_send_message(self) -> None:
        """Send message to AI assistant."""
        if not self.input_buffer.strip():
            return
            
        question = self.input_buffer.strip()
        self.input_buffer = ""
        self.update_input_display()
        
        # Get AI response from lue instance
        if hasattr(self.lue, 'get_ai_response'):
            answer = await self.lue.get_ai_response(question)
        else:
            answer = "AI Assistant not configured"
            
        # Add to conversation history
        self.conversation_history.append({
            'question': question,
            'answer': answer
        })
        
        self.update_conversation_display()


class LueApp(App):
    """Main Textual application for Lue e-book reader."""
    
    CSS = """
    #content-display {
        height: 1fr;
        padding: 1;
        border: solid $primary;
    }
    
    #progress-bar {
        height: 1;
        margin: 1 0;
    }
    
    #toc-container, #ai-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    #toc-title, #ai-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    """
    
    BINDINGS = [
        # Navigation
        Binding("h", "prev_paragraph", "Previous Paragraph"),
        Binding("l", "next_paragraph", "Next Paragraph"),
        Binding("j", "prev_sentence", "Previous Sentence"),
        Binding("k", "next_sentence", "Next Sentence"),
        Binding("left", "prev_sentence", "Previous Sentence"),
        Binding("right", "next_sentence", "Next Sentence"),
        Binding("up", "prev_paragraph", "Previous Paragraph"),
        Binding("down", "next_paragraph", "Next Paragraph"),
        
        # Scrolling
        Binding("i", "scroll_page_up", "Page Up"),
        Binding("m", "scroll_page_down", "Page Down"),
        Binding("u", "scroll_up", "Scroll Up"),
        Binding("n", "scroll_down", "Scroll Down"),
        
        # Jumping
        Binding("y", "move_to_beginning", "Beginning"),
        Binding("b", "move_to_end", "End"),
        Binding("t", "move_to_top_visible", "Top Visible"),
        
        # Controls
        Binding("p", "pause", "Pause/Resume"),
        Binding("a", "toggle_auto_scroll", "Auto Scroll"),
        
        # Overlays
        Binding("c", "show_toc", "Table of Contents"),
        Binding("question_mark", "show_ai_assistant", "AI Assistant"),
        
        # System
        Binding("q", "quit", "Quit"),
    ]
    
    def __init__(self, file_path: str, tts_model: Optional[TTSBase] = None, overlap: Optional[float] = None):
        super().__init__()
        self.lue = lue_reader.Lue(file_path, tts_model, overlap)
        # Add Textual adapter methods to the lue instance
        create_textual_adapter(self.lue)
        
    def compose(self) -> ComposeResult:
        """Create the main application layout."""
        yield ReaderWidget(self.lue)
        yield Footer()
        
    def on_mount(self) -> None:
        """Initialize the application."""
        reader_widget = self.query_one(ReaderWidget)
        reader_widget.current_position = (
            getattr(self.lue, 'chapter_idx', 0),
            getattr(self.lue, 'paragraph_idx', 0),
            getattr(self.lue, 'sentence_idx', 0)
        )
        
    # Navigation actions
    def action_prev_paragraph(self) -> None:
        """Move to previous paragraph."""
        if hasattr(self.lue, 'move_to_prev_paragraph'):
            self.lue.move_to_prev_paragraph()
            self._update_position()
            
    def action_next_paragraph(self) -> None:
        """Move to next paragraph."""
        if hasattr(self.lue, 'move_to_next_paragraph'):
            self.lue.move_to_next_paragraph()
            self._update_position()
            
    def action_prev_sentence(self) -> None:
        """Move to previous sentence."""
        if hasattr(self.lue, 'move_to_prev_sentence'):
            self.lue.move_to_prev_sentence()
            self._update_position()
            
    def action_next_sentence(self) -> None:
        """Move to next sentence."""
        if hasattr(self.lue, 'move_to_next_sentence'):
            self.lue.move_to_next_sentence()
            self._update_position()
            
    # Scrolling actions
    def action_scroll_page_up(self) -> None:
        """Scroll page up."""
        if hasattr(self.lue, 'scroll_page_up'):
            self.lue.scroll_page_up()
            self._update_position()
            
    def action_scroll_page_down(self) -> None:
        """Scroll page down."""
        if hasattr(self.lue, 'scroll_page_down'):
            self.lue.scroll_page_down()
            self._update_position()
            
    def action_scroll_up(self) -> None:
        """Scroll up."""
        if hasattr(self.lue, 'scroll_up'):
            self.lue.scroll_up()
            self._update_position()
            
    def action_scroll_down(self) -> None:
        """Scroll down."""
        if hasattr(self.lue, 'scroll_down'):
            self.lue.scroll_down()
            self._update_position()
            
    # Jumping actions
    def action_move_to_beginning(self) -> None:
        """Move to beginning of book."""
        if hasattr(self.lue, 'move_to_beginning'):
            self.lue.move_to_beginning()
            self._update_position()
            
    def action_move_to_end(self) -> None:
        """Move to end of book."""
        if hasattr(self.lue, 'move_to_end'):
            self.lue.move_to_end()
            self._update_position()
            
    def action_move_to_top_visible(self) -> None:
        """Move to top visible line."""
        if hasattr(self.lue, 'move_to_top_visible'):
            self.lue.move_to_top_visible()
            self._update_position()
            
    # Control actions
    def action_pause(self) -> None:
        """Pause/resume TTS."""
        if hasattr(self.lue, 'toggle_pause'):
            self.lue.toggle_pause()
            
    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto scroll."""
        if hasattr(self.lue, 'toggle_auto_scroll'):
            self.lue.toggle_auto_scroll()
            
    # Modal actions
    def action_show_toc(self) -> None:
        """Show table of contents."""
        self.push_screen(TOCModal(self.lue))
        
    def action_show_ai_assistant(self) -> None:
        """Show AI assistant."""
        self.push_screen(AIAssistantModal(self.lue))
        
    def _update_position(self) -> None:
        """Update the reader widget position."""
        reader_widget = self.query_one(ReaderWidget)
        reader_widget.current_position = (
            getattr(self.lue, 'chapter_idx', 0),
            getattr(self.lue, 'paragraph_idx', 0),
            getattr(self.lue, 'sentence_idx', 0)
        )


def run_textual_app(file_path: str, tts_model: Optional[TTSBase] = None, overlap: Optional[float] = None):
    """Run the Textual-based Lue application."""
    app = LueApp(file_path, tts_model, overlap)
    app.run()
