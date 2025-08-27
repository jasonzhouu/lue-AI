"""
Reader widget for the Lue e-book reader Textual interface.
Handles content display, progress tracking, and user interactions.
"""

from typing import Optional, TYPE_CHECKING
from textual.widgets import Static, ProgressBar
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from textual.events import Click, MouseScrollUp, MouseScrollDown
from textual.app import ComposeResult
from rich.text import Text
from rich.console import Console

if TYPE_CHECKING:
    from .. import reader as lue_reader


class ReaderWidget(Static):
    """Main reader widget that displays book content."""
    
    current_position = reactive((0, 0, 0))  # (chapter, paragraph, sentence)
    
    def __init__(self, lue_instance: "lue_reader.Lue"):
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
            from ..ui import get_terminal_size, get_visible_content
            _, height = get_terminal_size()
            
            # Ensure document layout is updated
            if not hasattr(self.lue, 'document_lines') or not self.lue.document_lines:
                from ..ui import update_document_layout
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
            focus_mode = getattr(self.lue, 'focus_mode', False)
            
            # Build status line as Rich Text for per-part styling
            status_text = Text()

            def append_part(part: str, style: str = "dim"):
                if status_text.plain:
                    status_text.append(" | ", style="dim")
                status_text.append(part, style=style)

            # Playback status
            if has_tts:
                append_part("⏸️ Paused" if is_paused else "▶️ Playing", style="dim")
            else:
                append_part("🔇 No TTS", style="dim")

            # Scroll mode
            append_part("📜 Auto" if auto_scroll else "📖 Manual", style="dim")

            # Focus indicator: always show; bold when on, dim when off
            append_part("🎯 Focus", style="bold" if focus_mode else "dim")

            tts_widget.update(status_text)
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
            
    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Handle trackpad/mouse wheel scroll up events."""
        try:
            # Scroll up by calling the lue instance's scroll method
            if hasattr(self.lue, 'scroll_up'):
                self.lue.scroll_up()
                # Update the display
                self.update_content_display()
                # Pause TTS to prevent reading during scrolling
                if hasattr(self.lue, 'is_paused'):
                    self.lue.is_paused = True
        except Exception:
            pass
            
    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        """Handle trackpad/mouse wheel scroll down events."""
        try:
            # Scroll down by calling the lue instance's scroll method
            if hasattr(self.lue, 'scroll_down'):
                self.lue.scroll_down()
                # Update the display
                self.update_content_display()
                # Pause TTS to prevent reading during scrolling
                if hasattr(self.lue, 'is_paused'):
                    self.lue.is_paused = True
        except Exception:
            pass
            
    def _find_sentence_at_position(self, click_x: int, click_y: int) -> Optional[tuple]:
        """Find which sentence is at the given click position."""
        try:
            # Get terminal dimensions and visible content area
            from ..ui import get_terminal_size, get_visible_content
            width, height = get_terminal_size()
            
            # Account for panel padding and borders
            content_start_y = 2  # Panel title and top border
            content_start_x = 5  # Left padding
            
            # Adjust click coordinates to content area
            content_y = click_y - content_start_y
            content_x = click_x - content_start_x
            
            # Ensure we have document layout
            if not hasattr(self.lue, 'document_lines') or not self.lue.document_lines:
                from ..ui import update_document_layout
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
            from .. import content_parser
            from ..ui import get_terminal_size
            
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
            from ..ui import _process_verse_markers
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
