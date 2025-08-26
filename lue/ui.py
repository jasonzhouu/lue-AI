import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from . import content_parser
from .ui_theme import ICONS, COLORS
import re
from .ui_utils import get_terminal_size, create_progress_bar, truncate_text


def _process_verse_markers(text):
    """Process verse number markers and apply appropriate styling"""
    styled_text = Text()
    
    # Split text by verse markers
    parts = re.split(r'(__VERSE__\d+__/VERSE__)', text)
    
    for part in parts:
        if re.match(r'__VERSE__\d+__/VERSE__', part):
            # Extract verse number
            verse_num = re.search(r'__VERSE__(\d+)__/VERSE__', part).group(1)
            # Style verse number with cyan dim (small and less prominent)
            styled_text.append(verse_num, style="cyan dim")
            styled_text.append(" ")  # Add space after verse number
        else:
            # Regular text
            styled_text.append(part, style=COLORS.TEXT_NORMAL)
    
    return styled_text


def update_document_layout(reader):
    """Update the document layout based on terminal size."""
    reader.document_lines = []
    reader.line_to_position = {}
    reader.position_to_line = {}
    reader.paragraph_line_ranges = {}

    width, _ = get_terminal_size()
    available_width = max(20, width - 10)

    for chap_idx, chapter in enumerate(reader.chapters):
        if chap_idx > 0:
            reader.document_lines.append(Text("", style=COLORS.TEXT_NORMAL))

        for para_idx, paragraph in enumerate(chapter):
            paragraph_start_line = len(reader.document_lines)

            # Create text with proper paragraph flow (sentences together)
            # Handle verse number markers for display
            styled_text = _process_verse_markers(paragraph)
            wrapped_lines = styled_text.wrap(reader.console, available_width)
            paragraph_end_line = len(reader.document_lines) + len(wrapped_lines) - 1

            reader.paragraph_line_ranges[(chap_idx, para_idx)] = (paragraph_start_line, paragraph_end_line)

            # Map sentences to their positions within the wrapped text
            sentences = content_parser.split_into_sentences(paragraph)
            current_char_pos = 0
            
            for sent_idx, sentence in enumerate(sentences):
                sentence_start = current_char_pos
                sentence_end = current_char_pos + len(sentence)

                # Find which wrapped line contains the start of this sentence
                accumulated_chars = 0
                for line_idx, line in enumerate(wrapped_lines):
                    line_start = accumulated_chars
                    line_end = accumulated_chars + len(line.plain)

                    # Check if sentence starts within this line
                    if line_start <= sentence_start < line_end:
                        global_line_idx = paragraph_start_line + line_idx
                        reader.position_to_line[(chap_idx, para_idx, sent_idx)] = global_line_idx
                        break

                    accumulated_chars = line_end
                    # Account for space between wrapped lines
                    if line_idx < len(wrapped_lines) - 1:
                        accumulated_chars += 1

                # Move to next sentence (add space between sentences)
                current_char_pos = sentence_end
                if sent_idx < len(sentences) - 1:
                    current_char_pos += 1

            # Map each line back to paragraph position
            for line_idx in range(len(wrapped_lines)):
                global_line_idx = paragraph_start_line + line_idx
                reader.line_to_position[global_line_idx] = (chap_idx, para_idx, 0)

            reader.document_lines.extend(wrapped_lines)

            if para_idx < len(chapter) - 1:
                reader.document_lines.append(Text("", style=COLORS.TEXT_NORMAL))

    if hasattr(reader, '_initial_load_complete') and reader._initial_load_complete:
        scroll_was_set = False
        if not reader.auto_scroll_enabled and reader.resize_anchor:
            anchor_pos = reader.resize_anchor
            if anchor_pos and anchor_pos in reader.position_to_line:
                target_line = reader.position_to_line[anchor_pos]
                _, height = get_terminal_size()
                available_height = max(1, height - 4)
                max_scroll = max(0, len(reader.document_lines) - available_height)
                reader.scroll_offset = reader.target_scroll_offset = min(target_line, max_scroll)
                scroll_was_set = True
            reader.resize_anchor = None

        if not scroll_was_set:
            current_position_key = (reader.ui_chapter_idx, reader.ui_paragraph_idx, reader.ui_sentence_idx)
            reader._scroll_to_position(
                current_position_key[0],
                current_position_key[1],
                current_position_key[2],
                smooth=False
            )


def _apply_current_text_color(line):
    """Apply the current theme's text color to a line."""
    if not line.plain:
        return Text("", style=COLORS.TEXT_NORMAL)

    # Create a new Text object with current theme color
    new_line = Text(line.plain, justify="left", no_wrap=False, style=COLORS.TEXT_NORMAL)
    return new_line


def _apply_verse_number_styling(line: Text) -> Text:
    """If a line starts with a verse-like number (e.g., "1 ", "23.", "7)") color it with VERSE_NUMBER.
    This is a non-destructive overlay on existing styles.
    """
    if not line or not line.plain:
        return line

    # Match leading verse markers: optional spaces, digits (1-3), optional ")" or ".", then space if punctuation absent
    # Examples matched: "1 ", "12 ", "3.", "45)", "7:1 " (be conservative and only take the first number part)
    m = re.match(r"^\s*(\d{1,3})([).:]?)\s?", line.plain)
    if not m:
        return line

    start = 0
    end = m.end()
    # Apply style to the matched range
    try:
        line.stylize(COLORS.VERSE_NUMBER, start, end)
    except Exception:
        # Fallback: rebuild minimal styled text if stylize fails
        prefix = line.plain[:end]
        suffix = line.plain[end:]
        new_line = Text(justify="left", no_wrap=False)
        new_line.append(prefix, style=COLORS.VERSE_NUMBER)
        new_line.append(suffix, style=COLORS.TEXT_NORMAL)
        return new_line
    return line

def get_visible_content(reader):
    """Get the visible content to display."""
    width, height = get_terminal_size()
    available_height = max(1, height - 4)
    available_width = max(20, width - 10)

    start_line = int(reader.scroll_offset)
    end_line = min(len(reader.document_lines), start_line + available_height)

    visible_lines = []
    current_paragraph_key = (reader.ui_chapter_idx, reader.ui_paragraph_idx)

    highlighted_paragraph_lines = None
    if current_paragraph_key in reader.paragraph_line_ranges:
        para_start, para_end = reader.paragraph_line_ranges[current_paragraph_key]
        paragraph = reader.chapters[reader.ui_chapter_idx][reader.ui_paragraph_idx]
        sentences = content_parser.split_into_sentences(paragraph)
        highlighted_text = Text(justify="left", no_wrap=False)

        for sent_idx, sentence in enumerate(sentences):
            style = COLORS.TEXT_HIGHLIGHT if sent_idx == reader.ui_sentence_idx else COLORS.TEXT_NORMAL
            highlighted_text.append(sentence, style=style)
            if sent_idx < len(sentences) - 1:
                highlighted_text.append(" ", style=COLORS.TEXT_NORMAL)

        highlighted_paragraph_lines = highlighted_text.wrap(reader.console, available_width)

    for i in range(start_line, end_line):
        if i < len(reader.document_lines):
            line = reader.document_lines[i]

            # Apply current theme text color
            line = _apply_current_text_color(line)

            if (i in reader.line_to_position and
                reader.line_to_position[i][:2] == current_paragraph_key and
                highlighted_paragraph_lines is not None):

                para_start, para_end = reader.paragraph_line_ranges[current_paragraph_key]
                line_offset = i - para_start

                if 0 <= line_offset < len(highlighted_paragraph_lines):
                    line = highlighted_paragraph_lines[line_offset]

            line = _apply_selection_highlighting(reader, line, i)
            # Apply verse number styling last so it overlays other styles but before append
            line = _apply_verse_number_styling(line)

            visible_lines.append(line)
        else:
            visible_lines.append(Text("", style=COLORS.TEXT_NORMAL))

    if len(visible_lines) > available_height:
        visible_lines = visible_lines[:available_height]

    return visible_lines

def _apply_selection_highlighting(reader, line, line_index):
    """Apply selection highlighting to a line if it's within the selection range."""
    if not reader.selection_active or not reader.selection_start or not reader.selection_end:
        return line

    start_line, start_char = reader.selection_start
    end_line, end_char = reader.selection_end

    # Ensure start comes before end
    if start_line > end_line or (start_line == end_line and start_char > end_char):
        start_line, start_char, end_line, end_char = end_line, end_char, start_line, start_char

    # Check if this line is within the selection range
    if not (start_line <= line_index <= end_line):
        return line

    line_text = line.plain
    if not line_text:
        return line

    # Create a new Text object with selection highlighting
    new_line = Text(justify="left", no_wrap=False)

    if start_line == end_line == line_index:
        # Single line selection
        selection_start = max(0, min(start_char, len(line_text)))
        selection_end = max(0, min(end_char, len(line_text)))

        # Add text before selection
        if selection_start > 0:
            new_line.append(line_text[:selection_start], style=COLORS.TEXT_NORMAL)

        # Add selected text with highlighting
        if selection_end > selection_start:
            new_line.append(line_text[selection_start:selection_end], style=COLORS.SELECTION_HIGHLIGHT)

        # Add text after selection
        if selection_end < len(line_text):
            new_line.append(line_text[selection_end:], style=COLORS.TEXT_NORMAL)

    elif line_index == start_line:
        # First line of multi-line selection
        selection_start = max(0, min(start_char, len(line_text)))

        # Add text before selection
        if selection_start > 0:
            new_line.append(line_text[:selection_start], style=COLORS.TEXT_NORMAL)

        # Add selected text from start_char to end of line
        if selection_start < len(line_text):
            new_line.append(line_text[selection_start:], style=COLORS.SELECTION_HIGHLIGHT)

    elif line_index == end_line:
        # Last line of multi-line selection
        selection_end = max(0, min(end_char, len(line_text)))

        # Add selected text from beginning to end_char
        if selection_end > 0:
            new_line.append(line_text[:selection_end], style=COLORS.SELECTION_HIGHLIGHT)

        # Add text after selection
        if selection_end < len(line_text):
            new_line.append(line_text[selection_end:], style=COLORS.TEXT_NORMAL)

    else:
        # Middle line of multi-line selection - entire line is selected
        new_line.append(line_text, style=COLORS.SELECTION_HIGHLIGHT)

    return new_line


def get_compact_subtitle(reader, width):
    """Generate a compact subtitle based on terminal width."""
    status_icon = ICONS.PLAYING if not reader.is_paused else ICONS.PAUSED
    status_text = "PLAYING" if not reader.is_paused else "PAUSED"

    if reader.auto_scroll_enabled:
        auto_scroll_icon = ICONS.AUTO_SCROLL
        auto_scroll_text = "AUTO"
    else:
        auto_scroll_icon = ICONS.MANUAL_MODE
        auto_scroll_text = "MANUAL"

    # Control text with centralized colors
    nav_text_1 = f"[{COLORS.CONTROL_KEYS}]h{ICONS.SEPARATOR}j[/{COLORS.CONTROL_KEYS}]"
    nav_text_2 = f"[{COLORS.CONTROL_KEYS}]k{ICONS.SEPARATOR}l[/{COLORS.CONTROL_KEYS}]"
    page_text = f"[{COLORS.CONTROL_KEYS}]u{ICONS.SEPARATOR}n[/{COLORS.CONTROL_KEYS}]"
    scroll_text = f"[{COLORS.CONTROL_KEYS}]i{ICONS.SEPARATOR}m[/{COLORS.CONTROL_KEYS}]"
    quit_text = f"[{COLORS.CONTROL_KEYS}]q[/{COLORS.CONTROL_KEYS}]"
    auto_text = f"[{COLORS.CONTROL_KEYS}]a{ICONS.SEPARATOR}t[/{COLORS.CONTROL_KEYS}]"
    toc_text = f"[{COLORS.CONTROL_KEYS}]c[/{COLORS.CONTROL_KEYS}]"
    ai_text = f"[{COLORS.CONTROL_KEYS}]?[/{COLORS.CONTROL_KEYS}]"

    if width >= 80:
        base_sep = ICONS.LINE_SEPARATOR_LONG

        status_part = f"[{COLORS.CONTROL_KEYS}]p[/{COLORS.CONTROL_KEYS}] {status_icon} {status_text}"
        status_extra = 1 if status_text == "PAUSED" else 0
        status_sep = base_sep + (ICONS.LINE_SEPARATOR_SHORT * status_extra)

        auto_part = f"{auto_scroll_icon} {auto_scroll_text}"
        auto_extra = 2 if auto_scroll_text == "AUTO" else 0
        auto_sep = base_sep + (ICONS.LINE_SEPARATOR_SHORT * auto_extra)

        controls_text = f"{nav_text_1} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_UP}[/{COLORS.CONTROL_ICONS}] {nav_text_2} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_DOWN}[/{COLORS.CONTROL_ICONS}] [{COLORS.SEPARATORS}]{base_sep}[/{COLORS.SEPARATORS}] {page_text} [{COLORS.ARROW_ICONS}]{ICONS.ROW_NAVIGATION}[/{COLORS.ARROW_ICONS}] {scroll_text} [{COLORS.ARROW_ICONS}]{ICONS.PAGE_NAVIGATION}[/{COLORS.ARROW_ICONS}] [{COLORS.SEPARATORS}]{base_sep}[/{COLORS.SEPARATORS}] {toc_text} TOC {ai_text} AI [{COLORS.SEPARATORS}]{base_sep}[/{COLORS.SEPARATORS}] {quit_text} [{COLORS.QUIT_ICON}]{ICONS.QUIT}[/{COLORS.QUIT_ICON}]"

        playing_color = COLORS.PLAYING_STATUS if not reader.is_paused else COLORS.PAUSED_STATUS
        auto_color = COLORS.AUTO_SCROLL_ENABLED if reader.auto_scroll_enabled else COLORS.AUTO_SCROLL_DISABLED

        return (
            f"[{playing_color}]{status_part}[/{playing_color}] "
            f"[{COLORS.SEPARATORS}]{status_sep}[/{COLORS.SEPARATORS}] "
            f"{auto_text} "
            f"[{auto_color}]{auto_part}[/{auto_color}] "
            f"[{COLORS.SEPARATORS}]{auto_sep}[/{COLORS.SEPARATORS}] "
            f"{controls_text}"
        )
    elif width >= 70:
        separator = ICONS.LINE_SEPARATOR_LONG
        icon_status = f"[{COLORS.CONTROL_KEYS}]p[/{COLORS.CONTROL_KEYS}] {status_icon}"
        icon_auto = f"{auto_scroll_icon}"
        controls_text = f"[{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {nav_text_1} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_UP}[/{COLORS.CONTROL_ICONS}] {nav_text_2} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_DOWN}[/{COLORS.CONTROL_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {page_text} [{COLORS.ARROW_ICONS}]{ICONS.ROW_NAVIGATION}[/{COLORS.ARROW_ICONS}] {scroll_text} [{COLORS.ARROW_ICONS}]{ICONS.PAGE_NAVIGATION}[/{COLORS.ARROW_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {toc_text} TOC {ai_text} AI [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {quit_text} [{COLORS.QUIT_ICON}]{ICONS.QUIT}[/{COLORS.QUIT_ICON}]"

        playing_color = COLORS.PLAYING_STATUS if not reader.is_paused else COLORS.PAUSED_STATUS
        auto_color = COLORS.AUTO_SCROLL_ENABLED if reader.auto_scroll_enabled else COLORS.AUTO_SCROLL_DISABLED

        return f"[{playing_color}]{icon_status}[/{playing_color}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {auto_text} [{auto_color}]{icon_auto}[/{auto_color}] {controls_text}"
    elif width >= 65:
        separator = ICONS.LINE_SEPARATOR_MEDIUM
        icon_status = f"[{COLORS.CONTROL_KEYS}]p[/{COLORS.CONTROL_KEYS}] {status_icon}"
        icon_auto = f"{auto_scroll_icon}"
        controls_text = f"[{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {nav_text_1} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_UP}[/{COLORS.CONTROL_ICONS}] {nav_text_2} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_DOWN}[/{COLORS.CONTROL_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {page_text} [{COLORS.ARROW_ICONS}]{ICONS.ROW_NAVIGATION}[/{COLORS.ARROW_ICONS}] {scroll_text} [{COLORS.ARROW_ICONS}]{ICONS.PAGE_NAVIGATION}[/{COLORS.ARROW_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {toc_text} TOC {ai_text} AI [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {quit_text} [{COLORS.QUIT_ICON}]{ICONS.QUIT}[/{COLORS.QUIT_ICON}]"

        playing_color = COLORS.PLAYING_STATUS if not reader.is_paused else COLORS.PAUSED_STATUS
        auto_color = COLORS.AUTO_SCROLL_ENABLED if reader.auto_scroll_enabled else COLORS.AUTO_SCROLL_DISABLED

        return f"[{playing_color}]{icon_status}[/{playing_color}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {auto_text} [{auto_color}]{icon_auto}[/{auto_color}] {controls_text}"
    else:
        separator = ICONS.LINE_SEPARATOR_SHORT
        icon_status = f"[{COLORS.CONTROL_KEYS}]p[/{COLORS.CONTROL_KEYS}] {status_icon}"
        icon_auto = f"{auto_scroll_icon}"
        controls_text = f"[{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {nav_text_1} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_UP}[/{COLORS.CONTROL_ICONS}] {nav_text_2} [{COLORS.CONTROL_ICONS}]{ICONS.HIGHLIGHT_DOWN}[/{COLORS.CONTROL_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {page_text} [{COLORS.ARROW_ICONS}]{ICONS.ROW_NAVIGATION}[/{COLORS.ARROW_ICONS}] {scroll_text} [{COLORS.ARROW_ICONS}]{ICONS.PAGE_NAVIGATION}[/{COLORS.ARROW_ICONS}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {toc_text} TOC {ai_text} AI [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {quit_text} [{COLORS.QUIT_ICON}]{ICONS.QUIT}[/{COLORS.QUIT_ICON}]"

        playing_color = COLORS.PLAYING_STATUS if not reader.is_paused else COLORS.PAUSED_STATUS
        auto_color = COLORS.AUTO_SCROLL_ENABLED if reader.auto_scroll_enabled else COLORS.AUTO_SCROLL_DISABLED

        return f"[{playing_color}]{icon_status}[/{playing_color}] [{COLORS.SEPARATORS}]{separator}[/{COLORS.SEPARATORS}] {auto_text} [{auto_color}]{icon_auto}[/{auto_color}] {controls_text}"

async def display_ui(reader):
    """Display the UI."""
    if reader.render_lock.locked():
        return

    async with reader.render_lock:
        try:
            width, height = get_terminal_size()

            progress_percent = reader._calculate_ui_progress_percentage()
            rounded_scroll = round(reader.scroll_offset, 1)
            current_state = (
                reader.ui_chapter_idx, reader.ui_paragraph_idx, reader.ui_sentence_idx,
                rounded_scroll, reader.is_paused, int(progress_percent),
                width, height, reader.auto_scroll_enabled, reader.selection_active,
                reader.selection_start, reader.selection_end
            )

            if reader.last_rendered_state == current_state and reader.last_terminal_size == (width, height):
                return

            reader.last_rendered_state = current_state
            reader.last_terminal_size = (width, height)

            visible_lines = get_visible_content(reader)
            book_content = Text("")
            for i, line in enumerate(visible_lines):
                book_content.append(line)
                if i < len(visible_lines) - 1:
                    book_content.append("\n")

            progress_bar_width = 10
            progress_bar = create_progress_bar(progress_percent, progress_bar_width,
                                              ICONS.PROGRESS_FILLED, ICONS.PROGRESS_EMPTY)

            percentage_text = f"{int(progress_percent)}% {progress_bar}"

            available_width = width - len(percentage_text) - 6

            title_text = truncate_text(reader.book_title, available_width)

            used_space = len(title_text) + len(percentage_text) + 2
            remaining_space = width - used_space - 6
            connecting_line = ICONS.LINE_SEPARATOR_SHORT * max(0, remaining_space)

            progress_text = f"{title_text} {connecting_line} {percentage_text}"

            sys.stdout.write('\033[?25l\033[2J\033[H')

            temp_console = Console(width=width, height=height, force_terminal=True)

            subtitle = get_compact_subtitle(reader, width)

            book_panel = Panel(
                book_content,
                title=f"[{COLORS.PANEL_TITLE}]{progress_text}[/{COLORS.PANEL_TITLE}]",
                subtitle=subtitle,
                border_style=COLORS.PANEL_BORDER,
                padding=(1, 4),
                title_align="center",
                subtitle_align="center",
                width=width,
                height=height,
                expand=False
            )

            with temp_console.capture() as capture:
                temp_console.print(book_panel, end='', overflow='crop')

            output = capture.get()
            output_lines = output.split('\n')
            if len(output_lines) > height:
                output_lines = output_lines[:height]
                output = '\n'.join(output_lines)

            sys.stdout.write(output)
            sys.stdout.flush()

        except (IndexError, ValueError):
            pass




