"""
UI Theme Configuration Module

This module contains all the UI styling, colors, and icons used throughout the application.
It provides a centralized way to manage themes and visual elements.
"""


class UIIcons:
    """Central place to configure all UI icons and separators."""

    # Status icons
    PLAYING = "▶"
    PAUSED = "⏸"

    # Mode icons
    AUTO_SCROLL = "⚙"
    MANUAL_MODE = "⏹"

    # Navigation icons
    HIGHLIGHT_UP = "⇈"
    HIGHLIGHT_DOWN = "⇊"
    ROW_NAVIGATION = "↑↓"
    PAGE_NAVIGATION = "↑↓"
    QUIT = "⏻"

    # Separators
    SEPARATOR = "·"

    # Progress bar
    PROGRESS_FILLED = "▓"
    PROGRESS_EMPTY = "░"

    # Line separators for different widths
    LINE_SEPARATOR_LONG = "───"
    LINE_SEPARATOR_MEDIUM = "──"
    LINE_SEPARATOR_SHORT = "─"


class UIColors:
    """Central place to configure all UI colors and styles."""

    # Status colors
    PLAYING_STATUS = "green"
    PAUSED_STATUS = "yellow"

    # Mode colors
    AUTO_SCROLL_ENABLED = "magenta"
    AUTO_SCROLL_DISABLED = "blue"

    # Control and navigation colors
    CONTROL_KEYS = "white"          # h, j, k, l, etc.
    CONTROL_ICONS = "green"         # The actual navigation icons
    ARROW_ICONS = "blue"            # Color for u/n and i/m icons
    QUIT_ICON = "red"               # Color for the q icon
    SEPARATORS = "bright_blue"      # Lines and separators

    # Panel and UI structure
    PANEL_BORDER = "bright_blue"
    PANEL_TITLE = "bold blue"

    # Text content colors
    TEXT_NORMAL = "white"           # Normal reading text
    TEXT_HIGHLIGHT = "bold magenta" # Current sentence highlight
    SELECTION_HIGHLIGHT = "reverse" # Text selection highlight
    VERSE_NUMBER = "cyan dim"       # Leading verse numbers (e.g., Bible)

    # Progress bar colors
    PROGRESS_BAR = "bold blue"      # Used for the progress text in title

    # Table of Contents colors
    TOC_TITLE = "bold cyan"
    TOC_CURRENT_CHAPTER = "bold magenta"
    TOC_NORMAL_CHAPTER = "white"
    TOC_SELECTED_CHAPTER = "black on white"
    TOC_CONTROLS = "yellow"
    TOC_BORDER = "bright_blue"

    # AI Assistant colors
    AI_TITLE = "bold green"
    AI_CONTEXT = "cyan"
    AI_USER_MESSAGE = "white"
    AI_AI_MESSAGE = "yellow"
    AI_INPUT = "white"
    AI_CONTROLS = "yellow"
    AI_BORDER = "green"
    AI_WAITING = "dim yellow"

    @classmethod
    def apply_black_theme(cls):
        """Apply a dark theme color scheme."""
        cls.PLAYING_STATUS = "black"
        cls.PAUSED_STATUS = "black"
        cls.AUTO_SCROLL_ENABLED = "black"
        cls.AUTO_SCROLL_DISABLED = "black"
        cls.CONTROL_KEYS = "black"
        cls.CONTROL_ICONS = "black"
        cls.SEPARATORS = "black"
        cls.PANEL_BORDER = "black"
        cls.PANEL_TITLE = "black"
        cls.PROGRESS_BAR = "black"
        cls.TEXT_NORMAL = "black"
        cls.TEXT_HIGHLIGHT = "white on black"
        cls.SELECTION_HIGHLIGHT = "reverse"
        cls.AI_BORDER = "black"
        cls.AI_TITLE = "white on black"
        cls.AI_CONTEXT = "black"
        cls.AI_USER_MESSAGE = "black"
        cls.AI_AI_MESSAGE = "black"
        cls.AI_WAITING = "black"
        cls.AI_INPUT = "white on black"
        cls.AI_CONTROLS = "black"
        cls.TOC_TITLE = "white on black"
        cls.TOC_CURRENT_CHAPTER = "white on black"
        cls.TOC_NORMAL_CHAPTER = "black"
        cls.TOC_SELECTED_CHAPTER = "white on black"
        cls.TOC_CONTROLS = "black"
        cls.TOC_BORDER = "black"

    @classmethod
    def apply_white_theme(cls):
        """Apply a light theme color scheme."""
        cls.PLAYING_STATUS = "white"
        cls.PAUSED_STATUS = "white"
        cls.AUTO_SCROLL_ENABLED = "white"
        cls.AUTO_SCROLL_DISABLED = "white"
        cls.CONTROL_KEYS = "white"
        cls.CONTROL_ICONS = "white"
        cls.SEPARATORS = "white"
        cls.PANEL_BORDER = "white"
        cls.PANEL_TITLE = "white"
        cls.PROGRESS_BAR = "white"
        cls.TEXT_NORMAL = "white"
        cls.TEXT_HIGHLIGHT = "bold white"
        cls.SELECTION_HIGHLIGHT = "reverse"
        cls.AI_BORDER = "white"
        cls.AI_TITLE = "bold white"
        cls.AI_CONTEXT = "white"
        cls.AI_USER_MESSAGE = "white"
        cls.AI_AI_MESSAGE = "white"
        cls.AI_WAITING = "white"
        cls.AI_INPUT = "bold white"
        cls.AI_CONTROLS = "white"
        cls.TOC_TITLE = "bold white"
        cls.TOC_CURRENT_CHAPTER = "bold white"
        cls.TOC_NORMAL_CHAPTER = "white"
        cls.TOC_SELECTED_CHAPTER = "black on white"
        cls.TOC_CONTROLS = "white"
        cls.TOC_BORDER = "white"


# Create global instances for easy access
ICONS = UIIcons()
COLORS = UIColors()

# Uncomment one of these to apply a different theme:
# COLORS.apply_black_theme()
# COLORS.apply_white_theme()
