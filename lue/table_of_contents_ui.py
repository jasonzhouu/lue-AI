"""
Table of Contents UI Module

This module handles the rendering and display of the table of contents interface.
It provides a full-screen overlay for navigating between chapters.
"""

from rich.console import Console
from rich.text import Text
from .ui_theme import COLORS
from .ui_utils import get_terminal_size, truncate_text, create_border_line, create_separator_line
from . import content_parser


def render_table_of_contents(reader, selected_chapter_idx=0):
    """
    Render a full-screen table of contents overlay.

    Args:
        reader: The reader instance containing chapters and current position
        selected_chapter_idx: The currently selected chapter index in the TOC
    """
    try:
        width, height = get_terminal_size()
        console = Console()

        # Extract chapter titles
        chapter_titles = content_parser.extract_chapter_titles(reader.chapters)

        # Clear screen
        console.clear()

        # Create title
        title = "TABLE OF CONTENTS"

        # Print title with borders
        border_line = "┌" + "─" * (width - 2) + "┐"
        title_line = "│" + title.center(width - 2) + "│"
        separator_line = create_separator_line(width)

        console.print(Text(border_line, style=COLORS.TOC_BORDER))
        console.print(Text(title_line, style=f"{COLORS.TOC_BORDER} {COLORS.TOC_TITLE}"))
        console.print(Text(separator_line, style=COLORS.TOC_BORDER))

        # Calculate available space for chapters
        available_height = height - 8  # Reserve space for title, controls, and borders
        start_idx = max(0, selected_chapter_idx - available_height // 2)
        end_idx = min(len(chapter_titles), start_idx + available_height)

        # Adjust start_idx if we're near the end
        if end_idx - start_idx < available_height and len(chapter_titles) > available_height:
            start_idx = max(0, end_idx - available_height)

        # Print empty lines to center content
        empty_lines = (available_height - (end_idx - start_idx)) // 2
        for _ in range(empty_lines):
            empty_line = create_border_line(width)
            console.print(Text(empty_line, style=COLORS.TOC_BORDER))

        # Print chapters
        for i in range(start_idx, end_idx):
            chapter_idx, title = chapter_titles[i]

            # Truncate title if too long
            max_title_width = width - 10  # Reserve space for borders and indicators
            title = truncate_text(title, max_title_width)

            # Determine styling
            if i == selected_chapter_idx:
                # Selected chapter
                indicator = "▶ "
                style = COLORS.TOC_SELECTED_CHAPTER
            elif chapter_idx == reader.chapter_idx:
                # Current reading chapter
                indicator = "● "
                style = COLORS.TOC_CURRENT_CHAPTER
            else:
                # Normal chapter
                indicator = "  "
                style = COLORS.TOC_NORMAL_CHAPTER

            chapter_text = f"{indicator}{title}"
            padding = width - 2 - len(chapter_text)
            full_line = "│" + chapter_text + " " * padding + "│"

            console.print(Text(full_line, style=style))

        # Fill remaining space
        remaining_lines = available_height - (end_idx - start_idx) - empty_lines
        for _ in range(remaining_lines):
            empty_line = create_border_line(width)
            console.print(Text(empty_line, style=COLORS.TOC_BORDER))

        # Print controls
        separator_line = create_separator_line(width)
        console.print(Text(separator_line, style=COLORS.TOC_BORDER))

        controls = "[↑↓] Navigate   [Enter] Jump to Chapter   [Esc/c] Close   [q] Quit"
        controls_padding = (width - 2 - len(controls)) // 2
        controls_line = "│" + " " * controls_padding + controls + " " * (width - 2 - len(controls) - controls_padding) + "│"
        console.print(Text(controls_line, style=COLORS.TOC_CONTROLS))

        # Current position info
        current_info = f"Current: {chapter_titles[reader.chapter_idx][1]} (Chapter {reader.chapter_idx + 1}/{len(chapter_titles)})"
        current_info = truncate_text(current_info, width - 4)
        info_padding = (width - 2 - len(current_info)) // 2
        info_line = "│" + " " * info_padding + current_info + " " * (width - 2 - len(current_info) - info_padding) + "│"
        console.print(Text(info_line, style="white"))

        separator_line = create_separator_line(width)
        console.print(Text(separator_line, style=COLORS.TOC_BORDER))

        help_text = "Press any key to return to reading"
        help_padding = (width - 2 - len(help_text)) // 2
        help_line = "│" + " " * help_padding + help_text + " " * (width - 2 - len(help_text) - help_padding) + "│"
        console.print(Text(help_line, style="dim"))

        bottom_line = "└" + "─" * (width - 2) + "┘"
        console.print(Text(bottom_line, style=COLORS.TOC_BORDER))

    except Exception as e:
        # Fallback to simple display
        console = Console()
        console.clear()
        console.print(f"\nTable of Contents (Error in rendering: {e})", style="red")
        console.print("─" * 50)
        chapter_titles = content_parser.extract_chapter_titles(reader.chapters)
        for i, (chapter_idx, title) in enumerate(chapter_titles):
            marker = "▶ " if i == selected_chapter_idx else "  "
            style = "bold magenta" if i == selected_chapter_idx else "white"
            console.print(f"{marker}{title}", style=style)
        console.print("─" * 50)
        console.print("Use ↑↓ to navigate, Enter to jump, Esc to close", style="yellow")


def get_chapter_navigation_info(reader, selected_idx, chapter_titles):
    """
    Get navigation information for the table of contents.

    Args:
        reader: The reader instance
        selected_idx: Currently selected chapter index
        chapter_titles: List of (chapter_idx, title) tuples

    Returns:
        dict: Navigation information including current position, total chapters, etc.
    """
    total_chapters = len(chapter_titles)
    current_chapter_idx = reader.chapter_idx if hasattr(reader, 'chapter_idx') else 0

    # Find the display name for current chapter
    current_chapter_title = ""
    for idx, title in chapter_titles:
        if idx == current_chapter_idx:
            current_chapter_title = title
            break

    return {
        'total_chapters': total_chapters,
        'current_chapter_idx': current_chapter_idx,
        'current_chapter_title': current_chapter_title,
        'selected_idx': selected_idx,
        'selected_title': chapter_titles[selected_idx][1] if selected_idx < len(chapter_titles) else ""
    }
