"""
Textual-based application for Lue e-book reader.
This replaces the manual input handling with Textual's robust event system.
"""

import asyncio
from typing import Optional
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.binding import Binding

from . import reader as lue_reader
from .tts.base import TTSBase
from .textual_adapter import create_textual_adapter
from .textual_ui.reader_widget import ReaderWidget
from .textual_ui.toc_modal import TOCModal
from .textual_ui.ai_modal import AIAssistantModal


class LueApp(App):
    """Main Textual application for Lue e-book reader."""
    
    CSS = """
    #header {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    
    #book-title {
        width: 2fr;
        height: 1;
        text-align: left;
    }
    
    #content-display {
        height: 1fr;
        padding: 1;
        border: solid $primary;
    }
    
    #progress-bar {
        width: 1fr;
        height: 1;
    }
    
    #tts-status {
        height: 1;
        text-align: center;
        padding: 0 1;
        background: $surface;
    }
    
    #toc-container, #ai-container {
        width: 100%;
        height: 100%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    #toc-title, #ai-title {
        text-align: center;
        text-style: bold;
        height: 1;
        margin-bottom: 0;
    }
    
    #toc-content {
        height: 1fr;
        padding: 0;
        margin: 0;
    }
    
    #toc-footer {
        height: 2;
        text-align: center;
        margin-top: 0;
        padding: 0;
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
        Binding("f", "toggle_focus_mode", "Focus Mode"),
        
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
        
    async def on_unmount(self) -> None:
        """Handle app shutdown by calling lue's shutdown method."""
        try:
            if hasattr(self.lue, '_shutdown'):
                await self.lue._shutdown()
        except Exception:
            pass
        
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
            
    def action_toggle_focus_mode(self) -> None:
        """Toggle focus mode (show only highlighted sentence)."""
        try:
            # Toggle state on the model
            current = getattr(self.lue, 'focus_mode', False)
            self.lue.focus_mode = not current
            
            # Refresh display and status
            reader_widget = self.query_one(ReaderWidget)
            reader_widget.update_content_display()
            reader_widget.update_tts_status()
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
        """Show enhanced table of contents modal."""
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
            from . import ui
            ui.update_document_layout(self.lue)
            
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
