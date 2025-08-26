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
from textual.events import Click
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
        with Vertical():
            yield Static(id="content-display")
            with Horizontal():
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                yield Static(id="tts-status")
        
    def on_mount(self) -> None:
        """Initialize widget when mounted."""
        self.update_content_display()
        self.update_progress()
        self.update_tts_status()
        
    def watch_current_position(self, position: tuple) -> None:
        """Update display when position changes."""
        self.update_content_display()
        self.update_progress()
        self.update_tts_status()
        
    def update_content_display(self) -> None:
        """Update the main content display with proper sentence highlighting."""
        try:
            content_widget = self.query_one("#content-display", Static)
            
            # Update UI position to match current position
            self.lue.ui_chapter_idx = self.lue.chapter_idx
            self.lue.ui_paragraph_idx = self.lue.paragraph_idx
            self.lue.ui_sentence_idx = self.lue.sentence_idx
            
            # Get terminal height for proper content sizing
            from .ui import get_terminal_size, get_visible_content
            _, height = get_terminal_size()
            
            # Ensure document layout is updated
            if not hasattr(self.lue, 'document_lines') or not self.lue.document_lines:
                from .ui import update_document_layout
                update_document_layout(self.lue)
            
            # Use the original UI's get_visible_content which handles highlighting
            visible_lines = get_visible_content(self.lue)
            
            # Convert visible lines to a single Text object with proper formatting
            display_content = Text()
            for i, line in enumerate(visible_lines):
                if i > 0:
                    display_content.append("\n")
                # Ensure line is a Text object, not a string
                if isinstance(line, str):
                    display_content.append(Text(line))
                else:
                    display_content.append(line)
                    
            content_widget.update(display_content)
        except Exception as e:
            # Graceful error handling
            content_widget = self.query_one("#content-display", Static)
            content_widget.update(Text(f"Error updating display: {str(e)}", style="red"))
        
    def _get_fallback_content(self) -> Text:
        """Fallback content display method."""
        chapter_idx, para_idx, sent_idx = self.current_position
        if (chapter_idx < len(self.lue.chapters) and 
            para_idx < len(self.lue.chapters[chapter_idx])):
            paragraph = self.lue.chapters[chapter_idx][para_idx]
            return Text(paragraph, style="white")
        else:
            return Text("No content available", style="dim")
        
    def update_progress(self) -> None:
        """Update the progress bar."""
        try:
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
        except Exception:
            # Graceful error handling for progress bar
            pass
            
    def update_tts_status(self) -> None:
        """Update TTS status display."""
        try:
            tts_widget = self.query_one("#tts-status", Static)
            
            # Get TTS status
            is_paused = getattr(self.lue, 'is_paused', True)
            has_tts = getattr(self.lue, 'tts_model', None) is not None
            auto_scroll = getattr(self.lue, 'auto_scroll_enabled', False)
            
            status_parts = []
            if has_tts:
                if is_paused:
                    status_parts.append("⏸️ Paused")
                else:
                    status_parts.append("▶️ Playing")
            else:
                status_parts.append("🔇 No TTS")
                
            if auto_scroll:
                status_parts.append("📜 Auto")
                
            status_text = " | ".join(status_parts)
            tts_widget.update(Text(status_text, style="dim"))
        except Exception:
            pass
            
    def refresh_display(self) -> None:
        """Force refresh of the display."""
        self.current_position = (
            getattr(self.lue, 'chapter_idx', 0),
            getattr(self.lue, 'paragraph_idx', 0),
            getattr(self.lue, 'sentence_idx', 0)
        )
        self.update_tts_status()
        
    def on_click(self, event: Click) -> None:
        """Handle mouse click events to change highlighted sentence."""
        try:
            # Get the content display widget
            content_widget = self.query_one("#content-display", Static)
            
            # Get click coordinates relative to the content widget
            click_x = event.x
            click_y = event.y
            
            # Find which sentence was clicked based on coordinates
            new_position = self._find_sentence_at_position(click_x, click_y)
            if new_position:
                chapter_idx, paragraph_idx, sentence_idx = new_position
                
                # Update the lue instance position
                self.lue.chapter_idx = chapter_idx
                self.lue.paragraph_idx = paragraph_idx
                self.lue.sentence_idx = sentence_idx
                
                # Update UI position
                self.lue.ui_chapter_idx = chapter_idx
                self.lue.ui_paragraph_idx = paragraph_idx
                self.lue.ui_sentence_idx = sentence_idx
                
                # Update the display
                self.current_position = (chapter_idx, paragraph_idx, sentence_idx)
                
                # Pause TTS to prevent reading during navigation
                if hasattr(self.lue, 'is_paused'):
                    self.lue.is_paused = True
                    
        except Exception as e:
            # Graceful error handling
            pass
            
    def _find_sentence_at_position(self, click_x: int, click_y: int) -> tuple[int, int, int] | None:
        """Find which sentence is at the given click position."""
        try:
            # Get terminal dimensions and visible content area
            from .ui import get_terminal_size, get_visible_content
            width, height = get_terminal_size()
            
            # Account for panel padding and borders
            content_start_y = 2  # Panel title and top border
            content_start_x = 5  # Left padding
            
            # Adjust click coordinates to content area
            content_y = click_y - content_start_y
            content_x = click_x - content_start_x
            
            # Ensure we have document layout
            if not hasattr(self.lue, 'document_lines') or not self.lue.document_lines:
                from .ui import update_document_layout
                update_document_layout(self.lue)
            
            # Get the visible content and find which line was clicked
            visible_lines = get_visible_content(self.lue)
            
            if content_y < 0 or content_y >= len(visible_lines):
                return None
                
            # Calculate which document line was clicked
            start_line = int(self.lue.scroll_offset)
            clicked_document_line = start_line + content_y
            
            # Find the position that corresponds to this line
            if clicked_document_line in self.lue.line_to_position:
                base_position = self.lue.line_to_position[clicked_document_line]
                chapter_idx, paragraph_idx, _ = base_position
                
                # Now we need to find which sentence within this paragraph
                # was clicked based on the character position
                sentence_idx = self._find_sentence_in_paragraph(
                    chapter_idx, paragraph_idx, clicked_document_line, content_x
                )
                
                return (chapter_idx, paragraph_idx, sentence_idx)
                
            return None
            
        except Exception:
            return None
            
    def _find_sentence_in_paragraph(self, chapter_idx: int, paragraph_idx: int, 
                                   line_idx: int, char_pos: int) -> int:
        """Find which sentence in a paragraph corresponds to the click position."""
        try:
            from . import content_parser
            from .ui import get_terminal_size
            
            # Get the paragraph text
            if (chapter_idx >= len(self.lue.chapters) or 
                paragraph_idx >= len(self.lue.chapters[chapter_idx])):
                return 0
                
            paragraph = self.lue.chapters[chapter_idx][paragraph_idx]
            sentences = content_parser.split_into_sentences(paragraph)
            
            if not sentences:
                return 0
            
            # Get terminal width for text wrapping calculations
            width, _ = get_terminal_size()
            available_width = max(20, width - 10)
            
            # Calculate the absolute character position within the paragraph
            # by reconstructing the wrapped text layout
            absolute_char_pos = self._calculate_absolute_char_position(
                chapter_idx, paragraph_idx, line_idx, char_pos, available_width
            )
            
            # Find which sentence contains this character position
            current_pos = 0
            for sent_idx, sentence in enumerate(sentences):
                sentence_start = current_pos
                sentence_end = current_pos + len(sentence)
                
                # Check if the click position falls within this sentence
                if sentence_start <= absolute_char_pos < sentence_end:
                    return sent_idx
                
                # Move to next sentence (account for space between sentences)
                current_pos = sentence_end
                if sent_idx < len(sentences) - 1:
                    current_pos += 1  # Space between sentences
            
            # If we didn't find a match, return the last sentence
            return len(sentences) - 1
            
        except Exception:
            return 0
            
    def _calculate_absolute_char_position(self, chapter_idx: int, paragraph_idx: int,
                                        line_idx: int, char_pos: int, available_width: int) -> int:
        """Calculate the absolute character position within a paragraph from click coordinates."""
        try:
            # Get paragraph text and wrap it to see how it's displayed
            paragraph = self.lue.chapters[chapter_idx][paragraph_idx]
            
            # Process verse markers like the UI does
            from .ui import _process_verse_markers
            styled_text = _process_verse_markers(paragraph)
            wrapped_lines = styled_text.wrap(self.lue.console, available_width)
            
            # Get paragraph line range
            paragraph_key = (chapter_idx, paragraph_idx)
            if (hasattr(self.lue, 'paragraph_line_ranges') and 
                paragraph_key in self.lue.paragraph_line_ranges):
                
                para_start, para_end = self.lue.paragraph_line_ranges[paragraph_key]
                line_offset = line_idx - para_start
                
                # Ensure line_offset is within bounds
                if line_offset < 0 or line_offset >= len(wrapped_lines):
                    return 0
                
                # Calculate character position by summing up characters in previous lines
                # plus the character position within the current line
                total_chars = 0
                
                # Add characters from all previous lines in this paragraph
                for i in range(line_offset):
                    if i < len(wrapped_lines):
                        total_chars += len(wrapped_lines[i].plain)
                        # Account for line breaks (except for the last line)
                        if i < len(wrapped_lines) - 1:
                            total_chars += 1
                
                # Add the character position within the current line
                if line_offset < len(wrapped_lines):
                    current_line = wrapped_lines[line_offset]
                    # Clamp char_pos to the actual line length
                    line_char_pos = min(char_pos, len(current_line.plain))
                    total_chars += max(0, line_char_pos)
                
                return total_chars
            
            # Fallback: simple estimation
            return min(char_pos, len(paragraph))
            
        except Exception:
            return 0


class TOCModal(ModalScreen):
    """Table of Contents modal screen with scrolling support."""
    
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
        # Initialize selected chapter to current chapter
        self.selected_chapter = getattr(lue_instance, 'chapter_idx', 0)
        # Scrolling support
        self.toc_scroll_offset = 0
        self.visible_height = 15  # Number of chapters visible at once
        
    def compose(self) -> ComposeResult:
        """Create the TOC interface."""
        with Container(id="toc-container"):
            yield Static("📚 Table of Contents", id="toc-title")
            yield Static(id="toc-content")
            
    def on_mount(self) -> None:
        """Initialize TOC content when mounted."""
        self.update_toc_display()
        
    def update_toc_display(self) -> None:
        """Update the TOC content display with scrolling support."""
        try:
            toc_widget = self.query_one("#toc-content", Static)
            
            # Get chapter titles from lue instance
            if hasattr(self.lue, 'get_chapter_titles'):
                chapter_titles = self.lue.get_chapter_titles()
            else:
                # Fallback: generate basic chapter titles
                chapter_titles = [f"Chapter {i+1}" for i in range(len(self.lue.chapters))]
            
            # Adjust scroll offset to keep selected chapter visible
            total_chapters = len(chapter_titles)
            if self.selected_chapter < self.toc_scroll_offset:
                self.toc_scroll_offset = self.selected_chapter
            elif self.selected_chapter >= self.toc_scroll_offset + self.visible_height:
                self.toc_scroll_offset = self.selected_chapter - self.visible_height + 1
            
            # Ensure scroll offset is within bounds
            self.toc_scroll_offset = max(0, min(self.toc_scroll_offset, total_chapters - self.visible_height))
            
            # Calculate visible range
            start_idx = self.toc_scroll_offset
            end_idx = min(start_idx + self.visible_height, total_chapters)
            
            # Build TOC display with selection indicators
            toc_lines = []
            current_chapter = getattr(self.lue, 'chapter_idx', 0)
            
            # Add scroll indicator at top if needed
            if self.toc_scroll_offset > 0:
                toc_lines.append((f"↑ ... ({self.toc_scroll_offset} more above)", "dim"))
            
            for i in range(start_idx, end_idx):
                title = chapter_titles[i]
                # Current chapter indicator
                current_indicator = "●" if i == current_chapter else " "
                # Selection indicator
                selection_indicator = "▶" if i == self.selected_chapter else " "
                
                # Style based on selection
                if i == self.selected_chapter:
                    style = "bold yellow on blue"
                elif i == current_chapter:
                    style = "bold green"
                else:
                    style = "white"
                
                line_text = f"{current_indicator}{selection_indicator} {title}"
                toc_lines.append((line_text, style))
            
            # Add scroll indicator at bottom if needed
            if end_idx < total_chapters:
                remaining = total_chapters - end_idx
                toc_lines.append((f"↓ ... ({remaining} more below)", "dim"))
            
            # Build the final display text
            toc_display = Text()
            for i, (line_text, style) in enumerate(toc_lines):
                if i > 0:
                    toc_display.append("\n")
                toc_display.append(line_text, style=style)
                
            toc_widget.update(toc_display)
        except Exception as e:
            toc_widget = self.query_one("#toc-content", Static)
            toc_widget.update(Text(f"Error updating TOC: {str(e)}", style="red"))
        
    def action_cursor_up(self) -> None:
        """Move selection up with scrolling support."""
        if self.selected_chapter > 0:
            self.selected_chapter -= 1
            self.update_toc_display()
            
    def action_cursor_down(self) -> None:
        """Move selection down with scrolling support."""
        # Get actual chapter count from titles
        if hasattr(self.lue, 'get_chapter_titles'):
            chapter_titles = self.lue.get_chapter_titles()
            max_chapters = len(chapter_titles) - 1
        else:
            max_chapters = len(self.lue.chapters) - 1
            
        if self.selected_chapter < max_chapters:
            self.selected_chapter += 1
            self.update_toc_display()
            
    def action_select_chapter(self) -> None:
        """Jump to selected chapter."""
        try:
            # Jump to selected chapter in lue instance
            if hasattr(self.lue, 'jump_to_chapter'):
                self.lue.jump_to_chapter(self.selected_chapter)
            else:
                # Fallback: set position manually
                self.lue.chapter_idx = self.selected_chapter
                self.lue.paragraph_idx = 0
                self.lue.sentence_idx = 0
                
                # Update UI state if available
                if hasattr(self.lue, 'ui_chapter_idx'):
                    self.lue.ui_chapter_idx = self.selected_chapter
                    self.lue.ui_paragraph_idx = 0
                    self.lue.ui_sentence_idx = 0
                    
            self.dismiss()
        except Exception:
            self.dismiss()
        
    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class AIAssistantModal(ModalScreen):
    """AI Assistant modal screen with proper input handling."""
    
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
        self.current_context = ""
        self.waiting_for_response = False
        
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
        try:
            context_widget = self.query_one("#ai-context", Static)
            
            # Get current sentence from lue instance
            if hasattr(self.lue, 'get_current_sentence'):
                current_sentence = self.lue.get_current_sentence()
            else:
                current_sentence = "No sentence available"
                
            self.current_context = current_sentence
            context_content = Text(f"Current: {current_sentence[:100]}...", style="cyan")
            context_widget.update(context_content)
        except Exception:
            pass
        
    def update_conversation_display(self) -> None:
        """Update the conversation history."""
        try:
            conv_widget = self.query_one("#ai-conversation", Static)
            
            if self.conversation_history:
                conv_display = Text()
                for i, entry in enumerate(self.conversation_history[-3:]):  # Show last 3 exchanges
                    if i > 0:
                        conv_display.append("\n")
                    conv_display.append(f"Q: {entry['question']}", style="yellow")
                    conv_display.append("\n")
                    conv_display.append(f"A: {entry['answer'][:200]}...", style="green")
                    conv_display.append("\n")
            else:
                conv_display = Text("Ask a question about the current text...", style="dim")
                
            conv_widget.update(conv_display)
        except Exception:
            pass
        
    def update_input_display(self) -> None:
        """Update the input buffer display."""
        try:
            input_widget = self.query_one("#ai-input-display", Static)
            
            if self.waiting_for_response:
                input_content = Text("❯ Waiting for AI response...", style="yellow")
            else:
                cursor = "█" if len(self.input_buffer) % 2 == 0 else " "  # Blinking cursor effect
                input_content = Text(f"❯ {self.input_buffer}{cursor}", style="white")
                
            input_widget.update(input_content)
        except Exception:
            pass
        
    def on_key(self, event) -> None:
        """Handle key input for the AI assistant."""
        if self.waiting_for_response:
            return  # Ignore input while waiting for response
            
        if event.key == "backspace":
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                self.update_input_display()
        elif event.character and event.character.isprintable():
            self.input_buffer += event.character
            self.update_input_display()
            
    def action_clear_input(self) -> None:
        """Clear the input buffer."""
        if not self.waiting_for_response:
            self.input_buffer = ""
            self.update_input_display()
        
    async def action_send_message(self) -> None:
        """Send message to AI assistant."""
        if not self.input_buffer.strip() or self.waiting_for_response:
            return
            
        question = self.input_buffer.strip()
        self.input_buffer = ""
        self.waiting_for_response = True
        self.update_input_display()
        
        try:
            # Get AI response from lue instance
            if hasattr(self.lue, 'get_ai_response'):
                answer = await self.lue.get_ai_response(question)
            else:
                answer = "AI Assistant not configured. Please set up Gemini API key."
                
            # Add to conversation history
            self.conversation_history.append({
                'question': question,
                'answer': answer,
                'context': self.current_context
            })
            
        except Exception as e:
            self.conversation_history.append({
                'question': question,
                'answer': f"Error: {str(e)}",
                'context': self.current_context
            })
        finally:
            self.waiting_for_response = False
            self.update_conversation_display()
            self.update_input_display()


class LueApp(App):
    """Main Textual application for Lue e-book reader."""
    
    CSS = """
    #content-display {
        height: 1fr;
        padding: 1;
        border: solid $primary;
    }
    
    #progress-bar {
        width: 3fr;
        height: 1;
    }
    
    #tts-status {
        width: 1fr;
        height: 1;
        text-align: right;
        padding: 0 1;
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
    
    Horizontal {
        height: auto;
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
        self._tts_initialized = False
        self._ai_initialized = False
        
    def compose(self) -> ComposeResult:
        """Create the main application layout."""
        yield ReaderWidget(self.lue)
        yield Footer()
        
    async def on_mount(self) -> None:
        """Initialize the application."""
        reader_widget = self.query_one(ReaderWidget)
        reader_widget.current_position = (
            getattr(self.lue, 'chapter_idx', 0),
            getattr(self.lue, 'paragraph_idx', 0),
            getattr(self.lue, 'sentence_idx', 0)
        )
        
        # Initialize TTS and AI in background
        asyncio.create_task(self._initialize_services())
        
    # Navigation actions
    def action_prev_paragraph(self) -> None:
        """Move to previous paragraph."""
        try:
            if hasattr(self.lue, 'move_to_prev_paragraph'):
                self.lue.move_to_prev_paragraph()
            else:
                # Direct navigation fallback
                if self.lue.paragraph_idx > 0:
                    self.lue.paragraph_idx -= 1
                    self.lue.sentence_idx = 0
                elif self.lue.chapter_idx > 0:
                    self.lue.chapter_idx -= 1
                    self.lue.paragraph_idx = len(self.lue.chapters[self.lue.chapter_idx]) - 1
                    self.lue.sentence_idx = 0
            self._update_position()
        except Exception:
            pass
            
    def action_next_paragraph(self) -> None:
        """Move to next paragraph."""
        try:
            if hasattr(self.lue, 'move_to_next_paragraph'):
                self.lue.move_to_next_paragraph()
            else:
                # Direct navigation fallback
                current_chapter = self.lue.chapters[self.lue.chapter_idx]
                if self.lue.paragraph_idx < len(current_chapter) - 1:
                    self.lue.paragraph_idx += 1
                    self.lue.sentence_idx = 0
                elif self.lue.chapter_idx < len(self.lue.chapters) - 1:
                    self.lue.chapter_idx += 1
                    self.lue.paragraph_idx = 0
                    self.lue.sentence_idx = 0
            self._update_position()
        except Exception:
            pass
            
    def action_prev_sentence(self) -> None:
        """Move to previous sentence."""
        try:
            if hasattr(self.lue, 'move_to_prev_sentence'):
                self.lue.move_to_prev_sentence()
            else:
                # Direct navigation fallback
                from . import content_parser
                if self.lue.sentence_idx > 0:
                    self.lue.sentence_idx -= 1
                else:
                    # Move to previous paragraph
                    self.action_prev_paragraph()
                    # Set to last sentence of new paragraph
                    current_para = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                    sentences = content_parser.split_into_sentences(current_para)
                    self.lue.sentence_idx = max(0, len(sentences) - 1)
            self._update_position()
        except Exception:
            pass
            
    def action_next_sentence(self) -> None:
        """Move to next sentence."""
        try:
            if hasattr(self.lue, 'move_to_next_sentence'):
                self.lue.move_to_next_sentence()
            else:
                # Direct navigation fallback
                from . import content_parser
                current_para = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                sentences = content_parser.split_into_sentences(current_para)
                if self.lue.sentence_idx < len(sentences) - 1:
                    self.lue.sentence_idx += 1
                else:
                    # Move to next paragraph
                    self.action_next_paragraph()
            self._update_position()
        except Exception:
            pass
            
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
        try:
            if hasattr(self.lue, 'toggle_pause'):
                self.lue.toggle_pause()
            else:
                # Direct toggle fallback
                self.lue.is_paused = not getattr(self.lue, 'is_paused', True)
            
            # Handle audio playback based on pause state
            if self._tts_initialized:
                asyncio.create_task(self._handle_audio_state_change())
            
            self._update_tts_status()
        except Exception:
            pass
            
    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto scroll."""
        try:
            if hasattr(self.lue, 'toggle_auto_scroll'):
                self.lue.toggle_auto_scroll()
            else:
                # Direct toggle fallback
                self.lue.auto_scroll_enabled = not getattr(self.lue, 'auto_scroll_enabled', False)
            self._update_tts_status()
        except Exception:
            pass
            
    # Modal actions
    def action_show_toc(self) -> None:
        """Show table of contents."""
        def handle_toc_result(result):
            """Handle TOC modal result and update display."""
            self._update_position()
            
        self.push_screen(TOCModal(self.lue), handle_toc_result)
        
    def action_show_ai_assistant(self) -> None:
        """Show AI assistant."""
        def handle_ai_result(result):
            """Handle AI Assistant modal result."""
            # Update context when returning from AI assistant
            pass
            
        self.push_screen(AIAssistantModal(self.lue), handle_ai_result)
        
    def _update_position(self) -> None:
        """Update the reader widget position and restart audio if needed."""
        try:
            reader_widget = self.query_one(ReaderWidget)
            reader_widget.current_position = (
                getattr(self.lue, 'chapter_idx', 0),
                getattr(self.lue, 'paragraph_idx', 0),
                getattr(self.lue, 'sentence_idx', 0)
            )
            # Also update UI state if available
            if hasattr(self.lue, 'ui_chapter_idx'):
                self.lue.ui_chapter_idx = self.lue.chapter_idx
                self.lue.ui_paragraph_idx = self.lue.paragraph_idx
                self.lue.ui_sentence_idx = self.lue.sentence_idx
            
            # Restart audio after navigation if TTS is active
            if self._tts_initialized:
                asyncio.create_task(self._handle_navigation_audio_restart())
        except Exception:
            pass
            
    def _update_tts_status(self) -> None:
        """Update TTS status in reader widget."""
        try:
            reader_widget = self.query_one(ReaderWidget)
            reader_widget.update_tts_status()
        except Exception:
            pass


    async def _initialize_services(self) -> None:
        """Initialize TTS and AI services in background."""
        try:
            # Set up the event loop for the lue instance
            self.lue.loop = asyncio.get_event_loop()
            
            # Initialize document layout
            from .ui import update_document_layout
            update_document_layout(self.lue)
            
            # Initialize TTS
            if not self._tts_initialized:
                self._tts_initialized = await self.lue.initialize_tts()
                
            # Initialize AI Assistant
            if not self._ai_initialized:
                self._ai_initialized = await self.lue.initialize_ai_assistant()
            
            # Set up TTS highlight update callback
            if self._tts_initialized:
                self._setup_tts_highlight_callback()
                
            # Start audio playback if TTS is available and not paused
            if self._tts_initialized and not self.lue.is_paused:
                from . import audio
                await audio.play_from_current_position(self.lue)
                
            # Update TTS status after initialization
            self._update_tts_status()
        except Exception as e:
            # Log error but don't crash the app
            pass


    async def _handle_audio_state_change(self) -> None:
        """Handle audio playback when pause state changes."""
        try:
            from . import audio
            
            if self.lue.is_paused:
                # Stop audio when paused
                await audio.stop_and_clear_audio(self.lue)
            else:
                # Start audio when resumed
                if self._tts_initialized and self.lue.tts_model:
                    await audio.play_from_current_position(self.lue)
        except Exception:
            pass
    
    async def _handle_navigation_audio_restart(self) -> None:
        """Restart audio after navigation if not paused."""
        try:
            if self._tts_initialized and not self.lue.is_paused and self.lue.tts_model:
                from . import audio
                await audio.stop_and_clear_audio(self.lue)
                await asyncio.sleep(0.1)  # Small delay for cleanup
                await audio.play_from_current_position(self.lue)
        except Exception:
            pass
    
    def _setup_tts_highlight_callback(self) -> None:
        """Set up callback to update Textual display when TTS advances."""
        try:
            # Store original _post_command_sync method
            original_post_command_sync = getattr(self.lue, '_post_command_sync', None)
            
            def enhanced_post_command_sync(cmd):
                # Call original method first
                if original_post_command_sync:
                    original_post_command_sync(cmd)
                
                # Handle TTS highlight updates for Textual
                if isinstance(cmd, tuple) and len(cmd) == 2:
                    command_name, data = cmd
                    if command_name == '_update_highlight':
                        # Update position and trigger Textual reactive update
                        if not self.lue.is_paused:
                            self.lue.chapter_idx, self.lue.paragraph_idx, self.lue.sentence_idx = data
                            # Trigger Textual reactive update
                            try:
                                reader_widget = self.query_one(ReaderWidget)
                                reader_widget.current_position = data
                            except Exception:
                                pass
            
            # Replace the method
            self.lue._post_command_sync = enhanced_post_command_sync
        except Exception:
            pass


def run_textual_app(file_path: str, tts_model: Optional[TTSBase] = None, overlap: Optional[float] = None):
    """Run the Textual-based Lue application."""
    app = LueApp(file_path, tts_model, overlap)
    app.run()
