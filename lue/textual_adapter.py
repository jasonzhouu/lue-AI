"""
Adapter layer to bridge existing Lue reader functionality with Textual interface.
This preserves all existing methods while adding Textual-compatible interfaces.
"""

from typing import Optional, Tuple, List
from rich.text import Text
from . import content_parser


class TextualReaderAdapter:
    """Adapter to make existing Lue reader compatible with Textual interface."""
    
    def __init__(self, lue_instance):
        self.lue = lue_instance
        
    def get_current_display_content(self, height: int = 20) -> Text:
        """Get formatted content for current view with proper highlighting."""
        try:
            # Import here to avoid circular imports
            from . import ui, content_parser
            from .ui_theme import COLORS
            
            # Use existing UI layout if available
            if hasattr(self.lue, 'document_lines') and self.lue.document_lines:
                # Get terminal dimensions
                width, term_height = ui.get_terminal_size()
                available_width = max(20, width - 10)
                display_height = min(height, term_height - 4)
                
                start_line = max(0, int(getattr(self.lue, 'scroll_offset', 0)))
                end_line = min(len(self.lue.document_lines), start_line + display_height)
                
                visible_lines = []
                current_paragraph_key = (self.lue.chapter_idx, self.lue.paragraph_idx)
                
                # Get highlighted paragraph content
                highlighted_paragraph_lines = None
                if (hasattr(self.lue, 'paragraph_line_ranges') and 
                    current_paragraph_key in self.lue.paragraph_line_ranges):
                    
                    para_start, para_end = self.lue.paragraph_line_ranges[current_paragraph_key]
                    paragraph = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                    sentences = content_parser.split_into_sentences(paragraph)
                    highlighted_text = Text(justify="left", no_wrap=False)
                    
                    # Build highlighted paragraph with current sentence emphasized
                    for sent_idx, sentence in enumerate(sentences):
                        if sent_idx == self.lue.sentence_idx:
                            highlighted_text.append(sentence, style="bold yellow on blue")
                        else:
                            highlighted_text.append(sentence, style="white")
                        if sent_idx < len(sentences) - 1:
                            highlighted_text.append(" ", style="white")
                    
                    highlighted_paragraph_lines = highlighted_text.wrap(self.lue.console, available_width)
                
                # Build visible content
                for i in range(start_line, end_line):
                    if i < len(self.lue.document_lines):
                        line = self.lue.document_lines[i]
                        
                        # Check if this line is part of current paragraph
                        if (hasattr(self.lue, 'line_to_position') and 
                            i in self.lue.line_to_position and
                            self.lue.line_to_position[i][:2] == current_paragraph_key and
                            highlighted_paragraph_lines is not None):
                            
                            para_start, para_end = self.lue.paragraph_line_ranges[current_paragraph_key]
                            line_offset = i - para_start
                            
                            if 0 <= line_offset < len(highlighted_paragraph_lines):
                                line = highlighted_paragraph_lines[line_offset]
                        
                        visible_lines.append(str(line))
                
                return Text("\n".join(visible_lines))
            else:
                # Fallback to basic paragraph display
                return self._get_basic_content_display()
                
        except Exception as e:
            return Text(f"Error loading content: {str(e)}")
            
    def _line_contains_current_sentence(self, line_idx: int) -> bool:
        """Check if line contains the current sentence."""
        try:
            current_pos = (self.lue.chapter_idx, self.lue.paragraph_idx, self.lue.sentence_idx)
            if hasattr(self.lue, 'position_to_line') and current_pos in self.lue.position_to_line:
                current_line = self.lue.position_to_line[current_pos]
                return abs(line_idx - current_line) < 2  # Highlight nearby lines
            return False
        except Exception:
            return False
            
    def _get_basic_content_display(self) -> Text:
        """Basic content display as fallback with sentence highlighting."""
        try:
            from . import content_parser
            
            chapter_idx = getattr(self.lue, 'chapter_idx', 0)
            para_idx = getattr(self.lue, 'paragraph_idx', 0)
            sent_idx = getattr(self.lue, 'sentence_idx', 0)
            
            if (chapter_idx < len(self.lue.chapters) and 
                para_idx < len(self.lue.chapters[chapter_idx])):
                
                chapter = self.lue.chapters[chapter_idx]
                content_lines = []
                
                # Add previous paragraph for context
                if para_idx > 0:
                    prev_para = chapter[para_idx - 1]
                    content_lines.append(Text(prev_para, style="dim"))
                    content_lines.append(Text(""))
                
                # Current paragraph with sentence highlighting
                current_para = chapter[para_idx]
                sentences = content_parser.split_into_sentences(current_para)
                
                highlighted_para = Text()
                for i, sentence in enumerate(sentences):
                    if i == sent_idx:
                        highlighted_para.append(sentence, style="bold yellow on blue")
                    else:
                        highlighted_para.append(sentence, style="white")
                    if i < len(sentences) - 1:
                        highlighted_para.append(" ", style="white")
                
                content_lines.append(highlighted_para)
                
                # Add next paragraph for context
                if para_idx + 1 < len(chapter):
                    content_lines.append(Text(""))
                    next_para = chapter[para_idx + 1]
                    content_lines.append(Text(next_para, style="dim"))
                
                # Combine all content
                result = Text()
                for i, line in enumerate(content_lines):
                    if i > 0:
                        result.append("\n")
                    result.append(line)
                
                return result
            else:
                return Text("No content available")
                
        except Exception as e:
            return Text(f"Error displaying content: {str(e)}")
    
    def get_reading_progress(self) -> float:
        """Get current reading progress as percentage."""
        try:
            if hasattr(self.lue, 'total_sentences') and self.lue.total_sentences > 0:
                # Calculate based on sentences
                current_sentences = 0
                for i in range(self.lue.chapter_idx):
                    for paragraph in self.lue.chapters[i]:
                        current_sentences += len(content_parser.split_into_sentences(paragraph))
                
                for i in range(self.lue.paragraph_idx):
                    paragraph = self.lue.chapters[self.lue.chapter_idx][i]
                    current_sentences += len(content_parser.split_into_sentences(paragraph))
                
                current_sentences += self.lue.sentence_idx
                
                return (current_sentences / self.lue.total_sentences) * 100
            else:
                # Fallback to paragraph-based calculation
                total_paragraphs = sum(len(chapter) for chapter in self.lue.chapters)
                current_paragraph = sum(len(self.lue.chapters[i]) for i in range(self.lue.chapter_idx))
                current_paragraph += self.lue.paragraph_idx
                
                return (current_paragraph / total_paragraphs * 100) if total_paragraphs > 0 else 0
                
        except Exception:
            return 0.0
    
    def get_chapter_titles(self) -> List[str]:
        """Get list of chapter titles using proper content parser."""
        try:
            from . import content_parser
            # Use the proper extract_chapter_titles function that returns (index, title) tuples
            chapter_title_tuples = content_parser.extract_chapter_titles(self.lue.chapters)
            # Extract just the titles for the list
            return [title for idx, title in chapter_title_tuples]
        except Exception:
            # Fallback: generate basic titles
            return [f"Chapter {i+1}" for i in range(len(self.lue.chapters))]
    
    def get_current_sentence(self) -> str:
        """Get the current sentence text."""
        try:
            chapter_idx = getattr(self.lue, 'chapter_idx', 0)
            para_idx = getattr(self.lue, 'paragraph_idx', 0)
            sent_idx = getattr(self.lue, 'sentence_idx', 0)
            
            if (chapter_idx < len(self.lue.chapters) and 
                para_idx < len(self.lue.chapters[chapter_idx])):
                
                paragraph = self.lue.chapters[chapter_idx][para_idx]
                sentences = content_parser.split_into_sentences(paragraph)
                
                if sent_idx < len(sentences):
                    return sentences[sent_idx].strip()
                    
            return "No sentence available"
        except Exception:
            return "Error getting sentence"
    
    def jump_to_chapter(self, chapter_idx: int) -> None:
        """Jump to specified chapter."""
        try:
            if 0 <= chapter_idx < len(self.lue.chapters):
                self.lue.chapter_idx = chapter_idx
                self.lue.paragraph_idx = 0
                self.lue.sentence_idx = 0
                
                # Update UI state if available
                if hasattr(self.lue, 'ui_chapter_idx'):
                    self.lue.ui_chapter_idx = chapter_idx
                    self.lue.ui_paragraph_idx = 0
                    self.lue.ui_sentence_idx = 0
                
                # Update scroll position if available
                if hasattr(self.lue, 'position_to_line'):
                    new_pos = (chapter_idx, 0, 0)
                    if new_pos in self.lue.position_to_line:
                        self.lue.scroll_offset = float(self.lue.position_to_line[new_pos])
                        self.lue.target_scroll_offset = self.lue.scroll_offset
                        
        except Exception:
            pass
    
    async def get_ai_response(self, question: str) -> str:
        """Get AI response for the given question."""
        try:
            from . import ai_assistant
            # Use the global AI assistant instance
            if ai_assistant.ai_assistant.initialized:
                return await ai_assistant.ask_ai_question(self.lue, question)
            else:
                # Try to initialize if not already done
                success = await ai_assistant.initialize_ai_assistant()
                if success:
                    return await ai_assistant.ask_ai_question(self.lue, question)
                else:
                    return "AI Assistant not configured. Please check if GEMINI_API_KEY environment variable is set."
        except Exception as e:
            return f"Error getting AI response: {str(e)}"
    
    # Navigation methods that directly call the navigation logic
    def move_to_prev_paragraph(self) -> None:
        """Move to previous paragraph."""
        try:
            if hasattr(self.lue, '_handle_navigation_immediate'):
                self.lue._handle_navigation_immediate('prev_paragraph')
            else:
                # Fallback: direct navigation
                if self.lue.paragraph_idx > 0:
                    self.lue.paragraph_idx -= 1
                    self.lue.sentence_idx = 0
                elif self.lue.chapter_idx > 0:
                    self.lue.chapter_idx -= 1
                    self.lue.paragraph_idx = len(self.lue.chapters[self.lue.chapter_idx]) - 1
                    self.lue.sentence_idx = 0
                self._update_ui_position()
        except Exception:
            pass
    
    def move_to_next_paragraph(self) -> None:
        """Move to next paragraph."""
        try:
            if hasattr(self.lue, '_handle_navigation_immediate'):
                self.lue._handle_navigation_immediate('next_paragraph')
            else:
                # Fallback: direct navigation
                current_chapter = self.lue.chapters[self.lue.chapter_idx]
                if self.lue.paragraph_idx < len(current_chapter) - 1:
                    self.lue.paragraph_idx += 1
                    self.lue.sentence_idx = 0
                elif self.lue.chapter_idx < len(self.lue.chapters) - 1:
                    self.lue.chapter_idx += 1
                    self.lue.paragraph_idx = 0
                    self.lue.sentence_idx = 0
                self._update_ui_position()
        except Exception:
            pass
    
    def move_to_prev_sentence(self) -> None:
        """Move to previous sentence."""
        try:
            if hasattr(self.lue, '_handle_navigation_immediate'):
                self.lue._handle_navigation_immediate('prev_sentence')
            else:
                # Fallback: direct navigation
                from . import content_parser
                if self.lue.sentence_idx > 0:
                    self.lue.sentence_idx -= 1
                else:
                    # Move to previous paragraph
                    self.move_to_prev_paragraph()
                    # Set to last sentence of new paragraph
                    current_para = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                    sentences = content_parser.split_into_sentences(current_para)
                    self.lue.sentence_idx = max(0, len(sentences) - 1)
                self._update_ui_position()
        except Exception:
            pass
    
    def move_to_next_sentence(self) -> None:
        """Move to next sentence."""
        try:
            if hasattr(self.lue, '_handle_navigation_immediate'):
                self.lue._handle_navigation_immediate('next_sentence')
            else:
                # Fallback: direct navigation
                from . import content_parser
                current_para = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                sentences = content_parser.split_into_sentences(current_para)
                if self.lue.sentence_idx < len(sentences) - 1:
                    self.lue.sentence_idx += 1
                else:
                    # Move to next paragraph
                    self.move_to_next_paragraph()
                self._update_ui_position()
        except Exception:
            pass
    
    def scroll_page_up(self) -> None:
        """Scroll page up."""
        try:
            # Stop auto scroll when manually scrolling
            self.lue.auto_scroll_enabled = False
            
            # Adjust scroll offset
            from . import ui
            _, height = ui.get_terminal_size()
            available_height = max(1, height - 4)
            self.lue.scroll_offset = max(0, self.lue.scroll_offset - available_height)
            self.lue.target_scroll_offset = self.lue.scroll_offset
            
            # Cancel smooth scroll if active
            if hasattr(self.lue, 'smooth_scroll_task') and self.lue.smooth_scroll_task and not self.lue.smooth_scroll_task.done():
                self.lue.smooth_scroll_task.cancel()
            
            # Update position tracking
            self.lue.chapter_idx = getattr(self.lue, 'ui_chapter_idx', self.lue.chapter_idx)
            self.lue.paragraph_idx = getattr(self.lue, 'ui_paragraph_idx', self.lue.paragraph_idx) 
            self.lue.sentence_idx = getattr(self.lue, 'ui_sentence_idx', self.lue.sentence_idx)
            
            # Save progress
            if hasattr(self.lue, '_save_extended_progress'):
                self.lue._save_extended_progress()
        except Exception:
            pass
    
    def scroll_page_down(self) -> None:
        """Scroll page down."""
        try:
            # Stop auto scroll when manually scrolling
            self.lue.auto_scroll_enabled = False
            
            # Adjust scroll offset
            from . import ui
            _, height = ui.get_terminal_size()
            available_height = max(1, height - 4)
            max_scroll = max(0, len(self.lue.document_lines) - available_height)
            self.lue.scroll_offset = min(max_scroll, self.lue.scroll_offset + available_height)
            self.lue.target_scroll_offset = self.lue.scroll_offset
            
            # Cancel smooth scroll if active
            if hasattr(self.lue, 'smooth_scroll_task') and self.lue.smooth_scroll_task and not self.lue.smooth_scroll_task.done():
                self.lue.smooth_scroll_task.cancel()
            
            # Update position tracking
            self.lue.chapter_idx = getattr(self.lue, 'ui_chapter_idx', self.lue.chapter_idx)
            self.lue.paragraph_idx = getattr(self.lue, 'ui_paragraph_idx', self.lue.paragraph_idx)
            self.lue.sentence_idx = getattr(self.lue, 'ui_sentence_idx', self.lue.sentence_idx)
            
            # Save progress
            if hasattr(self.lue, '_save_extended_progress'):
                self.lue._save_extended_progress()
        except Exception:
            pass
    
    def scroll_up(self) -> None:
        """Scroll up."""
        try:
            # Use existing method if available
            if hasattr(self.lue, '_handle_scroll_up_immediate'):
                self.lue._handle_scroll_up_immediate()
            else:
                # Fallback: manual implementation
                self.lue.auto_scroll_enabled = False
                self.lue.scroll_offset = max(0, self.lue.scroll_offset - 1)
                self.lue.target_scroll_offset = self.lue.scroll_offset
                
                # Cancel smooth scroll if active
                if hasattr(self.lue, 'smooth_scroll_task') and self.lue.smooth_scroll_task and not self.lue.smooth_scroll_task.done():
                    self.lue.smooth_scroll_task.cancel()
                
                # Update position tracking
                self.lue.chapter_idx = getattr(self.lue, 'ui_chapter_idx', self.lue.chapter_idx)
                self.lue.paragraph_idx = getattr(self.lue, 'ui_paragraph_idx', self.lue.paragraph_idx)
                self.lue.sentence_idx = getattr(self.lue, 'ui_sentence_idx', self.lue.sentence_idx)
                
                # Save progress
                if hasattr(self.lue, '_save_extended_progress'):
                    self.lue._save_extended_progress()
        except Exception:
            pass
    
    def scroll_down(self) -> None:
        """Scroll down."""
        try:
            # Use existing method if available
            if hasattr(self.lue, '_handle_scroll_down_immediate'):
                self.lue._handle_scroll_down_immediate()
            else:
                # Fallback: manual implementation
                self.lue.auto_scroll_enabled = False
                from . import ui
                _, height = ui.get_terminal_size()
                available_height = max(1, height - 4)
                max_scroll = max(0, len(self.lue.document_lines) - available_height)
                self.lue.scroll_offset = min(max_scroll, self.lue.scroll_offset + 1)
                self.lue.target_scroll_offset = self.lue.scroll_offset
                
                # Cancel smooth scroll if active
                if hasattr(self.lue, 'smooth_scroll_task') and self.lue.smooth_scroll_task and not self.lue.smooth_scroll_task.done():
                    self.lue.smooth_scroll_task.cancel()
                
                # Update position tracking
                self.lue.chapter_idx = getattr(self.lue, 'ui_chapter_idx', self.lue.chapter_idx)
                self.lue.paragraph_idx = getattr(self.lue, 'ui_paragraph_idx', self.lue.paragraph_idx)
                self.lue.sentence_idx = getattr(self.lue, 'ui_sentence_idx', self.lue.sentence_idx)
                
                # Save progress
                if hasattr(self.lue, '_save_extended_progress'):
                    self.lue._save_extended_progress()
        except Exception:
            pass
    
    def move_to_beginning(self) -> None:
        """Move to beginning of book."""
        try:
            if hasattr(self.lue, '_handle_move_to_beginning_immediate'):
                self.lue._handle_move_to_beginning_immediate()
            else:
                # Fallback: direct navigation
                self.lue.chapter_idx = 0
                self.lue.paragraph_idx = 0
                self.lue.sentence_idx = 0
                self.lue.scroll_offset = 0
                self.lue.target_scroll_offset = 0
                self._update_ui_position()
        except Exception:
            pass
    
    def move_to_end(self) -> None:
        """Move to end of book."""
        try:
            if hasattr(self.lue, '_handle_move_to_end_immediate'):
                self.lue._handle_move_to_end_immediate()
            else:
                # Fallback: direct navigation
                self.lue.chapter_idx = len(self.lue.chapters) - 1
                self.lue.paragraph_idx = len(self.lue.chapters[self.lue.chapter_idx]) - 1
                # Get last sentence
                from . import content_parser
                current_para = self.lue.chapters[self.lue.chapter_idx][self.lue.paragraph_idx]
                sentences = content_parser.split_into_sentences(current_para)
                self.lue.sentence_idx = max(0, len(sentences) - 1)
                # Scroll to end
                from . import ui
                _, height = ui.get_terminal_size()
                available_height = max(1, height - 4)
                max_scroll = max(0, len(self.lue.document_lines) - available_height)
                self.lue.scroll_offset = max_scroll
                self.lue.target_scroll_offset = max_scroll
                self._update_ui_position()
        except Exception:
            pass
    
    def move_to_top_visible(self) -> None:
        """Move to top visible line."""
        try:
            # Find position at top of screen
            start_line = int(self.lue.scroll_offset)
            if (hasattr(self.lue, 'line_to_position') and 
                start_line in self.lue.line_to_position):
                new_pos = self.lue.line_to_position[start_line]
                self.lue.chapter_idx, self.lue.paragraph_idx, self.lue.sentence_idx = new_pos
                self._update_ui_position()
                
                # Restart audio after navigation if not paused
                self._restart_audio_after_navigation()
        except Exception:
            pass
    
    def toggle_pause(self) -> None:
        """Toggle TTS pause/resume."""
        try:
            self.lue.is_paused = not getattr(self.lue, 'is_paused', True)
            # Save progress
            if hasattr(self.lue, '_save_extended_progress'):
                self.lue._save_extended_progress()
        except Exception:
            pass
    
    def toggle_auto_scroll(self) -> None:
        """Toggle auto scroll."""
        try:
            self.lue.auto_scroll_enabled = not getattr(self.lue, 'auto_scroll_enabled', False)
            if self.lue.auto_scroll_enabled and hasattr(self.lue, '_scroll_to_position_immediate'):
                self.lue._scroll_to_position_immediate(self.lue.chapter_idx, self.lue.paragraph_idx, self.lue.sentence_idx)
            # Save progress
            if hasattr(self.lue, '_save_extended_progress'):
                self.lue._save_extended_progress()
        except Exception:
            pass
    
    def _update_ui_position(self) -> None:
        """Update UI position tracking."""
        try:
            # Update UI state if available
            if hasattr(self.lue, 'ui_chapter_idx'):
                self.lue.ui_chapter_idx = self.lue.chapter_idx
                self.lue.ui_paragraph_idx = self.lue.paragraph_idx
                self.lue.ui_sentence_idx = self.lue.sentence_idx
            
            # Update scroll position if available
            if hasattr(self.lue, 'position_to_line'):
                new_pos = (self.lue.chapter_idx, self.lue.paragraph_idx, self.lue.sentence_idx)
                if new_pos in self.lue.position_to_line:
                    target_line = self.lue.position_to_line[new_pos]
                    from . import ui
                    _, height = ui.get_terminal_size()
                    available_height = max(1, height - 4)
                    new_offset = max(0, target_line - available_height // 2)
                    max_scroll = max(0, len(self.lue.document_lines) - available_height)
                    self.lue.scroll_offset = min(new_offset, max_scroll)
                    self.lue.target_scroll_offset = self.lue.scroll_offset
            
            # Save progress
            if hasattr(self.lue, '_save_extended_progress'):
                self.lue._save_extended_progress(sync_audio_position=True)
                
            # Restart audio after navigation if not paused
            self._restart_audio_after_navigation()
        except Exception:
            pass
    
    def _restart_audio_after_navigation(self) -> None:
        """Restart audio after navigation, similar to original implementation."""
        try:
            # Kill any existing audio playback first
            self._kill_audio_immediately()
            
            # Only restart if TTS is available and not paused
            if (hasattr(self.lue, 'tts_model') and self.lue.tts_model and 
                not getattr(self.lue, 'is_paused', True)):
                
                # Use async restart if available
                if hasattr(self.lue, '_restart_audio_after_navigation'):
                    import asyncio
                    if hasattr(self.lue, 'loop') and self.lue.loop:
                        # Schedule the restart task
                        if hasattr(self.lue, 'pending_restart_task'):
                            self.lue.pending_restart_task = asyncio.create_task(self.lue._restart_audio_after_navigation())
        except Exception:
            pass
    
    def _kill_audio_immediately(self) -> None:
        """Kill audio playback immediately, similar to original implementation."""
        try:
            import subprocess
            
            # Kill existing playback processes
            if hasattr(self.lue, 'playback_processes'):
                for process in self.lue.playback_processes[:]:
                    try:
                        process.kill()
                    except (ProcessLookupError, AttributeError):
                        pass
            
            # Kill any ffplay processes
            try:
                subprocess.run(['pkill', '-f', 'ffplay'], check=False, 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        except Exception:
            pass


def create_textual_adapter(lue_instance):
    """Create a Textual adapter for the given Lue instance."""
    adapter = TextualReaderAdapter(lue_instance)
    
    # Monkey-patch the adapter methods onto the lue instance
    lue_instance.get_current_display_content = adapter.get_current_display_content
    lue_instance.get_reading_progress = adapter.get_reading_progress
    lue_instance.get_chapter_titles = adapter.get_chapter_titles
    lue_instance.get_current_sentence = adapter.get_current_sentence
    lue_instance.jump_to_chapter = adapter.jump_to_chapter
    lue_instance.get_ai_response = adapter.get_ai_response
    lue_instance.move_to_prev_paragraph = adapter.move_to_prev_paragraph
    lue_instance.move_to_next_paragraph = adapter.move_to_next_paragraph
    lue_instance.move_to_prev_sentence = adapter.move_to_prev_sentence
    lue_instance.move_to_next_sentence = adapter.move_to_next_sentence
    lue_instance.scroll_page_up = adapter.scroll_page_up
    lue_instance.scroll_page_down = adapter.scroll_page_down
    lue_instance.scroll_up = adapter.scroll_up
    lue_instance.scroll_down = adapter.scroll_down
    lue_instance.move_to_beginning = adapter.move_to_beginning
    lue_instance.move_to_end = adapter.move_to_end
    lue_instance.move_to_top_visible = adapter.move_to_top_visible
    lue_instance.toggle_pause = adapter.toggle_pause
    lue_instance.toggle_auto_scroll = adapter.toggle_auto_scroll
    
    return lue_instance
