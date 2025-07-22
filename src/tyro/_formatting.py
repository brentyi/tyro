"""Lightweight formatting module for tyro's CLI help text.

This module provides a minimal, zero-dependency alternative to rich for
formatting CLI help text. It's optimized specifically for tyro's needs:
- Two-column tables for options/descriptions
- Multi-column layouts for option lists
- Simple ANSI color support
- Structured error messages with suggestions
"""

import io
import re
import shutil
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Any, TextIO, Generator


# ANSI color codes
COLORS = {
    # Basic colors (30-37)
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    # Bright colors (90-97)
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
}

# ANSI attribute codes
ATTRIBUTES = {
    "bold": 1,
    "dim": 2,
}


@dataclass(frozen=True)
class Style:
    """A simple terminal style focused on CLI needs.
    
    Unlike rich, we only support the subset of styling that makes sense
    for CLI help text: basic colors and bold/dim.
    """
    color: Optional[str] = None
    bold: bool = False
    dim: bool = False
    
    def to_ansi(self) -> str:
        """Convert style to ANSI escape codes.
        
        Returns empty string if no styling is applied.
        """
        codes = []
        
        if self.color and self.color in COLORS:
            codes.append(str(COLORS[self.color]))
        
        if self.bold:
            codes.append(str(ATTRIBUTES["bold"]))
            
        if self.dim:
            codes.append(str(ATTRIBUTES["dim"]))
        
        if codes:
            return f"\033[{';'.join(codes)}m"
        return ""
    
    def render(self, text: str) -> str:
        """Apply style to text and reset at the end.
        
        Example:
            Style(color='red', bold=True).render('Error!')
            # Returns: '\033[31;1mError!\033[0m'
        """
        # Check if rich formatting is enabled
        try:
            from . import _arguments
            if not _arguments.USE_RICH:
                return text
        except ImportError:
            pass
        
        if not self.color and not self.bold and not self.dim:
            return text
        
        return f"{self.to_ansi()}{text}\033[0m"


@dataclass(frozen=True)
class TyroTheme:
    """Theme specifically for tyro's help formatting needs.
    
    Each field corresponds to a specific element in the help output.
    """
    border: Style = Style()
    description: Style = Style()
    invocation: Style = Style()
    metavar: Style = Style()
    metavar_fixed: Style = Style()
    helptext: Style = Style()
    helptext_required: Style = Style()
    helptext_default: Style = Style()
    
    def as_rich_theme(self) -> Dict[str, Style]:
        """Convert to dict format compatible with rich Theme."""
        return {
            "border": self.border,
            "description": self.description,
            "invocation": self.invocation,
            "metavar": self.metavar,
            "metavar_fixed": self.metavar_fixed,
            "helptext": self.helptext,
            "helptext_required": self.helptext_required,
            "helptext_default": self.helptext_default,
        }


class Text:
    """Lightweight text with style support.
    
    Much simpler than rich.text.Text - focused on what CLIs need.
    This class maintains styling through operations like wrapping and padding.
    """
    def __init__(self, content: str, style: Optional[Style] = None):
        self.content = content
        self.style = style
        # For complex markup, store segments
        self._segments: Optional[List[Tuple[str, Optional[Style]]]] = None
    
    @property
    def plain(self) -> str:
        """Get plain text without any styling."""
        if self._segments:
            return ''.join(text for text, _ in self._segments)
        return self.content
    
    @property
    def visual_length(self) -> int:
        """Get visual length of text (without ANSI codes)."""
        return len(self.plain)
    
    def wrap(self, width: int) -> List["Text"]:
        """Wrap text to specified width, returning list of Text objects.
        
        Each line maintains the original styling.
        """
        plain_text = self.plain
        if not plain_text or width <= 0:
            return [self]
        
        # Check if text fits without wrapping
        if self.visual_length <= width:
            return [self]
        
        # For simple styled text
        if not self._segments:
            words = plain_text.split()
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_len = len(word)
                
                if current_line and current_length + 1 + word_len > width:
                    lines.append(Text(' '.join(current_line), self.style))
                    current_line = [word]
                    current_length = word_len
                else:
                    if current_line:
                        current_length += 1
                    current_line.append(word)
                    current_length += word_len
            
            if current_line:
                lines.append(Text(' '.join(current_line), self.style))
            
            return lines if lines else [Text("", self.style)]
        
        # For complex markup text with segments
        # Special handling: if this looks like help text with annotations,
        # try to wrap only the main help text part
        if self._segments and len(self._segments) >= 2:
            # Check if this follows the pattern: help text + annotations
            # Look for segments that start with " (" (like " (required)")
            main_segments = []
            annotation_segments = []
            
            for i, (text, style) in enumerate(self._segments):
                if text.strip().startswith("(") and i > 0:
                    # This and everything after are annotations
                    annotation_segments = self._segments[i:]
                    break
                main_segments.append((text, style))
            
            if annotation_segments:
                # Wrap only the main help text
                main_text = ''.join(text for text, _ in main_segments)
                main_style = None
                for _, style in main_segments:
                    if style:
                        main_style = style
                        break
                
                # Wrap the main text
                wrapped_main = Text(main_text, main_style).wrap(width)
                
                # Add annotations to the last line if they fit
                annotation_text = ''.join(str(Text(text, style)) for text, style in annotation_segments)
                last_line = wrapped_main[-1]
                
                # Check if annotations fit on the last line
                if last_line.visual_length + len(_strip_ansi(annotation_text)) <= width:
                    # Combine last line with annotations
                    combined = Text.from_ansi(str(last_line) + annotation_text)
                    wrapped_main[-1] = combined
                else:
                    # Put annotations on a new line
                    wrapped_main.append(Text.from_ansi(annotation_text))
                
                return wrapped_main
        
        # Fallback: treat as single styled text with first style
        first_style = None
        for _, style in self._segments:
            if style:
                first_style = style
                break
        
        words = plain_text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_len = len(word)
            
            if current_line and current_length + 1 + word_len > width:
                lines.append(Text(' '.join(current_line), first_style))
                current_line = [word]
                current_length = word_len
            else:
                if current_line:
                    current_length += 1
                current_line.append(word)
                current_length += word_len
        
        if current_line:
            lines.append(Text(' '.join(current_line), first_style))
        
        return lines if lines else [self]
    
    def pad(self, width: int, align: str = 'left') -> "Text":
        """Pad text to width, maintaining style."""
        padding_needed = width - self.visual_length
        if padding_needed <= 0:
            return self
        
        # If this is ANSI text, we need to handle it specially
        if hasattr(self, '_ansi_text'):
            # Pad the ANSI text directly
            spaces = ' ' * padding_needed
            if align == 'left':
                padded_ansi = self._ansi_text + spaces
            elif align == 'right':
                padded_ansi = spaces + self._ansi_text
            else:  # center
                left_pad = padding_needed // 2
                right_pad = padding_needed - left_pad
                padded_ansi = ' ' * left_pad + self._ansi_text + ' ' * right_pad
            
            return Text.from_ansi(padded_ansi)
        
        # Regular text
        plain_text = self.plain
        if align == 'left':
            padded = Text(plain_text + ' ' * padding_needed, self.style)
        elif align == 'right':
            padded = Text(' ' * padding_needed + plain_text, self.style)
        else:  # center
            left_pad = padding_needed // 2
            right_pad = padding_needed - left_pad
            padded = Text(' ' * left_pad + plain_text + ' ' * right_pad, self.style)
        
        # For segmented text, we need to convert to ANSI first then pad
        if self._segments:
            # Render segments to ANSI
            rendered_parts = []
            for text, style in self._segments:
                if style:
                    rendered_parts.append(style.render(text))
                else:
                    rendered_parts.append(text)
            ansi_text = ''.join(rendered_parts)
            
            # Now pad the ANSI text
            spaces = ' ' * padding_needed
            if align == 'left':
                padded_ansi = ansi_text + spaces
            elif align == 'right':
                padded_ansi = spaces + ansi_text
            else:  # center
                left_pad = padding_needed // 2
                right_pad = padding_needed - left_pad
                padded_ansi = ' ' * left_pad + ansi_text + ' ' * right_pad
            
            return Text.from_ansi(padded_ansi)
        
        return padded
    
    @classmethod
    def from_markup(cls, markup: str) -> "Text":
        """Parse simple markup like [red]text[/red].
        
        Only supports single-level markup, no nesting.
        Decision: Keep it simple - no nested markup support.
        """
        # Store the parts with their styles for rendering
        segments = []
        
        # Simple regex to find markup tags
        pattern = r'\[(\w+)\](.*?)\[/\1\]'
        last_end = 0
        
        for match in re.finditer(pattern, markup):
            # Add text before this match
            if match.start() > last_end:
                plain_text = markup[last_end:match.start()]
                segments.append((plain_text, None))
            
            # Add the styled text
            tag = match.group(1)
            content = match.group(2)
            
            # Map tag to style
            style = None
            if tag in COLORS:
                style = Style(color=tag)
            elif tag == "bold":
                style = Style(bold=True)
            elif tag == "dim":
                style = Style(dim=True)
            elif tag == "helptext":
                # Support theme-based tags
                style = Style(dim=True)
            elif tag == "helptext_required":
                style = Style(color="bright_red", bold=True)
            elif tag == "helptext_default":
                style = Style(color="cyan")
            elif tag == "metavar":
                style = Style(color="cyan", bold=True)
            
            segments.append((content, style))
            last_end = match.end()
        
        # Add any remaining text
        if last_end < len(markup):
            segments.append((markup[last_end:], None))
        
        # Create Text object
        if segments:
            obj = cls('')
            obj._segments = segments
            return obj
        else:
            return cls(markup)
    
    @classmethod
    def from_ansi(cls, text: str, style: Optional[Style] = None) -> "Text":
        """Create from text that already contains ANSI codes.
        
        This preserves existing ANSI formatting.
        
        Args:
            text: Text containing ANSI codes
            style: Additional style to apply (ignored if text has ANSI codes)
        """
        # Strip ANSI codes to get plain text
        ansi_escape = re.compile(r'\033\[[0-9;]*m')
        plain = ansi_escape.sub('', text)
        
        # Check if the text actually contains ANSI codes
        has_ansi = text != plain
        
        if has_ansi:
            # Text already has ANSI codes, preserve them
            obj = cls(plain)
            obj._ansi_text = text
            obj._has_ansi = True
            return obj
        else:
            # No ANSI codes, use the provided style
            return cls(text, style=style)
    
    def __str__(self) -> str:
        """Render with ANSI codes applied.
        
        This method is lazy - rendering only happens when the string
        representation is actually needed.
        """
        # If created from ANSI, use original
        if hasattr(self, '_ansi_text'):
            return self._ansi_text
        
        # Cache rendered output for segments
        if self._segments:
            if not hasattr(self, '_rendered_segments'):
                rendered_parts = []
                for text, style in self._segments:
                    if style:
                        rendered_parts.append(style.render(text))
                    else:
                        rendered_parts.append(text)
                self._rendered_segments = ''.join(rendered_parts)
            return self._rendered_segments
        
        # Simple text with optional style
        if self.style:
            if not hasattr(self, '_rendered_simple'):
                self._rendered_simple = self.style.render(self.content)
            return self._rendered_simple
        return self.content
    
    def __add__(self, other: Any) -> "Text":
        """Concatenate with another Text or string."""
        if isinstance(other, str):
            # Add plain string
            new_text = Text(self.plain + other)
            if self.style and not self._segments:
                new_text.style = self.style
            return new_text
        elif isinstance(other, Text):
            # Combine two Text objects
            # This is simplified - a full implementation would handle segments
            return Text.from_ansi(str(self) + str(other))
        else:
            return NotImplemented


class CompactTable:
    """Two-column table optimized for CLI option/help display.
    
    Unlike rich.table.Table, this is specifically designed for the common
    CLI pattern of showing options and their descriptions side-by-side.
    
    This implementation is lazy - it defers all formatting work until
    render() is called, improving startup performance.
    """
    def __init__(self):
        # Store raw data - don't create Text objects yet
        self.rows: List[Tuple[Any, Any]] = []
        self._rendered_cache: Dict[int, str] = {}
    
    def add_row(self, option: Any, description: Any) -> "CompactTable":
        """Add an option and its help text.
        
        Args:
            option: Option text (can be str, Text, or any object)
            description: Description text (can be str, Text, or any object)
        
        Returns self for chaining.
        """
        # Just store the raw objects - no processing
        self.rows.append((option, description))
        # Clear cache when data changes
        self._rendered_cache.clear()
        return self
    
    def render(self, width: int, min_option_width: int = 2, gutter: int = 2) -> str:
        """Render the table to a string.
        
        Args:
            width: Terminal width
            min_option_width: Minimum width for option column
            gutter: Space between columns
            
        The algorithm optimizes space usage:
        1. Calculate max option width needed
        2. Allocate remaining space to description
        3. Wrap descriptions intelligently
        4. Align continuation lines
        
        Results are cached based on width for performance.
        """
        if not self.rows:
            return ""
        
        # Check cache first
        cache_key = (width, min_option_width, gutter)
        cache_str = f"{cache_key[0]}_{cache_key[1]}_{cache_key[2]}"
        if cache_str in self._rendered_cache:
            return self._rendered_cache[cache_str]
        
        # Convert all items to Text objects for consistent handling
        text_rows = []
        for option, description in self.rows:
            # Ensure we have Text objects
            if isinstance(option, str):
                option = Text(option)
            elif not isinstance(option, Text):
                option = Text(str(option))
                
            if isinstance(description, str):
                description = Text(description)
            elif not isinstance(description, Text):
                description = Text(str(description))
            
            text_rows.append((option, description))
        
        # Calculate optimal column widths
        option_lengths = [opt.visual_length for opt, _ in text_rows]
        max_option_len = max(option_lengths)
        
        # For CLI help text, use full alignment for better readability
        # All descriptions will start at the same column
        target_option_width = max(max_option_len, min_option_width)
        
        # Ensure we have space for description
        desc_width = width - target_option_width - gutter
        if desc_width < 20:  # Minimum description width
            # If too narrow, fall back to vertical layout
            desc_width = width - gutter
            target_option_width = 0
        
        lines = []
        for option, description in text_rows:
            if target_option_width > 0:
                # Check if this specific option is too long
                if option.visual_length > target_option_width:
                    # Option is too long, put description on next line
                    lines.append(str(option))
                    desc_lines = description.wrap(desc_width)
                    indent = ' ' * (target_option_width + gutter)
                    for desc_line in desc_lines:
                        lines.append(f"{indent}{desc_line}")
                else:
                    # Standard two-column layout
                    option_padded = option.pad(target_option_width)
                    
                    # Wrap description, maintaining style
                    desc_lines = description.wrap(desc_width)
                    if desc_lines:
                        # First line with option
                        lines.append(f"{option_padded}{' ' * gutter}{desc_lines[0]}")
                        
                        # Continuation lines aligned to target width
                        indent = ' ' * (target_option_width + gutter)
                        for desc_line in desc_lines[1:]:
                            lines.append(f"{indent}{desc_line}")
                    else:
                        lines.append(str(option_padded))
            else:
                # Narrow layout - everything on separate lines
                lines.append(str(option))
                desc_lines = description.wrap(desc_width)
                # In narrow layout, still respect min_option_width for indentation
                indent = ' ' * (min_option_width + gutter)
                for desc_line in desc_lines:
                    lines.append(f"{indent}{desc_line}")
        
        result = '\n'.join(lines)
        
        # Cache the result
        self._rendered_cache[cache_str] = result
        
        return result


class CliColumns:
    """Multi-column layout optimized for CLI option lists.
    
    Better than rich.columns.Columns for CLI use cases because it:
    - Packs short items more efficiently
    - Handles common CLI patterns (flags all start with --)
    - Balances columns better
    """
    def __init__(self, items: List[str], column_first: bool = True):
        """Create columns from a list of items.
        
        Args:
            items: List of strings to display
            column_first: If True, fill columns top-to-bottom (like 'ls')
        """
        self.items = items
        self.column_first = column_first
    
    def render(self, width: int, min_column_width: int = 10, gutter: int = 2) -> str:
        """Render items in columns.
        
        Automatically determines optimal column count based on:
        - Terminal width
        - Longest item length
        - Minimum column width
        """
        if not self.items:
            return ""
        
        if len(self.items) == 1:
            return self.items[0]
        
        # Calculate column constraints
        max_item_len = max(len(item) for item in self.items)
        col_width = max(max_item_len, min_column_width)
        
        # How many columns can we fit?
        max_cols = max(1, (width + gutter) // (col_width + gutter))
        
        # Try different column counts to find optimal layout
        best_layout = None
        min_rows = float('inf')
        
        for num_cols in range(min(max_cols, len(self.items)), 0, -1):
            rows_needed = (len(self.items) + num_cols - 1) // num_cols
            
            # Check if this layout fits
            total_width = num_cols * col_width + (num_cols - 1) * gutter
            if total_width <= width and rows_needed < min_rows:
                min_rows = rows_needed
                best_layout = num_cols
        
        if not best_layout:
            best_layout = 1
        
        # Arrange items
        num_cols = best_layout
        num_rows = (len(self.items) + num_cols - 1) // num_cols
        
        # Build the grid
        grid = []
        if self.column_first:
            # Fill columns top to bottom
            for row in range(num_rows):
                row_items = []
                for col in range(num_cols):
                    idx = col * num_rows + row
                    if idx < len(self.items):
                        row_items.append(self.items[idx].ljust(col_width))
                grid.append((' ' * gutter).join(row_items).rstrip())
        else:
            # Fill rows left to right
            for row in range(num_rows):
                row_items = []
                for col in range(num_cols):
                    idx = row * num_cols + col
                    if idx < len(self.items):
                        row_items.append(self.items[idx].ljust(col_width))
                grid.append((' ' * gutter).join(row_items).rstrip())
        
        return '\n'.join(grid)


class CliError:
    """Structured error display with CLI-specific features.
    
    Provides better error messages than generic exceptions:
    - Did-you-mean suggestions
    - Contextual help
    - Copy-paste friendly formatting
    """
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Create an error.
        
        Args:
            message: Main error message
            context: Additional context (expected, got, available options, etc)
        """
        self.message = message
        self.context = context or {}
        self.suggestions: List[str] = []
    
    def with_suggestions(self, available: List[str], max_suggestions: int = 3) -> "CliError":
        """Add did-you-mean suggestions based on similarity.
        
        Uses edit distance and prefix matching for good suggestions.
        Decision: Returns self for chaining (modifies in place).
        """
        # Extract what the user typed from the error message
        # Look for patterns like "Unknown option: --foo"
        user_input = None
        if "Unknown option:" in self.message:
            parts = self.message.split("Unknown option:")
            if len(parts) > 1:
                user_input = parts[1].strip()
        
        if user_input:
            # Calculate similarity scores
            scores = []
            for option in available:
                score = _similarity_score(user_input, option)
                scores.append((score, option))
            
            # Sort by score (lower is better) and take top suggestions
            scores.sort(key=lambda x: x[0])
            self.suggestions = [opt for score, opt in scores[:max_suggestions] if score < 5]
        
        return self
    
    def render(self, width: int) -> str:
        """Render error as a formatted panel."""
        # Build the error content
        lines = [self.message]
        
        # Add context information
        if self.context:
            lines.append("")  # Blank line
            for key, value in self.context.items():
                # Format context nicely
                if key == "expected":
                    lines.append(f"Expected: {value}")
                elif key == "got":
                    lines.append(f"Got: {value}")
                elif key == "help":
                    lines.append(f"{value}")
                else:
                    lines.append(f"{key.title()}: {value}")
        
        # Add suggestions
        if self.suggestions:
            lines.append("")
            lines.append("Did you mean:")
            for suggestion in self.suggestions:
                lines.append(f"  {suggestion}")
        
        # Wrap in a panel
        panel = Panel('\n'.join(lines), title="Error", style=Style(color="red"))
        return panel.render(width)


class Panel:
    """Simple panel with border for error messages and help sections.
    
    This implementation is lazy - rendering is deferred until needed.
    """
    def __init__(
        self,
        content: Any,
        title: Optional[str] = None,
        title_align: str = "center",
        style: Optional[Style] = None,
        border_style: Optional[Style] = None,
        expand: bool = True,
    ):
        self.content = content
        self.title = title
        self.title_align = title_align
        self.style = style or Style()
        self.border_style = border_style or self.style
        self.expand = expand  # Not used in our implementation, but kept for API compatibility
        self._rendered_cache: Dict[int, str] = {}
    
    def render(self, width: int) -> str:
        """Render with Unicode box drawing characters.
        
        Results are cached by width for performance.
        Decision: Use Unicode by default, could add ASCII fallback later.
        """
        # Check if rich formatting is enabled
        try:
            from . import _arguments
            if not _arguments.USE_RICH:
                # No borders when USE_RICH is False
                if hasattr(self.content, 'render'):
                    return self.content.render(width)
                else:
                    return str(self.content)
        except ImportError:
            pass
        
        # Check cache first
        if width in self._rendered_cache:
            return self._rendered_cache[width]
        # Get content as string
        if hasattr(self.content, 'render'):
            content_str = self.content.render(width - 4)  # Account for borders
        else:
            content_str = str(self.content)
        
        content_lines = content_str.split('\n')
        
        # Box drawing characters (use rounded corners like rich)
        top_left = "╭"
        top_right = "╮"
        bottom_left = "╰"
        bottom_right = "╯"
        horizontal = "─"
        vertical = "│"
        
        # Build top border
        inner_width = width - 2
        if self.title:
            # Parse markup in title if present
            if '[' in self.title and ']' in self.title:
                title_text = Text.from_markup(self.title)
                title_str = f" {title_text} "
                visual_len = title_text.visual_length + 2  # +2 for spaces
            else:
                title_str = f" {self.title} "
                visual_len = len(title_str)
            
            if self.title_align == "left":
                # Left-aligned title (tyro style)
                top_border = top_left + horizontal + title_str + horizontal * (inner_width - 1 - visual_len) + top_right
            elif self.title_align == "right":
                # Right-aligned title
                top_border = top_left + horizontal * (inner_width - visual_len) + title_str + horizontal + top_right
            else:
                # Center title (default)
                padding = (inner_width - visual_len) // 2
                top_border = (
                    top_left + 
                    horizontal * padding + 
                    title_str + 
                    horizontal * (inner_width - padding - visual_len) +
                    top_right
                )
        else:
            top_border = top_left + horizontal * inner_width + top_right
        
        # Build content lines with side borders
        bordered_lines = []
        for line in content_lines:
            # Convert to Text object to handle padding properly
            line_text = Text.from_ansi(line) if isinstance(line, str) else line
            padded = line_text.pad(inner_width - 2)  # -2 for spaces around content
            bordered_lines.append(f"{vertical} {padded} {vertical}")
        
        # Build bottom border
        bottom_border = bottom_left + horizontal * inner_width + bottom_right
        
        # Combine all parts
        all_lines = [top_border] + bordered_lines + [bottom_border]
        
        # Apply border style to borders only, not content
        if self.border_style and self.border_style.to_ansi():
            # Style the borders
            styled_lines = []
            styled_lines.append(self.border_style.render(all_lines[0]))  # Top border
            
            # Content lines - only style the border characters, not the content
            for line in all_lines[1:-1]:
                # Extract the border parts and content
                left_border = line[0]  # │
                right_border = line[-1]  # │
                content = line[1:-1]  # Everything between borders
                
                # Apply border style only to borders
                styled_line = (
                    self.border_style.render(left_border) + 
                    content + 
                    self.border_style.render(right_border)
                )
                styled_lines.append(styled_line)
            
            styled_lines.append(self.border_style.render(all_lines[-1]))  # Bottom border
            result = '\n'.join(styled_lines)
        else:
            result = '\n'.join(all_lines)
        
        # Cache the result
        self._rendered_cache[width] = result
        return result


class Rule:
    """Horizontal rule for visual separation."""
    def __init__(self, title: Optional[str] = None, style: Optional[Style] = None):
        self.title = title
        self.style = style or Style()
    
    def render(self, width: int) -> str:
        """Render as a line with optional centered title."""
        char = "─"
        
        if self.title:
            # Center title with padding
            title_str = f" {self.title} "
            padding = (width - len(title_str)) // 2
            line = char * padding + title_str + char * (width - padding - len(title_str))
        else:
            line = char * width
        
        # Apply style
        if self.style and self.style.to_ansi():
            return self.style.render(line)
        return line


class Group:
    """Stack renderables vertically."""
    def __init__(self, *renderables: Any):
        self.renderables = renderables
    
    def render(self, width: int) -> str:
        """Render each item with newline separation."""
        if not self.renderables:
            return ""
        
        parts = []
        for item in self.renderables:
            if hasattr(item, 'render'):
                parts.append(item.render(width))
            elif isinstance(item, str) and '[' in item and ']' in item:
                # Handle markup in strings
                parts.append(str(Text.from_markup(item)))
            else:
                parts.append(str(item))
        
        return '\n'.join(parts)


class Padding:
    """Add padding around content."""
    def __init__(self, renderable: Any, pad: Tuple[int, int, int, int]):
        """
        Args:
            renderable: Content to pad
            pad: (top, right, bottom, left) padding
        """
        self.renderable = renderable
        self.pad = pad
    
    def render(self, width: int) -> str:
        """Render with spacing."""
        top, right, bottom, left = self.pad
        
        # Get content
        if hasattr(self.renderable, 'render'):
            content = self.renderable.render(width - left - right)
        else:
            content = str(self.renderable)
        
        lines = content.split('\n')
        
        # Add left/right padding to each line
        padded_lines = []
        for line in lines:
            # Don't add right padding if not requested
            if right > 0:
                padded = ' ' * left + line + ' ' * right
            else:
                padded = ' ' * left + line
            padded_lines.append(padded)
        
        # Add top/bottom padding
        result_lines = []
        
        # Top padding
        for _ in range(top):
            result_lines.append('')
        
        # Content
        result_lines.extend(padded_lines)
        
        # Bottom padding
        for _ in range(bottom):
            result_lines.append('')
        
        return '\n'.join(result_lines)


class Console:
    """Simplified console for output handling."""
    def __init__(
        self,
        theme: Optional[TyroTheme] = None,
        width: Optional[int] = None,
        stderr: bool = False,
    ):
        """
        Args:
            theme: Styling theme
            width: Force width (None = auto-detect)
            stderr: Output to stderr instead of stdout
        """
        self.theme = theme or TyroTheme()
        self._width = width
        self.stderr = stderr
        self._file = sys.stderr if stderr else sys.stdout
    
    @property
    def width(self) -> int:
        """Get console width."""
        if self._width is not None:
            return self._width
        
        # Auto-detect terminal width
        try:
            return shutil.get_terminal_size().columns
        except:
            return 80  # Fallback
    
    def print(self, *renderables: Any) -> None:
        """Print renderables to console."""
        for item in renderables:
            if hasattr(item, 'render'):
                output = item.render(self.width)
            else:
                output = str(item)
            
            print(output, file=self._file)
    
    @contextmanager
    def capture(self) -> Generator[Any, None, None]:
        """Capture output to string instead of printing."""
        # Create a string buffer
        buffer = io.StringIO()
        
        # Temporarily replace the file
        old_file = self._file
        self._file = buffer
        
        # Create capture object
        class Capture:
            def get(self) -> str:
                return buffer.getvalue()
        
        capture = Capture()
        
        try:
            yield capture
        finally:
            # Restore original file
            self._file = old_file


def escape(text: str) -> str:
    """Escape markup brackets in text."""
    # Don't double-escape
    if r'\[' in text:
        return text
    
    # Escape only opening brackets (rich behavior)
    return text.replace('[', r'\[')


# Helper functions

def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\033\[[0-9;]*m')
    return ansi_escape.sub('', text)


def _similarity_score(a: str, b: str) -> int:
    """Calculate similarity score between two strings.
    
    Lower score = more similar. Uses simple edit distance.
    """
    # Simple Levenshtein distance implementation
    if len(a) > len(b):
        a, b = b, a
    
    if not a:
        return len(b)
    
    previous_row = range(len(a) + 1)
    for i, c2 in enumerate(b):
        current_row = [i + 1]
        for j, c1 in enumerate(a):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]