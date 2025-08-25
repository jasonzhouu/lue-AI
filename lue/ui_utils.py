"""
UI Utilities Module

This module contains common utility functions used across different UI components.
It provides terminal handling, text formatting, and other shared functionality.
"""

import shutil


def get_terminal_size():
    """
    Get terminal dimensions with fallback.

    Returns:
        tuple: (width, height) of the terminal
    """
    try:
        return shutil.get_terminal_size()
    except:
        return (80, 24)  # Fallback dimensions


def truncate_text(text, max_width, suffix="..."):
    """
    Truncate text to fit within a maximum width.

    Args:
        text (str): The text to truncate
        max_width (int): Maximum width allowed
        suffix (str): Suffix to add when truncating (default: "...")

    Returns:
        str: Truncated text with suffix if needed
    """
    if len(text) <= max_width:
        return text

    if max_width <= len(suffix):
        return suffix[:max_width]

    return text[:max_width - len(suffix)] + suffix


def center_text(text, width, fill_char=" "):
    """
    Center text within a given width.

    Args:
        text (str): Text to center
        width (int): Target width
        fill_char (str): Character to use for padding (default: space)

    Returns:
        str: Centered text
    """
    if len(text) >= width:
        return text[:width]

    padding = width - len(text)
    left_padding = padding // 2
    right_padding = padding - left_padding

    return fill_char * left_padding + text + fill_char * right_padding


def create_border_line(width, left="│", right="│", fill=" "):
    """
    Create a bordered line for UI elements.

    Args:
        width (int): Total width of the line
        left (str): Left border character
        right (str): Right border character
        fill (str): Fill character for the middle

    Returns:
        str: Bordered line
    """
    if width < 2:
        return ""

    middle_width = width - len(left) - len(right)
    middle = fill * max(0, middle_width)

    return left + middle + right


def create_separator_line(width, left="├", right="┤", fill="─"):
    """
    Create a separator line for UI elements.

    Args:
        width (int): Total width of the line
        left (str): Left border character
        right (str): Right border character
        fill (str): Fill character for the middle

    Returns:
        str: Separator line
    """
    return create_border_line(width, left, right, fill)


def wrap_text_to_lines(text, width, indent=0):
    """
    Wrap text to fit within specified width, with optional indentation.

    Args:
        text (str): Text to wrap
        width (int): Maximum width per line
        indent (int): Number of spaces to indent continuation lines

    Returns:
        list: List of wrapped text lines
    """
    if not text:
        return [""]

    words = text.split()
    lines = []
    current_line = ""
    indent_str = " " * indent

    for i, word in enumerate(words):
        # For first word or if adding word doesn't exceed width
        test_line = current_line + (" " if current_line else "") + word

        if i == 0:  # First word always goes on first line
            current_line = word
        elif len(test_line) <= width:
            current_line = test_line
        else:
            # Word doesn't fit, start new line
            if current_line:
                lines.append(current_line)
            current_line = indent_str + word

    # Add the last line if there's content
    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def format_percentage(value, decimal_places=0):
    """
    Format a percentage value for display.

    Args:
        value (float): Percentage value (0-100)
        decimal_places (int): Number of decimal places to show

    Returns:
        str: Formatted percentage string
    """
    if decimal_places == 0:
        return f"{int(value)}%"
    else:
        return f"{value:.{decimal_places}f}%"


def create_progress_bar(percentage, width, filled_char="▓", empty_char="░"):
    """
    Create a text-based progress bar.

    Args:
        percentage (float): Progress percentage (0-100)
        width (int): Width of the progress bar
        filled_char (str): Character for filled portion
        empty_char (str): Character for empty portion

    Returns:
        str: Progress bar string
    """
    if width <= 0:
        return ""

    filled_width = int((percentage / 100) * width)
    empty_width = width - filled_width

    return filled_char * filled_width + empty_char * empty_width


def calculate_padding(content_length, total_width):
    """
    Calculate padding needed to center content.

    Args:
        content_length (int): Length of the content
        total_width (int): Total available width

    Returns:
        tuple: (left_padding, right_padding)
    """
    if content_length >= total_width:
        return (0, 0)

    padding = total_width - content_length
    left_padding = padding // 2
    right_padding = padding - left_padding

    return (left_padding, right_padding)


def safe_slice_text(text, start, end=None):
    """
    Safely slice text without raising IndexError.

    Args:
        text (str): Text to slice
        start (int): Start index
        end (int, optional): End index

    Returns:
        str: Sliced text
    """
    if not text:
        return ""

    start = max(0, min(start, len(text)))

    if end is None:
        return text[start:]
    else:
        end = max(start, min(end, len(text)))
        return text[start:end]
