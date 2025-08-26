import os
import sys
import asyncio
import re
import signal
import logging
import subprocess
from rich.console import Console
from rich.text import Text
import platformdirs

from . import config, content_parser, progress_manager, audio, ui, ai_assistant
from .tts.base import TTSBase

class Lue:
    def __init__(self, file_path, tts_model: TTSBase | None, overlap: float | None = None):
        self.console = Console()
        self.loop = None
        self.file_path = file_path
        self.book_title = os.path.splitext(os.path.basename(file_path))[0]
        self.progress_file = progress_manager.get_progress_file_path(self.book_title)
        self.overlap_override = overlap
        
        self._initialize_state()
        self._initialize_tts(tts_model)
        self._load_content()
        self._initialize_progress()
        self._initialize_ui_state()
        
    def _initialize_state(self):
        """Initialize basic application state."""
        self.running = True
        self.command = None
        self.playback_processes = []
        self.producer_task = None
        self.player_task = None
        self.background_task = None
        self.command_received_event = asyncio.Event()
        self.playback_finished_event = asyncio.Event()
        self.audio_queue = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        self.active_playback_tasks = []
        self.audio_restart_lock = asyncio.Lock()
        self.pending_restart_task = None
        
    def _initialize_tts(self, tts_model):
        """Initialize TTS-related state."""
        self.tts_model = tts_model
        self.tts_voice = tts_model.voice if tts_model and tts_model.voice else config.TTS_VOICES.get(tts_model.name) if tts_model else None
        
    def _load_content(self):
        """Load and process the document content."""
        self.console.print(f"[bold cyan]Loading document: {self.book_title}...[/bold cyan]")
        self.chapters = content_parser.extract_content(self.file_path, self.console)
        self.console.print(f"[green]Document loaded successfully![/green]")
        self.console.print(f"[bold cyan]Loading TTS model...[/bold cyan]")
        
        self.document_lines = []
        self.line_to_position = {}
        self.position_to_line = {}
        self.paragraph_line_ranges = {}
        
        self.total_sentences = sum(
            len(content_parser.split_into_sentences(paragraph)) 
            for chapter in self.chapters 
            for paragraph in chapter
        )
        
        # Update document layout immediately after loading content
        ui.update_document_layout(self)
        
    def _initialize_progress(self):
        """Initialize reading progress from saved state."""
        progress_data = progress_manager.load_extended_progress(self.progress_file)
        c, p, s = progress_data["c"], progress_data["p"], progress_data["s"]
        
        self.chapter_idx, self.paragraph_idx, self.sentence_idx = (
            progress_manager.validate_and_set_progress(self.chapters, self.progress_file, c, p, s)
        )
        self.ui_chapter_idx = self.chapter_idx
        self.ui_paragraph_idx = self.paragraph_idx
        self.ui_sentence_idx = self.sentence_idx
        
        self.scroll_offset = progress_data["scroll_offset"]
        self.auto_scroll_enabled = progress_data["auto_scroll_enabled"]
        self.is_paused = not progress_data["tts_enabled"]
        if not self.tts_model:
            self.is_paused = True
            
        # Restore manual scroll position if available
        manual_anchor = progress_data.get("manual_scroll_anchor")
        if manual_anchor:
            anchor_pos = tuple(manual_anchor)
            if anchor_pos in self.position_to_line:
                target_line = self.position_to_line[anchor_pos]
                self.scroll_offset = float(target_line)
                
    def _initialize_ui_state(self):
        """Initialize UI and interaction state."""
        self.ui_update_interval = 0.033
        self.target_scroll_offset = self.scroll_offset
        self.scroll_animation_speed = 0.8
        
        # Scroll state
        self.last_auto_scroll_position = (0, 0, 0)
        self.smooth_scroll_task = None
        self.last_scroll_time = 0
        self.scroll_momentum = 0
        
        # Mouse state
        self.last_mouse_event_time = 0
        self.mouse_sequence_buffer = ''
        self.mouse_sequence_active = False
        self.resize_anchor = None
        
        # Legacy UI state variables removed - handled by Textual interface
        # Table of Contents and AI Assistant state now managed by Textual modals
        self.ai_conversation = []
        self.ai_waiting_response = False
        self.ai_current_context = ""
        
        # Text selection state
        self.selection_active = False
        self.selection_start = None
        self.selection_end = None
        self.selection_start_pos = None
        self.selection_end_pos = None
        self.mouse_pressed = False
        self.mouse_press_pos = None
        
        # Rendering state
        self.last_rendered_state = None
        self.last_terminal_size = None
        self.render_lock = asyncio.Lock()
        self.resize_scheduled = False
        self.first_sentence_jump = False
        self._initial_load_complete = True

    async def initialize_tts(self) -> bool:
        """Initializes the selected TTS model."""
        if not self.tts_model:
            self.console.print("[yellow]No TTS model selected. TTS playback is disabled.[/yellow]")
            return True
        
        initialized = await self.tts_model.initialize()
        if initialized:
            await self.tts_model.warm_up()
            return True
        else:
            self.console.print(f"[bold red]Initialization of {self.tts_model.name.upper()} failed. TTS will be disabled.[/bold red]")
            self.tts_model = None
            self.is_paused = True
            return False

    async def initialize_ai_assistant(self) -> bool:
        """Initialize the AI assistant."""
        try:
            success = await ai_assistant.initialize_ai_assistant()
            if success:
                self.console.print("[green]AI Assistant initialized successfully![/green]")
            else:
                self.console.print("[yellow]AI Assistant initialization failed. Check GEMINI_API_KEY environment variable.[/yellow]")
            return success
        except Exception as e:
            self.console.print(f"[red]AI Assistant initialization error: {e}[/red]")
            return False

    def _post_command_sync(self, cmd):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._post_command(cmd), self.loop)

    async def _post_command(self, cmd):
        self.command = cmd
        self.command_received_event.set()

    def _is_position_visible(self, chapter_idx, paragraph_idx, sentence_idx):
        position_key = (chapter_idx, paragraph_idx, sentence_idx)
        if position_key not in self.position_to_line: return False
        target_line = self.position_to_line[position_key]
        _, height = ui.get_terminal_size()
        available_height = max(1, height - 4)
        return self.scroll_offset <= target_line < self.scroll_offset + available_height
    
    def _scroll_to_position(self, chapter_idx, paragraph_idx, sentence_idx, smooth=True):
        if not smooth and self._is_position_visible(chapter_idx, paragraph_idx, sentence_idx): return
        position_key = (chapter_idx, paragraph_idx, sentence_idx)
        if position_key in self.position_to_line:
            target_line = self.position_to_line[position_key]
            _, height = ui.get_terminal_size()
            available_height = max(1, height - 4)
            if hasattr(self, 'first_sentence_jump') and self.first_sentence_jump:
                new_offset = max(0, target_line) if self._is_position_visible(chapter_idx, paragraph_idx, sentence_idx) else max(0, target_line)
            else:
                new_offset = max(0, target_line - available_height // 2)
            max_scroll = max(0, len(self.document_lines) - available_height)
            new_offset = min(new_offset, max_scroll)
            if smooth: self._smooth_scroll_to(new_offset)
            else: self.scroll_offset = self.target_scroll_offset = new_offset

    def _smooth_scroll_to(self, target_offset, fast=False):
        self.target_scroll_offset = max(0, min(target_offset, len(self.document_lines) - 1))
        if self.smooth_scroll_task and not self.smooth_scroll_task.done(): self.smooth_scroll_task.cancel()
        self.smooth_scroll_task = asyncio.create_task(self._animate_scroll(fast))

    async def _animate_scroll(self, fast=False):
        try:
            if fast:
                self.scroll_offset = self.target_scroll_offset
                return
            start_offset, target_offset = self.scroll_offset, self.target_scroll_offset
            if abs(target_offset - start_offset) < 0.1: return
            animation_speed, frame_delay, convergence_threshold, min_step, steps, max_steps = 0.15, 0.03, 0.5, 2.0, 0, 80
            while abs(self.scroll_offset - self.target_scroll_offset) > convergence_threshold and steps < max_steps:
                diff = self.target_scroll_offset - self.scroll_offset
                step = diff * animation_speed
                distance = abs(diff)
                if distance > 30: step *= 2.5
                elif distance > 15: step *= 1.8
                elif distance > 5: step *= 1.2
                elif distance < 2: step *= 0.7
                if abs(step) < min_step: step = min_step if diff > 0 else -min_step
                if abs(step) > abs(diff): step = diff
                self.scroll_offset += step
                max_scroll = max(0, len(self.document_lines) - (ui.get_terminal_size()[1] - 4))
                self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
                await asyncio.sleep(frame_delay)
                steps += 1
            self.scroll_offset = self.target_scroll_offset
        except asyncio.CancelledError: pass

    def _find_sentence_at_click(self, click_x, click_y):
        width, height = ui.get_terminal_size()
        available_height = max(1, height - 4)
        content_y, content_x = click_y - 3, click_x - 5
        if not (0 <= content_y < available_height): return None
        clicked_line = int(self.scroll_offset) + content_y
        if clicked_line >= len(self.document_lines): return None
        if clicked_line in self.line_to_position:
            chap_idx, para_idx, _ = self.line_to_position[clicked_line]
            if (chap_idx, para_idx) in self.paragraph_line_ranges:
                para_start, _ = self.paragraph_line_ranges[(chap_idx, para_idx)]
                paragraph = self.chapters[chap_idx][para_idx]
                sentences = content_parser.split_into_sentences(paragraph)
                sentence_positions = []
                current_char = 0
                for sent_idx, sentence in enumerate(sentences):
                    sentence_positions.append((current_char, current_char + len(sentence), sent_idx))
                    current_char += len(sentence) + 1
                wrapped_lines = Text(paragraph, justify="left", no_wrap=False).wrap(self.console, max(20, width - 10))
                line_offset = clicked_line - para_start
                if 0 <= line_offset < len(wrapped_lines):
                    char_pos_in_para = sum(len(line.plain) for line in wrapped_lines[:line_offset]) + min(content_x, len(wrapped_lines[line_offset].plain))
                    for start_char, end_char, sent_idx in sentence_positions:
                        if start_char <= char_pos_in_para <= end_char:
                            return (chap_idx, para_idx, sent_idx)
        return None

    def _clear_selection(self):
        """Clear the current text selection."""
        self.selection_active = False
        self.selection_start = None
        self.selection_end = None
        self.selection_start_pos = None
        self.selection_end_pos = None

    def _get_selected_text(self):
        """Get the currently selected text as a string."""
        if not self.selection_active or not self.selection_start or not self.selection_end:
            return ""
        
        start_line, start_char = self.selection_start
        end_line, end_char = self.selection_end
        
        # Ensure start comes before end
        if start_line > end_line or (start_line == end_line and start_char > end_char):
            start_line, start_char, end_line, end_char = end_line, end_char, start_line, start_char
        
        selected_text = []
        
        for line_idx in range(start_line, end_line + 1):
            if line_idx >= len(self.document_lines):
                break
                
            line_text = self.document_lines[line_idx].plain
            
            if start_line == end_line:
                # Single line selection
                selection_start = max(0, min(start_char, len(line_text)))
                selection_end = max(0, min(end_char, len(line_text)))
                selected_text.append(line_text[selection_start:selection_end])
            elif line_idx == start_line:
                # First line of multi-line selection
                selection_start = max(0, min(start_char, len(line_text)))
                selected_text.append(line_text[selection_start:])
            elif line_idx == end_line:
                # Last line of multi-line selection
                selection_end = max(0, min(end_char, len(line_text)))
                selected_text.append(line_text[:selection_end])
            else:
                # Middle line of multi-line selection
                selected_text.append(line_text)
        
        # Join all lines with spaces instead of newlines
        raw_text = " ".join(selected_text)
        
        # Clean up the text: replace multiple spaces with single spaces
        # This handles cases like "  ", "   ", "    ", etc.
        cleaned_text = re.sub(r' {2,}', ' ', raw_text)
        
        # Remove any remaining newlines (just in case)
        cleaned_text = cleaned_text.replace('\n', ' ')
        
        # Clean up any double spaces that might have been created
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        
        # Strip leading/trailing whitespace
        return cleaned_text.strip()

    def _copy_to_clipboard(self, text):
        """Copy text to system clipboard using pbcopy on macOS."""
        if not text:
            return False
            
        try:
            # Use pbcopy on macOS to copy to clipboard
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return process.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _handle_copy_selection(self):
        """Handle copying selected text to clipboard."""
        if not self.selection_active:
            return False
            
        selected_text = self._get_selected_text()
        if selected_text:
            success = self._copy_to_clipboard(selected_text)
            if success:
                # Clear selection after successful copy
                self._clear_selection()
            return success
        return False

    def _advance_position(self, current_pos, mode='sentence', wrap=True):
        c, p, s = current_pos
        if mode == 'paragraph': p, s = p + 1, 0
        else: s += 1
        while c < len(self.chapters):
            if p < len(self.chapters[c]):
                if s < len(content_parser.split_into_sentences(self.chapters[c][p])):
                    if mode == 'paragraph': s = 0
                    return c, p, s
                p, s = p + 1, 0
            else: c, p, s = c + 1, 0, 0
        # If we've reached the end, either wrap to beginning or return None
        return (0, 0, 0) if wrap else None

    def _rewind_position(self, current_pos, mode='sentence'):
        c, p, s = current_pos
        if mode == 'paragraph':
            p, s = p - 1, 0
        else:
            s -= 1

        while c >= 0:
            if p >= 0:
                if s >= 0:
                    if mode == 'paragraph':
                        s = 0
                    return c, p, s
                
                p -= 1
                if p >= 0:
                    s = len(content_parser.split_into_sentences(self.chapters[c][p])) - 1
                else:
                    c -= 1
                    if c >= 0:
                        p = len(self.chapters[c]) - 1
                        s = len(content_parser.split_into_sentences(self.chapters[c][p])) - 1
            else:
                c -= 1
                if c >= 0:
                    p = len(self.chapters[c]) - 1
                    s = len(content_parser.split_into_sentences(self.chapters[c][p])) - 1

        # If we've rewound past the beginning, loop to the end
        c = len(self.chapters) - 1
        p = len(self.chapters[c]) - 1
        s = len(content_parser.split_into_sentences(self.chapters[c][p])) - 1
        return c, p, s

    def _get_topmost_visible_sentence(self):
        """Finds and returns the (c, p, s) of the topmost sentence in the viewport."""
        top_visible_line = int(self.scroll_offset)
        bottom_visible_line = top_visible_line + max(1, ui.get_terminal_size()[1] - 4)
        topmost_sentence_pos = None
        earliest_line = float('inf')

        for pos, line_num in self.position_to_line.items():
            if top_visible_line <= line_num < bottom_visible_line:
                if line_num < earliest_line:
                    earliest_line = line_num
                    topmost_sentence_pos = pos
        
        if topmost_sentence_pos:
            return topmost_sentence_pos

        last_pos_before_view = None
        latest_line = -1
        for pos, line_num in self.position_to_line.items():
            if line_num < top_visible_line and line_num > latest_line:
                latest_line = line_num
                last_pos_before_view = pos
        return last_pos_before_view
    
    def _calculate_ui_progress_percentage(self):
        """Calculate progress percentage based on current scroll position."""
        if len(self.document_lines) == 0:
            return 100.0
        
        # Calculate scroll percentage based on current scroll position
        _, height = ui.get_terminal_size()
        available_height = max(1, height - 4)
        max_scroll = max(0, len(self.document_lines) - available_height)
        
        if max_scroll == 0:
            return 100.0
        
        scroll_percentage = (self.scroll_offset / max_scroll) * 100
        return min(100.0, max(0.0, scroll_percentage))

    def _save_extended_progress(self, sync_audio_position=False):
        if sync_audio_position:
            self.chapter_idx, self.paragraph_idx, self.sentence_idx = self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx
        
        manual_scroll_anchor = self._get_topmost_visible_sentence()

        progress_manager.save_extended_progress(
            self.progress_file, 
            self.chapter_idx, 
            self.paragraph_idx, 
            self.sentence_idx, 
            self.scroll_offset, 
            not self.is_paused, 
            self.auto_scroll_enabled,
            manual_scroll_anchor=manual_scroll_anchor
        )

    def _scroll_to_position_immediate(self, chapter_idx, paragraph_idx, sentence_idx):
        if (chapter_idx, paragraph_idx, sentence_idx) in self.position_to_line:
            target_line = self.position_to_line[(chapter_idx, paragraph_idx, sentence_idx)]
            _, height = ui.get_terminal_size()
            available_height = max(1, height - 4)
            new_offset = min(max(0, target_line - available_height // 2), max(0, len(self.document_lines) - available_height))
            self.scroll_offset = self.target_scroll_offset = new_offset

    def _handle_scroll_up_immediate(self):
        self.auto_scroll_enabled = False
        self.scroll_offset = self.target_scroll_offset = max(0, self.scroll_offset - 1)
        if self.smooth_scroll_task and not self.smooth_scroll_task.done(): self.smooth_scroll_task.cancel()
        self.chapter_idx, self.paragraph_idx, self.sentence_idx = self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx
        progress_manager.save_extended_progress(self.progress_file, self.chapter_idx, self.paragraph_idx, self.sentence_idx, self.scroll_offset, not self.is_paused, self.auto_scroll_enabled)

    def _handle_scroll_down_immediate(self):
        self.auto_scroll_enabled = False
        max_scroll = max(0, len(self.document_lines) - (ui.get_terminal_size()[1] - 4))
        self.scroll_offset = self.target_scroll_offset = min(max_scroll, self.scroll_offset + 1)
        if self.smooth_scroll_task and not self.smooth_scroll_task.done(): self.smooth_scroll_task.cancel()
        self.chapter_idx, self.paragraph_idx, self.sentence_idx = self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx
        progress_manager.save_extended_progress(self.progress_file, self.chapter_idx, self.paragraph_idx, self.sentence_idx, self.scroll_offset, not self.is_paused, self.auto_scroll_enabled)

    def _handle_navigation_immediate(self, cmd):
        current_pos = (self.chapter_idx, self.paragraph_idx, self.sentence_idx)
        direction, mode = cmd.split('_')
        new_pos = self._advance_position(current_pos, mode) if direction == 'next' else self._rewind_position(current_pos, mode)
        if new_pos:
            self.first_sentence_jump = False
            self.chapter_idx, self.paragraph_idx, self.sentence_idx = new_pos
            self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx = new_pos
            self._scroll_to_position_immediate(*new_pos)
            self._save_extended_progress(sync_audio_position=True)

    async def _restart_audio_after_navigation(self):
        """Restart audio after navigation, preventing concurrent executions."""
        async with self.audio_restart_lock:
            # Cancel any pending restart task
            if self.pending_restart_task and not self.pending_restart_task.done():
                self.pending_restart_task.cancel()
                try:
                    await self.pending_restart_task
                except asyncio.CancelledError:
                    pass
            
            await audio.stop_and_clear_audio(self)
            
            # Add a small delay to debounce rapid navigation
            await asyncio.sleep(0.1)
            
            # Check if we're still running and not paused after the delay
            if not self.is_paused and self.running:
                await audio.play_from_current_position(self)

    def _handle_page_scroll_immediate(self, direction):
        self.auto_scroll_enabled = False
        page_size = max(1, ui.get_terminal_size()[1] - 4)
        new_offset = max(0, self.scroll_offset - page_size) if direction < 0 else min(max(0, len(self.document_lines) - page_size), self.scroll_offset + page_size)
        self.scroll_offset = self.target_scroll_offset = new_offset
        if self.smooth_scroll_task and not self.smooth_scroll_task.done(): self.smooth_scroll_task.cancel()
        self._save_extended_progress()

    def _handle_move_to_top_immediate(self):
        top_visible_line, bottom_visible_line = int(self.scroll_offset), int(self.scroll_offset) + max(1, ui.get_terminal_size()[1] - 4)
        topmost_sentence, topmost_line = None, float('inf')
        for pos, line in self.position_to_line.items():
            if top_visible_line <= line < bottom_visible_line and line < topmost_line:
                topmost_line, topmost_sentence = line, pos
        if topmost_sentence:
            self.chapter_idx, self.paragraph_idx, self.sentence_idx = topmost_sentence
            self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx = topmost_sentence
            self.first_sentence_jump = True
        self.auto_scroll_enabled = True
        if self.smooth_scroll_task and not self.smooth_scroll_task.done(): self.smooth_scroll_task.cancel()
        self._save_extended_progress()

    def _handle_move_to_beginning_immediate(self):
        self.auto_scroll_enabled = False
        self.scroll_offset = self.target_scroll_offset = 0
        if self.smooth_scroll_task and not self.smooth_scroll_task.done():
            self.smooth_scroll_task.cancel()
        self._save_extended_progress()

    def _handle_move_to_end_immediate(self):
        self.auto_scroll_enabled = False
        _, height = ui.get_terminal_size()
        available_height = max(1, height - 4)
        max_scroll = max(0, len(self.document_lines) - available_height)
        self.scroll_offset = self.target_scroll_offset = max_scroll
        if self.smooth_scroll_task and not self.smooth_scroll_task.done():
            self.smooth_scroll_task.cancel()
        self._save_extended_progress()

    async def _handle_pause_toggle(self):
        await audio.stop_and_clear_audio(self)
        if not self.is_paused and self.running:
            await audio.play_from_current_position(self)

    def _handle_resize(self, signum, frame):
        if not self.resize_scheduled:
            # In manual mode, create a simple anchor based on the top visible sentence
            if not self.auto_scroll_enabled:
                top_sentence = self._get_topmost_visible_sentence()
                if top_sentence and top_sentence in self.position_to_line:
                    top_line = self.position_to_line[top_sentence]
                    available_height = max(1, ui.get_terminal_size()[1] - 4)
                    fraction_in_view = (top_line - self.scroll_offset) / available_height
                    # Clamp between 0 and 1
                    fraction_in_view = max(0.0, min(1.0, fraction_in_view))
                    self.resize_anchor = (top_sentence, fraction_in_view)

            self.resize_scheduled = True
            self.loop.call_soon_threadsafe(self._post_command_sync, '_resize')

    async def _background_task_loop(self):
        last_update_time, last_sentence_pos, last_progress_save_time = 0, None, asyncio.get_event_loop().time()
        progress_save_interval = 5.0
        while self.running:
            try:
                current_time = asyncio.get_event_loop().time()
                needs_update = False
                if not self.is_paused:
                    target_pos = (self.chapter_idx, self.paragraph_idx, self.sentence_idx)
                    if target_pos != (self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx):
                        if self.first_sentence_jump and last_sentence_pos is not None and target_pos != last_sentence_pos:
                            self.first_sentence_jump = False
                        self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx = target_pos
                        needs_update = True
                        if self.auto_scroll_enabled:
                            self.last_auto_scroll_position = target_pos
                            self._scroll_to_position(*target_pos)
                        last_sentence_pos = target_pos
                if (current_time - last_progress_save_time) >= progress_save_interval:
                    self._save_extended_progress()
                    last_progress_save_time = current_time
                
                # Legacy UI rendering removed - use Textual interface instead
                # await ui.display_ui(self)
                last_update_time = current_time
                
                await asyncio.sleep(self.ui_update_interval)
            except asyncio.CancelledError: break
            except Exception as e:
                logging.error(f"Error in UI update loop: {e}", exc_info=True)
                await asyncio.sleep(self.ui_update_interval)

    async def _shutdown(self):
        self.running = False
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        
        # Cancel all tasks including pending restart task
        tasks_to_cancel = [self.smooth_scroll_task, self.background_task, self.pending_restart_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try: 
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError): 
                    pass
        
        await audio.stop_and_clear_audio(self)
        self._save_extended_progress()
        logging.info("--- Application Shutting Down ---")
        # Disable mouse reporting and restore terminal
        sys.stdout.write('\033[?1002l\033[2J\033[H\033[?25h')
        sys.stdout.flush()

        if config.SHOW_ERRORS_ON_EXIT:
            try:
                log_dir = platformdirs.user_log_dir(appname="lue", appauthor=False)
                log_file = os.path.join(log_dir, "error.log")
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    start_indices = [i for i, line in enumerate(lines) if "--- Application Starting ---" in line]
                    last_start_index = start_indices[-1] if start_indices else 0
                    
                    session_lines = lines[last_start_index:]
                    error_lines = [line.strip() for line in session_lines if " - ERROR - " in line]
                    
                    if error_lines:
                        error_console = Console()
                        error_console.print("\n[bold red]Errors recorded during this session:[/bold red]")
                        for error in error_lines:
                            message = ' - '.join(error.split(' - ')[3:])
                            error_console.print(f"- {message}")
                    
                    # Clear the log file after displaying errors
                    os.remove(log_file)
            except FileNotFoundError:
                pass
            except Exception as e:
                pass

    def _handle_exit_signal(self, signum, frame):
        self._save_extended_progress()
        self.running = False
        if self.loop and self.loop.is_running(): self.loop.call_soon_threadsafe(self._post_command_sync, 'quit')

    async def run(self):
        self.loop = asyncio.get_running_loop()
        # Legacy input handler removed - use Textual interface instead
        # self.loop.add_reader(sys.stdin.fileno(), input_handler.process_input, self)
        
        # Enable mouse reporting for drag events (button motion only)
        sys.stdout.write('\033[?1002h')  # Enable button motion events (drag only)
        sys.stdout.flush()
        
        signal.signal(signal.SIGWINCH, self._handle_resize)
        signal.signal(signal.SIGINT, self._handle_exit_signal)
        signal.signal(signal.SIGTERM, self._handle_exit_signal)
        
        if not self.chapters or not self.chapters[0]: return
            
        self.background_task = asyncio.create_task(self._background_task_loop())
        
        await audio.play_from_current_position(self)
        
        while self.running:
            await self.command_received_event.wait()
            self.command_received_event.clear()
            cmd = self.command
            self.command = None
            if not cmd: continue
            
            if isinstance(cmd, tuple):
                command_name, data = cmd
                if command_name == '_update_highlight':
                    if not self.is_paused: self.chapter_idx, self.paragraph_idx, self.sentence_idx = data
                elif command_name == 'click_jump':
                    if clicked_position := self._find_sentence_at_click(*data):
                        self.first_sentence_jump = False
                        self.chapter_idx, self.paragraph_idx, self.sentence_idx = clicked_position
                        self.ui_chapter_idx, self.ui_paragraph_idx, self.ui_sentence_idx = clicked_position
                        self.auto_scroll_enabled = False
                        self._save_extended_progress(sync_audio_position=True)
                        self.pending_restart_task = asyncio.create_task(self._restart_audio_after_navigation())
                continue
            
        await self._shutdown()