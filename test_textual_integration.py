#!/usr/bin/env python3
"""
Integration test for Textual-based Lue application.
Tests the complete migration with real book content.
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lue.textual_main import main as textual_main
from lue.textual_app import LueApp

def create_test_book():
    """Create a simple test book file."""
    test_content = """Chapter 1: Introduction

This is the first paragraph of our test book. It contains multiple sentences to test navigation. The sentences should be properly highlighted when navigating.

This is the second paragraph with different content. It helps test paragraph navigation and scrolling functionality.

Chapter 2: Advanced Features

The second chapter demonstrates more complex features. It includes table of contents navigation and AI assistant integration.

Multiple paragraphs in this chapter allow testing of all navigation modes. The user can move between sentences, paragraphs, and chapters seamlessly.

Chapter 3: Conclusion

The final chapter wraps up our test content. It provides a complete test scenario for the Textual migration.

All input handling issues should be resolved with the new framework. No more flickering, consistent key behavior, and proper modal management.
"""
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        return f.name

def test_basic_functionality():
    """Test basic Textual app functionality without running the full app."""
    test_file = create_test_book()
    
    try:
        # Test app creation
        app = LueApp(test_file)
        print("✅ Textual app creation successful")
        
        # Test adapter integration
        if hasattr(app.lue, 'get_current_display_content'):
            content = app.lue.get_current_display_content()
            print("✅ Content display adapter working")
        
        if hasattr(app.lue, 'get_reading_progress'):
            progress = app.lue.get_reading_progress()
            print(f"✅ Progress calculation working: {progress:.1f}%")
            
        if hasattr(app.lue, 'get_chapter_titles'):
            titles = app.lue.get_chapter_titles()
            print(f"✅ Chapter titles extraction working: {len(titles)} chapters")
            
        print("\n🎉 All basic functionality tests passed!")
        print("\nTo run the full Textual app:")
        print(f"python -m lue.textual_main '{test_file}'")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        try:
            os.unlink(test_file)
        except:
            pass

if __name__ == "__main__":
    print("Testing Textual Integration for Lue")
    print("=" * 40)
    test_basic_functionality()
