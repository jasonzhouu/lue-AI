import sys
import select
import asyncio
import subprocess

def process_input(reader):
    """Process user input from stdin."""
    try:
        if select.select([sys.stdin], [], [], 0)[0]:
            data = sys.stdin.read(1)
            
            if not data:
                return
            
            # Handle AI Assistant input first (highest priority)
            if reader.ai_visible:
                if data == '\x1b':  # Escape key - close AI
                    reader.ai_visible = False
                    # Don't call toggle_ai_assistant since we already set ai_visible = False
                    # Just trigger a UI refresh to return to normal reading view
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'refresh_ui')
                    return
                elif data == '\r' or data == '\n':  # Enter key
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'ai_send_message')
                    return
                elif data == '\x15':  # Ctrl+U - clear input
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'ai_clear_input')
                    return
                elif data.isprintable() and len(data) == 1:
                    # Add character to input buffer
                    reader.ai_input_buffer += data
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'ai_update_display')
                    return
                elif data == '\x7f' or data == '\b':  # Backspace
                    if reader.ai_input_buffer:
                        reader.ai_input_buffer = reader.ai_input_buffer[:-1]
                        reader.loop.call_soon_threadsafe(reader._post_command_sync, 'ai_update_display')
                        return
                # If none of the AI-specific keys, ignore other input
                return
            
            # Handle TOC input (second priority)
            if reader.toc_visible:
                if data == '\x1b':  # Escape key - close TOC
                    reader.toc_visible = False
                    # Don't call toggle_toc since we already set toc_visible = False
                    # Just trigger a UI refresh to return to normal reading view
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'refresh_ui')
                    return
                elif data == '\r' or data == '\n':  # Enter key - jump to selected chapter
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'toc_select')
                    return
                elif data == 'c':  # c - close TOC
                    reader.toc_visible = False
                    reader.loop.call_soon_threadsafe(reader._post_command_sync, 'refresh_ui')
                    return
                elif data == 'q':  # q - quit program
                    reader.running = False
                    reader.command_received_event.set()
                    return
                # Arrow keys will be handled in escape sequence processing below
                # Other keys will fall through to normal processing
            
            if data == '\x1b':
                # Handle escape sequences (arrow keys, mouse, etc.)
                reader.mouse_sequence_buffer = data
                reader.mouse_sequence_active = True
                return
            elif reader.mouse_sequence_active:
                reader.mouse_sequence_buffer += data
                
                if reader.mouse_sequence_buffer.startswith('\x1b[<') and (data == 'M' or data == 'm'):
                    sequence = reader.mouse_sequence_buffer
                    reader.mouse_sequence_buffer = ''
                    reader.mouse_sequence_active = False
                    
                    if len(sequence) > 3:
                        mouse_part = sequence[3:]
                        if mouse_part.endswith('M') or mouse_part.endswith('m'):
                            try:
                                parts = mouse_part[:-1].split(';')
                                if len(parts) >= 3:
                                    button = int(parts[0])
                                    x_pos = int(parts[1])
                                    y_pos = int(parts[2])
                                    
                                    if mouse_part.endswith('M'):
                                        if button == 0:
                                            if reader._is_click_on_progress_bar(x_pos, y_pos):
                                                if reader._handle_progress_bar_click(x_pos, y_pos):
                                                    return
                                            
                                            if not reader._is_click_on_text(x_pos, y_pos):
                                                return

                                            # Cancel any pending restart task before killing audio
                                            if hasattr(reader, 'pending_restart_task') and reader.pending_restart_task and not reader.pending_restart_task.done():
                                                reader.pending_restart_task.cancel()
                                            
                                            _kill_audio_immediately(reader)
                                            reader.loop.call_soon_threadsafe(reader._post_command_sync, ('click_jump', (x_pos, y_pos)))
                                        elif button == 64:
                                            if reader.auto_scroll_enabled:
                                                reader.auto_scroll_enabled = False
                                            reader.loop.call_soon_threadsafe(reader._post_command_sync, 'wheel_scroll_up')
                                        elif button == 65:
                                            if reader.auto_scroll_enabled:
                                                reader.auto_scroll_enabled = False
                                            reader.loop.call_soon_threadsafe(reader._post_command_sync, 'wheel_scroll_down')
                                    return
                            except (ValueError, IndexError):
                                pass
                    return
                
                elif reader.mouse_sequence_buffer.startswith('\x1b[') and len(reader.mouse_sequence_buffer) >= 3 and data in 'ABCD':
                    sequence = reader.mouse_sequence_buffer
                    reader.mouse_sequence_buffer = ''
                    reader.mouse_sequence_active = False
                    
                    cmd = None
                    if reader.toc_visible:
                        # Handle TOC navigation with arrow keys
                        if data == 'A':  # Up arrow
                            cmd = 'toc_up'
                        elif data == 'B':  # Down arrow
                            cmd = 'toc_down'
                        elif data == 'C':  # Right arrow - close TOC
                            cmd = 'toggle_toc'
                        elif data == 'D':  # Left arrow - close TOC
                            cmd = 'toggle_toc'
                    else:
                        # Normal navigation
                        _kill_audio_immediately(reader)
                        if data == 'C':
                            cmd = 'next_sentence'
                        elif data == 'D':
                            cmd = 'prev_sentence'
                        elif data == 'B':
                            cmd = 'next_paragraph'
                        elif data == 'A':
                            cmd = 'prev_paragraph'
                    
                    if cmd:
                        reader.loop.call_soon_threadsafe(reader._post_command_sync, cmd)
                    return
                
                # Handle incomplete escape sequences - if we have just '\x1b' and no more input
                elif len(reader.mouse_sequence_buffer) == 1 and reader.mouse_sequence_buffer == '\x1b':
                    # Check if more input is immediately available
                    if not select.select([sys.stdin], [], [], 0.01)[0]:  # Reduced timeout to 10ms
                        # No more input within timeout, treat as standalone ESC
                        reader.mouse_sequence_buffer = ''
                        reader.mouse_sequence_active = False
                        # ESC handling is now done at higher priority above
                
                return
            
            reader.mouse_sequence_buffer = ''
            reader.mouse_sequence_active = False
            
            if data == 'q':
                reader.running = False
                reader.command_received_event.set()
                return
            
            cmd = None
            if data == 'p':
                cmd = 'pause'
            elif data == 'h':
                cmd = 'prev_paragraph'
            elif data == 'j':
                cmd = 'prev_sentence'
            elif data == 'k':
                cmd = 'next_sentence'
            elif data == 'l':
                cmd = 'next_paragraph'
            elif data == 'i':
                cmd = 'scroll_page_up'
            elif data == 'm':
                cmd = 'scroll_page_down'
            elif data == 'u':
                cmd = 'scroll_up'
            elif data == 'n':
                cmd = 'scroll_down'
            elif data == 'a':
                cmd = 'toggle_auto_scroll'
            elif data == 't':
                cmd = 'move_to_top_visible'
            elif data == 'y':
                cmd = 'move_to_beginning'
            elif data == 'b':
                cmd = 'move_to_end'
            elif data == 'c':
                cmd = 'toggle_toc'
            elif data == '?':
                cmd = 'toggle_ai_assistant'
            
            
            # TOC navigation is now handled at higher priority above
            
            if cmd:
                reader.loop.call_soon_threadsafe(reader._post_command_sync, cmd)
                
    except Exception:
        pass

def _kill_audio_immediately(reader):
    """Kill audio playback immediately."""
    for process in reader.playback_processes[:]:
        try:
            process.kill()
        except (ProcessLookupError, AttributeError):
            pass
    try:
        subprocess.run(['pkill', '-f', 'ffplay'], check=False, 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass