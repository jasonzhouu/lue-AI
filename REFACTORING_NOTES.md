# UI Refactoring Documentation

## Overview

The `ui.py` file has been refactored to improve code organization, maintainability, and scalability. Previously, all UI-related functionality was contained in a single large file, making it difficult to manage and extend.

## Changes Made

### 1. New Modular Structure

The UI functionality has been split into four specialized modules:

#### `ui_theme.py`
- **Purpose**: Centralized theme and styling configuration
- **Contents**:
  - `UIIcons` class: All UI icons and separators
  - `UIColors` class: All color definitions and theme methods
  - Theme switching methods (`apply_black_theme()`, `apply_white_theme()`)
  - Global instances `ICONS` and `COLORS`

#### `ui_utils.py`
- **Purpose**: Common utility functions used across UI components
- **Contents**:
  - `get_terminal_size()`: Terminal dimension detection with fallback
  - `truncate_text()`: Safe text truncation with suffix
  - `center_text()`: Text centering within given width
  - `create_border_line()`: UI border creation
  - `create_separator_line()`: UI separator creation
  - `wrap_text_to_lines()`: Text wrapping with indentation support
  - `create_progress_bar()`: Text-based progress bar generation
  - Various padding and formatting utilities

#### `ai_assistant_ui.py`
- **Purpose**: AI assistant interface rendering
- **Contents**:
  - `render_ai_assistant()`: Full-screen AI assistant overlay
  - `get_current_context()`: Extract current reading context
  - `format_conversation_message()`: Message formatting with word wrapping
  - Uses utilities from `ui_utils.py` for consistent behavior

#### `table_of_contents_ui.py`
- **Purpose**: Table of contents interface rendering
- **Contents**:
  - `render_table_of_contents()`: Full-screen TOC overlay
  - `get_chapter_navigation_info()`: Navigation information extraction
  - Uses utilities from `ui_utils.py` for consistent behavior

### 2. Updated `ui.py`

The main `ui.py` file has been significantly simplified:
- Removed ~220 lines of duplicated theme/icon definitions
- Removed ~220 lines of AI assistant rendering logic
- Removed ~120 lines of table of contents rendering logic
- Now imports functionality from the specialized modules
- Maintains the same public API for backward compatibility

## Benefits

### 1. **Better Code Organization**
- Each module has a clear, single responsibility
- Related functionality is grouped together
- Easier to locate and modify specific features

### 2. **Reduced Code Duplication**
- Common utilities are centralized in `ui_utils.py`
- No duplicate `get_terminal_size()` functions
- Consistent text handling across all components

### 3. **Improved Maintainability**
- Theme changes only require editing `ui_theme.py`
- AI assistant improvements only require editing `ai_assistant_ui.py`
- TOC improvements only require editing `table_of_contents_ui.py`
- Bug fixes in utilities automatically benefit all components

### 4. **Enhanced Scalability**
- Easy to add new UI components without bloating main file
- Theme system can be extended with new themes
- Utility functions can be reused for new components

### 5. **Better Testing**
- Each module can be tested independently
- Utilities can be unit tested separately
- UI components can be tested in isolation

## Migration Notes

### For Developers
- All existing imports from `ui.py` continue to work
- `render_ai_assistant()` and `render_table_of_contents()` are still available from `ui.py`
- `ICONS` and `COLORS` are now imported from `ui_theme.py` but still accessible

### For Theme Customization
- Edit `ui_theme.py` to modify colors and icons
- Use `COLORS.apply_black_theme()` or `COLORS.apply_white_theme()` for preset themes
- Add new theme methods to `UIColors` class as needed

### For New Features
- Add new UI utilities to `ui_utils.py` if they're reusable
- Create new specialized modules for major UI components
- Import utilities and themes from their respective modules

## File Structure

```
lue/lue/
├── ui.py                    # Main UI module (simplified)
├── ui_theme.py             # Theme and styling configuration
├── ui_utils.py             # Common utility functions
├── ai_assistant_ui.py      # AI assistant interface
├── table_of_contents_ui.py # Table of contents interface
└── ...
```

## Backward Compatibility

All public functions and classes remain available from their original locations:
- `from lue.ui import render_ai_assistant, render_table_of_contents` still works
- Global `ICONS` and `COLORS` are still accessible from `ui.py`
- No changes required to existing code that imports from `ui.py`

## Bug Fixes

During the refactoring process, a critical bug was identified and fixed:

### Terminal Size Type Error
- **Problem**: `'<=' not supported between instances of 'int' and 'tuple'`
- **Root Cause**: The `get_terminal_size()` function was returning `os.terminal_size` objects instead of proper tuples
- **Impact**: Code in `reader.py` that used indexing like `get_terminal_size()[1]` was failing
- **Solution**: Modified both `ui.py` and `ui_utils.py` to return proper tuples `(width, height)` instead of `os.terminal_size` objects

### Code Changes Made
```python
# Before (broken):
def get_terminal_size():
    return shutil.get_terminal_size()  # Returns os.terminal_size object

# After (fixed):
def get_terminal_size():
    terminal_size = shutil.get_terminal_size()
    return (terminal_size.columns, terminal_size.lines)  # Returns tuple
```

This fix ensures that code like `ui.get_terminal_size()[1] - 4` works correctly throughout the application.

## Future Improvements

This refactoring sets the foundation for:
1. **Plugin System**: Easy to add new UI overlays as separate modules
2. **Theme Marketplace**: External theme files that modify `ui_theme.py`
3. **Component Library**: Reusable UI components using `ui_utils.py`
4. **Configuration System**: Runtime theme switching and customization
5. **Testing Framework**: Comprehensive UI testing with isolated components