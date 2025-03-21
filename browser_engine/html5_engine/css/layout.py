"""
CSS Layout Engine implementation.
This module handles layout calculations for HTML elements based on the CSS box model.
"""

import logging
import re
import math
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from enum import Enum

from ..dom import Element, Document

logger = logging.getLogger(__name__)

class DisplayType(Enum):
    """CSS display property values."""
    BLOCK = "block"
    INLINE = "inline"
    INLINE_BLOCK = "inline-block"
    FLEX = "flex"
    GRID = "grid"
    NONE = "none"
    TABLE = "table"
    TABLE_ROW = "table-row"
    TABLE_CELL = "table-cell"

class PositionType(Enum):
    """CSS position property values."""
    STATIC = "static"
    RELATIVE = "relative"
    ABSOLUTE = "absolute"
    FIXED = "fixed"
    STICKY = "sticky"

class FloatType(Enum):
    """CSS float property values."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"

class BoxType(Enum):
    """CSS box type enum for layout boxes."""
    BLOCK = "block"
    INLINE = "inline"
    INLINE_BLOCK = "inline-block"

class BoxMetrics:
    """
    Container for box model metrics.
    
    Stores measurements for content box, padding, border, and margin.
    """
    
    def __init__(self):
        """Initialize box metrics with default values."""
        # Content box dimensions
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        
        # Content dimensions (may differ from width/height due to box-sizing)
        self.content_width: Union[int, str] = 'auto'
        self.content_height: Union[int, str] = 'auto'
        
        # Padding (top, right, bottom, left)
        self.padding_top: int = 0
        self.padding_right: int = 0
        self.padding_bottom: int = 0
        self.padding_left: int = 0
        
        # Border (top, right, bottom, left)
        self.border_top_width: int = 0
        self.border_right_width: int = 0
        self.border_bottom_width: int = 0
        self.border_left_width: int = 0
        
        # Margin (top, right, bottom, left)
        self.margin_top: int = 0
        self.margin_right: int = 0
        self.margin_bottom: int = 0
        self.margin_left: int = 0
        
        # Position coordinates
        self.x: int = 0
        self.y: int = 0
    
    @property
    def padding_box_width(self) -> int:
        """Get the width of the padding box."""
        width = self.width
        if isinstance(width, str):
            try:
                width = int(width)
            except (ValueError, TypeError):
                width = 0
        elif width is None:
            width = 0
        return width + self.padding_left + self.padding_right
    
    @property
    def padding_box_height(self) -> int:
        """Get the height of the padding box."""
        height = self.height
        if isinstance(height, str):
            try:
                height = int(height)
            except (ValueError, TypeError):
                height = 0
        elif height is None:
            height = 0
        return height + self.padding_top + self.padding_bottom
    
    @property
    def border_box_width(self) -> int:
        """Get the width of the border box."""
        return self.padding_box_width + self.border_left_width + self.border_right_width
    
    @property
    def border_box_height(self) -> int:
        """Get the height of the border box."""
        return self.padding_box_height + self.border_top_width + self.border_bottom_width
    
    @property
    def margin_box_width(self) -> int:
        """Get the width of the margin box."""
        return self.border_box_width + self.margin_left + self.margin_right
    
    @property
    def margin_box_height(self) -> int:
        """Get the height of the margin box."""
        return self.border_box_height + self.margin_top + self.margin_bottom

    def _update_box_dimensions(self) -> None:
        """
        Update box dimensions based on content dimensions.
        
        This method updates the box dimensions based on the content dimensions,
        taking into account padding, border, and margin.
        """
        # Handle content width
        if isinstance(self.content_width, (int, float)):
            self.width = self.content_width
        elif isinstance(self.content_width, str):
            if self.content_width == 'auto':
                # For auto width, we'll use a default percentage of parent width
                # This will be adjusted by the layout engine based on the element type
                self.width = 0  # Will be set by layout engine
            else:
                try:
                    self.width = int(self.content_width)
                except (ValueError, TypeError):
                    # If conversion fails, use a default width
                    self.width = 0  # Will be set by layout engine
        
        # Handle content height
        if isinstance(self.content_height, (int, float)):
            self.height = self.content_height
        elif isinstance(self.content_height, str):
            if self.content_height == 'auto':
                # For auto height, we'll use a default based on content
                # This will be adjusted by the layout engine based on content and children
                self.height = 0  # Will be set by layout engine
            else:
                try:
                    self.height = int(self.content_height)
                except (ValueError, TypeError):
                    # If conversion fails, use a default height
                    self.height = 0  # Will be set by layout engine

class LayoutBox:
    """
    Layout box for an element.
    
    Stores layout information for a DOM element.
    """
    
    def __init__(self, element: Optional[Element] = None, display: DisplayType = DisplayType.BLOCK, parent: Optional['LayoutBox'] = None):
        """
        Initialize a layout box for an element.
        
        Args:
            element: The DOM element to create a layout box for
            display: The display type for the layout box
            parent: The parent layout box
        """
        self.element = element
        self.box_metrics = BoxMetrics()
        
        # Layout properties
        self.display: DisplayType = display
        self.box_type: BoxType = BoxType.BLOCK  # Default to BLOCK box type
        self.position: PositionType = PositionType.STATIC
        self.float_type: FloatType = FloatType.NONE
        
        # Computed style
        self.computed_style: Dict[str, str] = {}
        
        # Child layout boxes
        self.children: List[LayoutBox] = []
        
        # Parent layout box
        self.parent: Optional[LayoutBox] = parent
    
    def add_child(self, child: 'LayoutBox') -> None:
        """
        Add a child layout box.
        
        Args:
            child: The child layout box to add
        """
        self.children.append(child)
        child.parent = self
        
    def _update_box_dimensions(self) -> None:
        """
        Update box dimensions based on content dimensions.
        
        This method updates the box dimensions based on the content dimensions,
        taking into account padding, border, and margin.
        """
        # If content width is a number or numeric string, use it to calculate width
        if isinstance(self.box_metrics.content_width, (int, float)):
            self.box_metrics.width = self.box_metrics.content_width
        elif isinstance(self.box_metrics.content_width, str):
            try:
                self.box_metrics.width = int(self.box_metrics.content_width)
            except (ValueError, TypeError):
                self.box_metrics.width = 0
        
        # If content height is a number or numeric string, use it to calculate height
        if isinstance(self.box_metrics.content_height, (int, float)):
            self.box_metrics.height = self.box_metrics.content_height
        elif isinstance(self.box_metrics.content_height, str):
            try:
                self.box_metrics.height = int(self.box_metrics.content_height)
            except (ValueError, TypeError):
                self.box_metrics.height = 0

class LayoutEngine:
    """
    CSS Layout Engine.
    
    This class calculates layout for HTML elements based on CSS rules.
    """
    
    def __init__(self):
        """Initialize the layout engine."""
        logger.debug("Layout Engine initialized")
    
    def create_layout(self, document, viewport_width: int = None, viewport_height: int = None) -> Optional[LayoutBox]:
        """
        Create a layout tree from a document.
        
        Args:
            document: Document to create layout for
            viewport_width: Optional viewport width override
            viewport_height: Optional viewport height override
            
        Returns:
            Root layout box or None if document is invalid
        """
        if viewport_width is not None:
            self.viewport_width = viewport_width
        if viewport_height is not None:
            self.viewport_height = viewport_height
            
        if not document or not hasattr(document, 'document_element') or not document.document_element:
            return None
            
        # Build layout tree from DOM
        layout_tree = self._build_layout_tree(document.document_element)
        
        # Apply styles
        layout_tree.compute_styles()
        
        # Apply layout
        self.layout(layout_tree, self.viewport_width, self.viewport_height)
        
        return layout_tree
        
    def layout(self, layout_box: LayoutBox, viewport_width: int, viewport_height: int) -> None:
        """
        Apply layout to a layout tree.
        
        Args:
            layout_box: Root layout box
            viewport_width: Viewport width
            viewport_height: Viewport height
        """
        # Update viewport dimensions
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        # Apply layout starting at position (0, 0)
        # Check if the layout_box has its own layout method
        if hasattr(layout_box, 'layout') and callable(getattr(layout_box, 'layout')):
            # Use the layout_box's own layout method
            layout_box.layout(viewport_width, 0, 0)
        else:
            # Use our internal layout method as a fallback
            self._layout_box(layout_box, 0, 0, viewport_width)
            
    def _layout_box(self, layout_box: LayoutBox, x: int, y: int, container_width: int) -> None:
        """
        Apply layout to a single box and its children.
        
        Args:
            layout_box: Layout box to apply layout to
            x: X position
            y: Y position
            container_width: Width of containing box
        """
        try:
            # Set position
            layout_box.box_metrics.x = x
            layout_box.box_metrics.y = y
            
            # Calculate width if it needs to be determined
            if isinstance(layout_box.box_metrics.width, str):
                if layout_box.box_metrics.width == 'auto':
                    layout_box.box_metrics.width = 0
                else:
                    try:
                        layout_box.box_metrics.width = float(layout_box.box_metrics.width)
                    except (ValueError, TypeError):
                        layout_box.box_metrics.width = 0
            
            # Convert width to float for comparison
            width = float(layout_box.box_metrics.width) if isinstance(layout_box.box_metrics.width, (int, float)) else 0
            
            # Calculate content width based on display type
            if width == 0:
                if layout_box.display == DisplayType.BLOCK:
                    # Block elements take full container width
                    layout_box.box_metrics.content_width = container_width
                elif layout_box.display == DisplayType.INLINE:
                    # Inline elements size to content
                    if layout_box.element and hasattr(layout_box.element, 'text_content') and layout_box.element.text_content:
                        # Calculate width based on text content
                        text_length = len(layout_box.element.text_content)
                        font_size = self._parse_dimension(layout_box.computed_style.get('font-size', '16px'))
                        if isinstance(font_size, str):
                            font_size = 16 if font_size == 'auto' else float(font_size)
                        
                        # Rough estimate: each character is about 0.6 times the font size width
                        layout_box.box_metrics.content_width = int(text_length * font_size * 0.6)
                    else:
                        # Minimum width for empty inline elements
                        layout_box.box_metrics.content_width = 0
                else:
                    # Inline elements use a percentage of container width
                    layout_box.box_metrics.content_width = int(container_width * 0.8)  # 80% of container width
            
            # Update box dimensions
            try:
                layout_box._update_box_dimensions()
            except Exception as e:
                logger.error(f"Error updating box dimensions: {e}")
            
            # Layout children
            try:
                if layout_box.display == DisplayType.BLOCK:
                    self._layout_block_children(layout_box, container_width)
                elif layout_box.display == DisplayType.INLINE:
                    self._layout_inline_children(layout_box, container_width)
                else:
                    # Default to block layout
                    self._layout_block_children(layout_box, container_width)
            except Exception as e:
                logger.error(f"Error laying out children: {e}")
            
            # Calculate height if it needs to be determined
            if isinstance(layout_box.box_metrics.height, str):
                if layout_box.box_metrics.height == 'auto':
                    layout_box.box_metrics.height = 0
                else:
                    try:
                        layout_box.box_metrics.height = float(layout_box.box_metrics.height)
                    except (ValueError, TypeError):
                        layout_box.box_metrics.height = 0
            
            # Convert height to float for comparison
            height = float(layout_box.box_metrics.height) if isinstance(layout_box.box_metrics.height, (int, float)) else 0
            
            if height == 0:
                # First try to calculate height based on children
                height = 0
                for child in layout_box.children:
                    try:
                        # Ensure child metrics are numeric
                        child_y = float(child.box_metrics.y) if isinstance(child.box_metrics.y, (int, float)) else 0
                        child_height = float(child.box_metrics.margin_box_height) if isinstance(child.box_metrics.margin_box_height, (int, float)) else 0
                        layout_y = float(layout_box.box_metrics.y) if isinstance(layout_box.box_metrics.y, (int, float)) else 0
                        
                        child_bottom = child_y + child_height - layout_y
                        height = max(height, child_bottom)
                    except Exception as e:
                        logger.error(f"Error calculating child height: {e}")
                        continue
                
                # If no children or height is still 0, use element-specific defaults
                if height == 0:
                    if layout_box.element and hasattr(layout_box.element, 'text_content') and layout_box.element.text_content:
                        # For text content, calculate height based on font size and line height
                        font_size = self._parse_dimension(layout_box.computed_style.get('font-size', '16px'))
                        if isinstance(font_size, str):
                            font_size = 16 if font_size == 'auto' else float(font_size)
                        
                        line_height = self._parse_dimension(layout_box.computed_style.get('line-height', '1.2'))
                        if isinstance(line_height, str):
                            line_height = font_size * 1.2 if line_height == 'auto' else float(line_height)
                        
                        height = int(line_height)  # Single line height
                    else:
                        # For empty elements, use tag-specific defaults
                        tag_name = layout_box.element.tag_name.lower() if hasattr(layout_box.element, 'tag_name') else ''
                        
                        if tag_name in ['input', 'button', 'select', 'textarea']:
                            height = 24  # Form elements
                        elif tag_name in ['img']:
                            height = 150  # Default image placeholder height
                        elif tag_name in ['hr']:
                            height = 2  # Horizontal rule
                        elif tag_name in ['br']:
                            height = 16  # Line break
                        elif tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            # Headers get progressively smaller
                            base_height = 32
                            header_level = int(tag_name[1])
                            height = base_height - ((header_level - 1) * 4)
                        else:
                            # Default minimum height for other elements
                            height = 0  # Let content determine height
                
                layout_box.box_metrics.content_height = height
            
            try:
                layout_box._update_box_dimensions()
            except Exception as e:
                logger.error(f"Error updating final box dimensions: {e}")
                
        except Exception as e:
            logger.error(f"Error in layout_box: {e}")

    def _layout_block_children(self, layout_box: LayoutBox, container_width: int) -> None:
        """
        Layout block children of a box.
        
        Args:
            layout_box: Parent box
            container_width: Width of containing box
        """
        # Convert box metrics to numeric values
        margin_left = layout_box.box_metrics.margin_left
        margin_right = layout_box.box_metrics.margin_right
        border_left = layout_box.box_metrics.border_left_width
        border_right = layout_box.box_metrics.border_right_width
        padding_left = layout_box.box_metrics.padding_left
        padding_right = layout_box.box_metrics.padding_right
        
        # Convert string values to float, handling 'auto' as 0
        if isinstance(margin_left, str):
            margin_left = 0 if margin_left == 'auto' else float(margin_left)
        if isinstance(margin_right, str):
            margin_right = 0 if margin_right == 'auto' else float(margin_right)
        if isinstance(border_left, str):
            border_left = 0 if border_left == 'auto' else float(border_left)
        if isinstance(border_right, str):
            border_right = 0 if border_right == 'auto' else float(border_right)
        if isinstance(padding_left, str):
            padding_left = 0 if padding_left == 'auto' else float(padding_left)
        if isinstance(padding_right, str):
            padding_right = 0 if padding_right == 'auto' else float(padding_right)
        
        x = layout_box.box_metrics.x + margin_left + border_left + padding_left
        y = layout_box.box_metrics.y + layout_box.box_metrics.margin_top + layout_box.box_metrics.border_top_width + layout_box.box_metrics.padding_top
        
        # Calculate available width safely
        try:
            if isinstance(layout_box.box_metrics.content_width, (int, float)):
                available_width = float(layout_box.box_metrics.content_width)
            elif isinstance(layout_box.box_metrics.content_width, str):
                if layout_box.box_metrics.content_width == 'auto':
                    # For auto width, use container width minus padding and borders
                    total_margin = margin_left + margin_right
                    total_padding = padding_left + padding_right
                    total_border = border_left + border_right
                    
                    available_width = container_width - total_margin - total_padding - total_border
                else:
                    try:
                        available_width = float(layout_box.box_metrics.content_width)
                    except (ValueError, TypeError):
                        # If conversion fails, use container width as fallback
                        available_width = container_width - total_padding - total_border
            else:
                # Default to container width if content_width is None or invalid
                available_width = container_width - total_padding - total_border
        except Exception as e:
            logger.error(f"Error calculating available width: {e}")
            available_width = container_width - total_padding - total_border
        
        total_height = 0
        prev_element_tag = None
        
        # Base spacing for different element types (as percentages of viewport height)
        base_spacing = {
            'h1': 0.08,    # 8% spacing for main headings
            'h2': 0.07,    # 7% spacing for major subheadings
            'h3': 0.06,    # 6% spacing for subheadings
            'h4': 0.05,    # 5% spacing for minor subheadings
            'h5': 0.04,    # 4% spacing for small headings
            'h6': 0.03,    # 3% spacing for smallest headings
            'p': 0.04,     # 4% spacing for paragraphs
            'div': 0.04,   # 4% spacing for divs
            'pre': 0.04,   # 4% spacing for code blocks
            'a': 0.02,     # 2% spacing for links
            'span': 0.01,  # 1% spacing for inline elements
            'img': 0.04,   # 4% spacing for images
            'ul': 0.04,    # 4% spacing for lists
            'ol': 0.04,    # 4% spacing for ordered lists
            'li': 0.02,    # 2% spacing for list items
            'table': 0.04, # 4% spacing for tables
            'form': 0.04,  # 4% spacing for forms
            'input': 0.02, # 2% spacing for inputs
            'button': 0.02 # 2% spacing for buttons
        }
        def smallest_multiplier(spacing):
            # Find the smallest integer y where x * y = spacing for some x
            if spacing <= 1:
                return spacing  # Handle special cases
        
            # Check all potential divisors up to sqrt(spacing)
            for i in range(2, int(spacing**0.5) + 1):
                if spacing % i == 0:
                    return i
            
            # If no divisors found, spacing is prime
            return spacing
        
        for child in layout_box.children:
            # Get current element's tag
            current_tag = child.element.tag_name.lower() if hasattr(child.element, 'tag_name') else None
            


            # Calculate spacing based on current and previous elements
            spacing = 0
            if current_tag and prev_element_tag:
                # Get base spacing for both elements
                current_base = base_spacing.get(current_tag, 0.02)  # Default to 2%
                prev_base = base_spacing.get(prev_element_tag, 0.02)  # Default to 2%
                
                # Special case handling for divs and spans to prevent overlapping
                if current_tag == 'div' and prev_element_tag == 'div':
                    # Ensure minimum spacing between consecutive divs
                    spacing = max((current_base + prev_base) / 2, 0.08) * container_width  # Increased to 8%
                elif current_tag == 'span' and prev_element_tag == 'span':
                    # Ensure minimum spacing between consecutive spans
                    spacing = max((current_base + prev_base) / 2, 0.02) * container_width
                elif current_tag == 'div' or prev_element_tag == 'div':
                    # Ensure minimum spacing when div is next to any other element
                    spacing = max((current_base + prev_base) / 2, 0.06) * container_width  # Increased to 6%
                # Add extra spacing between divs and headings or paragraphs
                elif (current_tag and current_tag.startswith('h')) or (prev_element_tag and prev_element_tag.startswith('h')):
                    spacing = max((spacing * smallest_multiplier(spacing)), 0.10 * (container_width * 1.5))  # 10% for headings
                elif current_tag == 'p' or prev_element_tag == 'p' or current_tag == 'a' or prev_element_tag == 'a' or current_tag == 'cite' or prev_element_tag == 'cite':
                    spacing = max((spacing * smallest_multiplier(spacing)), 0.07 * (container_width * 1.5))  # 7% for paragraphs
                else:
                    # Use half of each element's base spacing to create the gap
                    # But ensure a minimum spacing to prevent elements from merging visually
                    base_spacing_value = ((current_base + prev_base) / 2)
                    
                    # Minimum spacing for any adjacent elements to prevent merging
                    min_spacing = 0.03  # 3% minimum spacing between any two elements
                    
                    spacing = max(base_spacing_value, min_spacing) * container_width
            
            # Update y position with spacing if not the first element
            if prev_element_tag:
                y += spacing
            
            # Layout the child at the current position
            self._layout_box(child, x, y, available_width)
            
            # Get child's margin box height safely
            child_margin_box_height = child.box_metrics.margin_box_height
            if isinstance(child_margin_box_height, str):
                try:
                    child_margin_box_height = float(child_margin_box_height)
                except (ValueError, TypeError):
                    child_margin_box_height = 0
            elif isinstance(child_margin_box_height, (int, float)):
                child_margin_box_height = float(child_margin_box_height)
            else:
                child_margin_box_height = 0
            
            # Force proper vertical stacking for block elements
            # Ensure we always move down by the height of the element plus spacing
            y += child_margin_box_height
            
            # Save element tag for next iteration
            if hasattr(child.element, 'tag_name'):
                prev_element_tag = child.element.tag_name.lower()
        
        # Update parent box height
        layout_box.box_metrics.content_height = max(total_height, float(layout_box.box_metrics.content_height) if isinstance(layout_box.box_metrics.content_height, (int, float)) else 0)

    def _layout_inline_children(self, layout_box: LayoutBox, container_width: int) -> None:
        """
        Layout inline children of a box.
        
        Args:
            layout_box: Parent box
            container_width: Width of containing box
        """
        # Convert box metrics to numeric values
        margin_left = layout_box.box_metrics.margin_left
        margin_right = layout_box.box_metrics.margin_right
        border_left = layout_box.box_metrics.border_left_width
        border_right = layout_box.box_metrics.border_right_width
        padding_left = layout_box.box_metrics.padding_left
        padding_right = layout_box.box_metrics.padding_right
        margin_top = layout_box.box_metrics.margin_top
        border_top = layout_box.box_metrics.border_top_width
        padding_top = layout_box.box_metrics.padding_top
        
        # Convert string values to float, handling 'auto' as 0
        if isinstance(margin_left, str):
            margin_left = 0 if margin_left == 'auto' else float(margin_left)
        if isinstance(margin_right, str):
            margin_right = 0 if margin_right == 'auto' else float(margin_right)
        if isinstance(border_left, str):
            border_left = 0 if border_left == 'auto' else float(border_left)
        if isinstance(border_right, str):
            border_right = 0 if border_right == 'auto' else float(border_right)
        if isinstance(padding_left, str):
            padding_left = 0 if padding_left == 'auto' else float(padding_left)
        if isinstance(padding_right, str):
            padding_right = 0 if padding_right == 'auto' else float(padding_right)
        if isinstance(margin_top, str):
            margin_top = 0 if margin_top == 'auto' else float(margin_top)
        if isinstance(border_top, str):
            border_top = 0 if border_top == 'auto' else float(border_top)
        if isinstance(padding_top, str):
            padding_top = 0 if padding_top == 'auto' else float(padding_top)
        
        # Get content width safely
        content_width = layout_box.box_metrics.content_width
        if isinstance(content_width, str):
            if content_width == 'auto':
                content_width = container_width - padding_left - padding_right
            else:
                try:
                    content_width = float(content_width)
                except (ValueError, TypeError):
                    content_width = container_width - padding_left - padding_right
        elif isinstance(content_width, (int, float)):
            content_width = float(content_width)
        else:
            content_width = container_width - padding_left - padding_right
        
        # Adjust for content area
        content_x = layout_box.box_metrics.x + margin_left + border_left + padding_left
        content_y = layout_box.box_metrics.y + margin_top + border_top + padding_top
        
        # Available width for children
        if isinstance(layout_box.box_metrics.content_width, str) and layout_box.box_metrics.content_width == 'auto':
            # Default to a reasonable width if not specified
            child_container_width = content_width
            layout_box.box_metrics.content_width = child_container_width
            layout_box._update_box_dimensions()
        else:
            child_container_width = content_width
        
        # Current position within the content box
        current_x = content_x
        current_y = content_y
        line_height = 0
        
        # Determine if we're within a paragraph context
        is_paragraph = False
        if layout_box.element and hasattr(layout_box.element, 'tag_name'):
            is_paragraph = layout_box.element.tag_name.lower() in ['p', 'div', 'span', 'em', 'strong', 'i', 'b']
        
        # For non-paragraph contexts, use standard block or grid layout
        if not is_paragraph:
            # Default spacing for elements in non-paragraph contexts
            min_spacing = 10
            
            for child in layout_box.children:
                # Layout the child
                child.layout(child_container_width, current_x, current_y)
                
                # Get child dimensions
                child_width = 0
                if isinstance(child.box_metrics.margin_box_width, (int, float)):
                    child_width = float(child.box_metrics.margin_box_width)
                
                child_height = 0
                if isinstance(child.box_metrics.margin_box_height, (int, float)):
                    child_height = float(child.box_metrics.margin_box_height)
                
                # Move right for next child
                current_x += child_width + min_spacing
                
                # Update line height
                line_height = max(line_height, child_height)
            
            return
        
        # Special handling for paragraph context - continuous text flow with embedded links
        # First, collect all children to determine their content and layout needs
        paragraph_children = []
        
        for child in layout_box.children:
            child_info = {
                'child': child,
                'type': None,
                'text': '',
                'is_link': False,
                'width': 0,
                'height': 0
            }
            
            # Determine element type
            if child.element and hasattr(child.element, 'tag_name'):
                child_info['type'] = child.element.tag_name.lower()
                child_info['is_link'] = child_info['type'] == 'a'
            
            # Extract text content
            if child.element and hasattr(child.element, 'text_content') and child.element.text_content:
                child_info['text'] = child.element.text_content
            
            paragraph_children.append(child_info)
        
        # Now layout the children in a continuous flow
        max_width = content_width
        line_width = 0
        word_spacing = 2  # Small spacing between words
        
        for child_info in paragraph_children:
            child = child_info['child']
            
            # Calculate the child's width (temporary layout)
            child.layout(child_container_width, 0, 0)  # Temporary layout to get dimensions
            
            if isinstance(child.box_metrics.margin_box_width, (int, float)):
                child_width = float(child.box_metrics.margin_box_width)
            else:
                child_width = 0
                
            if isinstance(child.box_metrics.margin_box_height, (int, float)):
                child_height = float(child.box_metrics.margin_box_height)
            else:
                child_height = 0
            
            # Update child info
            child_info['width'] = child_width
            child_info['height'] = child_height
            
            # Check if we need to wrap to next line
            if line_width + child_width > max_width:
                # Move to next line
                current_x = content_x
                current_y += line_height + 2  # Small vertical spacing between lines
                line_width = 0
                line_height = 0
            
            # Position child at current position
            child.layout(child_container_width, current_x, current_y)
            
            # Update current position
            current_x += child_width + word_spacing
            line_width += child_width + word_spacing
            line_height = max(line_height, child_height)

    def create_layout_tree(self, document: Document) -> LayoutBox:
        """
        Create a layout tree for a document.
        
        Args:
            document: The document to create a layout tree for
            
        Returns:
            The root layout box
        """
        if not document.document_element:
            # Create an empty root box
            return LayoutBox()
        
        # Create the root layout box
        root_box = self._create_layout_box(document.document_element)
        
        # Process the document tree
        self._build_layout_tree(document.document_element, root_box)
        
        return root_box
    
    def _build_layout_tree(self, element, parent_box=None) -> LayoutBox:
        """
        Build a layout tree from an element tree.
        
        Args:
            element: The root element
            parent_box: Optional parent layout box
            
        Returns:
            Root of the layout tree
        """
        # Import LayoutBox if needed
        from browser_engine.html5_engine.layout.layout import LayoutBox
        
        # Create a layout box for this element
        display_type = 'block'  # Default display type
        if parent_box:
            display_type = parent_box.display
            
        layout_box = LayoutBox(element, display_type, parent_box)
        
        # Recursively add children
        if hasattr(element, 'child_nodes'):
            for child in element.child_nodes:
                # Skip non-element nodes for now (like text, comments, etc.)
                if hasattr(child, 'node_type') and child.node_type == 1:  # ELEMENT_NODE
                    child_box = self._build_layout_tree(child, layout_box)
                    layout_box.add_child(child_box)
                elif hasattr(child, 'node_type') and child.node_type == 3:  # TEXT_NODE
                    # Handle text nodes specially
                    # In a real browser, we would create anonymous boxes for text
                    # For simplicity, we'll just include the text in the parent's content
                    if hasattr(element, 'text_content'):
                        if hasattr(child, 'node_value'):
                            if not element.text_content:
                                element.text_content = child.node_value
                            else:
                                element.text_content += child.node_value
                        
        return layout_box
    
    def _create_layout_box(self, element: Element) -> LayoutBox:
        """
        Create a layout box for an element.
        
        Args:
            element: The DOM element
            
        Returns:
            The created layout box
        """
        box = LayoutBox(element)
        
        # Get computed style
        computed_style = self._get_computed_style(element)
        box.computed_style = computed_style
        
        # First check if it's a known block-level element by tag name
        is_block_element = False
        if hasattr(element, 'tag_name'):
            block_elements = [
                'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                'ul', 'ol', 'li', 'table', 'form', 'article', 'section',
                'header', 'footer', 'nav', 'aside', 'main', 'figure', 'figcaption',
                'blockquote', 'pre', 'address', 'hr', 'fieldset'
            ]
            if element.tag_name.lower() in block_elements:
                is_block_element = True
                
        # Set display type
        display_value = computed_style.get('display', 'inline').lower()
        
        # Override with block for known block elements, unless explicitly set to something else
        if is_block_element and display_value == 'inline':
            display_value = 'block'
            
        try:
            box.display = DisplayType(display_value)
        except ValueError:
            # Default to block for unknown display values
            box.display = DisplayType.BLOCK
        
        # Set position type
        position_value = computed_style.get('position', 'static').lower()
        try:
            box.position = PositionType(position_value)
        except ValueError:
            box.position = PositionType.STATIC
        
        # Set float type
        float_value = computed_style.get('float', 'none').lower()
        try:
            box.float_type = FloatType(float_value)
        except ValueError:
            box.float_type = FloatType.NONE
        
        # Apply box model properties
        self._apply_box_model(box, computed_style)
        
        return box
    
    def _get_computed_style(self, element: Element) -> Dict[str, str]:
        """
        Get the computed style for an element.
        
        Args:
            element: The DOM element
            
        Returns:
            Dictionary of computed style properties
        """
        # In a full implementation, this would use the CSS parser
        # to calculate the computed style based on the cascade.
        
        # For demo purposes, we'll extract inline styles and add defaults
        computed_style = self._get_default_styles(element)
        
        # Add inline styles (highest precedence)
        inline_styles = {}
        style_attr = element.get_attribute('style')
        if style_attr:
            inline_styles = self._parse_inline_styles(style_attr)
            
            for prop_name, prop_value in inline_styles.items():
                computed_style[prop_name] = prop_value
        
        return computed_style
    
    def _get_default_styles(self, element: Element) -> Dict[str, str]:
        """
        Get default styles based on element type.
        
        Args:
            element: The DOM element
            
        Returns:
            Dictionary of default style properties
        """
        tag_name = element.tag_name.lower()
        defaults = {
            'display': 'block',
            'margin-top': '0px',
            'margin-right': '0px',
            'margin-bottom': '0px',
            'margin-left': '0px',
            'padding-top': '8px',
            'padding-right': '8px',
            'padding-bottom': '8px',
            'padding-left': '8px',
            'border-top-width': '0px',
            'border-right-width': '0px',
            'border-bottom-width': '0px',
            'border-left-width': '0px',
            'position': 'static',
            'float': 'none',
            'line-height': '1.5',
            'font-size': '16px',
        }
        
        # Add tag-specific defaults with natural vertical spacing
        if tag_name == 'body':
            defaults.update({
                'margin-top': '24px',
                'margin-right': '24px',
                'margin-bottom': '24px',
                'margin-left': '24px',
                'line-height': '1.6',
            })
        # Block elements
        elif tag_name == 'div':
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '16px',
                'padding-top': '12px',
                'padding-bottom': '12px',
            })
        elif tag_name == 'p':
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '16px',
                'line-height': '1.6',
            })
        # Headings with progressively smaller margins and larger font sizes
        elif tag_name == 'h1':
            defaults.update({
                'margin-top': '32px',
                'margin-bottom': '24px',
                'line-height': '1.2',
                'font-size': '2.5em',
            })
        elif tag_name == 'h2':
            defaults.update({
                'margin-top': '28px',
                'margin-bottom': '20px',
                'line-height': '1.2',
                'font-size': '2em',
            })
        elif tag_name == 'h3':
            defaults.update({
                'margin-top': '24px',
                'margin-bottom': '16px',
                'line-height': '1.2',
                'font-size': '1.75em',
            })
        elif tag_name == 'h4':
            defaults.update({
                'margin-top': '20px',
                'margin-bottom': '12px',
                'line-height': '1.2',
                'font-size': '1.5em',
            })
        elif tag_name == 'h5':
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '12px',
                'line-height': '1.2',
                'font-size': '1.25em',
            })
        elif tag_name == 'h6':
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '12px',
                'line-height': '1.2',
                'font-size': '1.1em',
            })
        # Lists
        elif tag_name in ('ul', 'ol'):
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '16px',
                'padding-left': '40px',
            })
        elif tag_name == 'li':
            defaults.update({
                'margin-top': '8px',
                'margin-bottom': '8px',
                'line-height': '1.6',
            })
        # Table elements
        elif tag_name == 'table':
            defaults.update({
                'margin-top': '24px',
                'margin-bottom': '24px',
                'border-collapse': 'collapse',
            })
        # Form elements
        elif tag_name == 'form':
            defaults.update({
                'margin-top': '24px',
                'margin-bottom': '24px',
                'padding': '16px',
            })
        elif tag_name in ('input', 'button', 'textarea', 'select'):
            defaults.update({
                'margin-top': '8px',
                'margin-bottom': '8px',
                'padding': '8px',
                'line-height': '1.4',
            })
        # Inline elements
        elif tag_name == 'span':
            defaults.update({
                'display': 'inline',
                'padding': '0',
                'margin': '0',
            })
        # Image elements
        elif tag_name == 'img':
            defaults.update({
                'margin-top': '16px',
                'margin-bottom': '16px',
                'display': 'inline-block',
                'max-width': '100%',
                'height': 'auto',
            })
        # Add spacious margins for other structural elements
        elif tag_name in ('section', 'article', 'header', 'footer', 'nav', 'aside'):
            defaults.update({
                'margin-top': '24px',
                'margin-bottom': '24px',
                'padding': '16px',
            })
        # Horizontal rule gets extra margin
        elif tag_name == 'hr':
            defaults.update({
                'margin-top': '24px',
                'margin-bottom': '24px',
                'height': '1px',
                'background-color': '#cccccc',
                'border': 'none',
            })
        
        return defaults
    
    def _parse_inline_styles(self, style_attr: str) -> Dict[str, str]:
        """
        Parse an inline style attribute.
        
        Args:
            style_attr: Style attribute value
            
        Returns:
            Dictionary of style properties
        """
        style_dict = {}
        
        # Split the style attribute by semicolons
        declarations = [decl.strip() for decl in style_attr.split(';') if decl.strip()]
        
        for declaration in declarations:
            # Split each declaration into property and value
            parts = declaration.split(':', 1)
            if len(parts) == 2:
                property_name, value = parts
                style_dict[property_name.strip().lower()] = value.strip()
        
        return style_dict
    
    def _has_display_none(self, element: Element) -> bool:
        """Check if an element has display: none in its computed style."""
        if not element:
            return False
            
        if hasattr(element, 'computed_style'):
            return element.computed_style.get('display', '') == 'none'
        
        style = self._get_computed_style(element)
        return style.get('display', '') == 'none'
        
    def _get_display_type(self, element: Element) -> DisplayType:
        """
        Get the display type for an element based on its computed style.
        
        Args:
            element: The element to get the display type for
            
        Returns:
            The display type enum value
        """
        if not element:
            return DisplayType.BLOCK
            
        # Get computed style
        style = self._get_computed_style(element)
        display_value = style.get('display', 'block').lower()
        
        # Map to DisplayType enum
        if display_value == 'inline':
            return DisplayType.INLINE
        elif display_value == 'inline-block':
            return DisplayType.INLINE_BLOCK
        elif display_value == 'flex':
            return DisplayType.FLEX
        elif display_value == 'grid':
            return DisplayType.GRID
        elif display_value == 'none':
            return DisplayType.NONE
        elif display_value == 'table':
            return DisplayType.TABLE
        elif display_value == 'table-row':
            return DisplayType.TABLE_ROW
        elif display_value == 'table-cell':
            return DisplayType.TABLE_CELL
        else:
            # Default to block display
            return DisplayType.BLOCK
    
    def _apply_box_model(self, box: LayoutBox, computed_style: Dict[str, str]) -> None:
        """
        Apply box model properties to a layout box.
        
        Args:
            box: The layout box to update
            computed_style: The computed style dictionary
        """
        # Apply width and height
        width_value = computed_style.get('width')
        if width_value and width_value != 'auto':
            box.box_metrics.width = self._parse_dimension(width_value)
        
        height_value = computed_style.get('height')
        if height_value and height_value != 'auto':
            box.box_metrics.height = self._parse_dimension(height_value)
        
        # Apply padding
        box.box_metrics.padding_top = self._parse_dimension(computed_style.get('padding-top', '0px'))
        box.box_metrics.padding_right = self._parse_dimension(computed_style.get('padding-right', '0px'))
        box.box_metrics.padding_bottom = self._parse_dimension(computed_style.get('padding-bottom', '0px'))
        box.box_metrics.padding_left = self._parse_dimension(computed_style.get('padding-left', '0px'))
        
        # Apply border widths
        box.box_metrics.border_top_width = self._parse_dimension(computed_style.get('border-top-width', '0px'))
        box.box_metrics.border_right_width = self._parse_dimension(computed_style.get('border-right-width', '0px'))
        box.box_metrics.border_bottom_width = self._parse_dimension(computed_style.get('border-bottom-width', '0px'))
        box.box_metrics.border_left_width = self._parse_dimension(computed_style.get('border-left-width', '0px'))
        
        # Apply margins
        box.box_metrics.margin_top = self._parse_dimension(computed_style.get('margin-top', '0px'))
        box.box_metrics.margin_right = self._parse_dimension(computed_style.get('margin-right', '0px'))
        box.box_metrics.margin_bottom = self._parse_dimension(computed_style.get('margin-bottom', '0px'))
        box.box_metrics.margin_left = self._parse_dimension(computed_style.get('margin-left', '0px'))
    
    def _parse_dimension(self, value: Optional[str]) -> int:
        """
        Parse a CSS dimension value to pixels.
        
        Args:
            value: CSS dimension value (e.g., '10px', '2em')
            
        Returns:
            Integer pixel value, or 0 if the value is None or cannot be parsed
        """
        if not value:
            return 0
        
        # Extract the numeric part and unit
        match = re.match(r'^([-+]?[0-9]*\.?[0-9]+)([a-z%]*)$', value)
        if not match:
            return 0
        
        number, unit = match.groups()
        
        try:
            number_value = float(number)
            
            # Handle different units
            if unit == 'px' or unit == '':
                return int(number_value)
            elif unit == 'em':
                # Simplified: 1em = 16px
                return int(number_value * 16)
            elif unit == 'rem':
                # Simplified: 1rem = 16px
                return int(number_value * 16)
            elif unit == '%':
                # Percentage requires context, default to 0
                # In a full implementation, this would be calculated based on parent
                return 0
            elif unit == 'pt':
                # 1pt = 1.333px (approximately)
                return int(number_value * 1.333)
            
            # Default for unknown units
            return int(number_value)
            
        except ValueError:
            return 0
    
    def _layout_block(self, box: LayoutBox, container_width: int, container_height: int) -> Tuple[int, int]:
        """
        Perform block layout for a box.
        
        Args:
            box: The layout box
            container_width: Width of the container
            container_height: Height of the container
            
        Returns:
            Tuple of (width, height) of the laid out box
        """
        # Ensure box has proper width (block elements take full container width by default)
        if isinstance(box.box_metrics.content_width, str) and box.box_metrics.content_width == 'auto':
            box.box_metrics.content_width = container_width
            box._update_box_dimensions()
            
        # Ensure box has at least some height
        if not box.box_metrics.content_height or (isinstance(box.box_metrics.content_height, str) and box.box_metrics.content_height == 'auto'):
            box.box_metrics.content_height = 20  # Minimum reasonable height for empty blocks
            
        # Get content area dimensions
        padding_left = box.box_metrics.padding_left
        padding_top = box.box_metrics.padding_top
        
        if isinstance(padding_left, str):
            padding_left = 0 if padding_left == 'auto' else float(padding_left)
        if isinstance(padding_top, str):
            padding_top = 0 if padding_top == 'auto' else float(padding_top)
            
        # Current Y position for child layout
        current_y = padding_top
        max_width = 0
        
        # Layout children vertical stacking, regardless of their display property
        # Block layout forces children to stack vertically
        for child in box.children:
            # Position child at the current Y position, but always start at the left edge
            child_x = padding_left
            child_y = current_y
            
            # Layout the child
            child_width, child_height = self._calculate_layout(
                child, 
                box.box_metrics.content_width, 
                container_height, 
                box.box_metrics.x + child_x, 
                box.box_metrics.y + child_y
            )
            
            # Update maximum width
            max_width = max(max_width, child_width)
            
            # Always move down by the child's height to ensure vertical stacking
            # Add a minimum vertical spacing between block elements (10px)
            current_y += child_height + 10
        
        # Calculate height if not explicitly set
        if box.box_metrics.height is None or isinstance(box.box_metrics.height, str) and box.box_metrics.height == 'auto':
            box.box_metrics.height = current_y
            
        return (box.box_metrics.border_box_width, box.box_metrics.border_box_height)
    
    def _layout_inline(self, box: LayoutBox, container_width: int, container_height: int) -> Tuple[int, int]:
        """
        Perform inline layout for a box.
        
        Args:
            box: The layout box
            container_width: Width of the container
            container_height: Height of the container
            
        Returns:
            Tuple of (width, height) of the laid out box
        """
        # Simplified inline layout - in a full implementation, this would handle text flow
        # Current X and Y positions for child layout
        current_x = box.box_metrics.padding_left
        current_y = box.box_metrics.padding_top
        line_height = 0
        
        # Default minimum spacing between inline elements
        MINIMUM_INLINE_SPACING = 5
        
        for child in box.children:
            # Check if we need to wrap to next line
            try:
                if (current_x + float(child.box_metrics.margin_box_width) > float(box.box_metrics.width)):
                    current_x = box.box_metrics.padding_left
                    current_y += line_height
                    line_height = 0
            except:
                pass
            
            # Layout the child
            child_width, child_height = self._calculate_layout(
                child, 
                box.box_metrics.width - current_x, 
                container_height, 
                box.box_metrics.x + current_x, 
                box.box_metrics.y + current_y
            )
            
            # Move right for next child
            # Add minimum spacing if no margins are defined
            margin_spacing = child.box_metrics.margin_left + child.box_metrics.margin_right
            if margin_spacing == 0:
                margin_spacing = MINIMUM_INLINE_SPACING
                
            current_x += child_width + margin_spacing
            
            # Update line height
            line_height = max(line_height, child_height + child.box_metrics.margin_top + child.box_metrics.margin_bottom)
        
        # Calculate height if not explicitly set
        if box.box_metrics.height is None:
            box.box_metrics.height = current_y + line_height
        
        return (box.box_metrics.border_box_width, box.box_metrics.border_box_height)
    
    def _layout_flex(self, box: LayoutBox, container_width: int, container_height: int) -> Tuple[int, int]:
        """
        Perform flexbox layout for a box.
        
        Args:
            box: The layout box
            container_width: Width of the container
            container_height: Height of the container
            
        Returns:
            Tuple of (width, height) of the laid out box
        """
        # Simplified flex layout - in a full implementation, this would handle flex properties
        # Get flex direction
        flex_direction = box.computed_style.get('flex-direction', 'row')
        
        if flex_direction in ('row', 'row-reverse'):
            # Current X and Y positions for child layout
            current_x = box.box_metrics.padding_left
            current_y = box.box_metrics.padding_top
            max_height = 0
            
            # Determine layout direction
            children = box.children
            if flex_direction == 'row-reverse':
                children = list(reversed(children))
            
            for child in children:
                # Layout the child
                child_width, child_height = self._calculate_layout(
                    child, 
                    container_width, 
                    container_height, 
                    box.box_metrics.x + current_x, 
                    box.box_metrics.y + current_y
                )
                
                # Move right for next child
                current_x += child_width + child.box_metrics.margin_left + child.box_metrics.margin_right
                
                # Update max height
                max_height = max(max_height, child_height + child.box_metrics.margin_top + child.box_metrics.margin_bottom)
            
            # Calculate height if not explicitly set
            if box.box_metrics.height is None:
                box.box_metrics.height = max_height
                
        else:  # column or column-reverse
            # Current X and Y positions for child layout
            current_x = box.box_metrics.padding_left
            current_y = box.box_metrics.padding_top
            max_width = 0
            
            # Determine layout direction
            children = box.children
            if flex_direction == 'column-reverse':
                children = list(reversed(children))
            
            for child in children:
                # Layout the child
                child_width, child_height = self._calculate_layout(
                    child, 
                    container_width, 
                    container_height, 
                    box.box_metrics.x + current_x, 
                    box.box_metrics.y + current_y
                )
                
                # Move down for next child
                current_y += child_height + child.box_metrics.margin_top + child.box_metrics.margin_bottom
                
                # Update max width
                max_width = max(max_width, child_width + child.box_metrics.margin_left + child.box_metrics.margin_right)
            
            # Calculate width if not explicitly set
            if box.box_metrics.width is None:
                box.box_metrics.width = max_width
        
        return (box.box_metrics.border_box_width, box.box_metrics.border_box_height)
    
    def _calculate_layout(self, box: LayoutBox, container_width: int, container_height: int, 
                          start_x: int, start_y: int) -> Tuple[int, int]:
        """
        Calculate layout for a box and its children.
        
        Args:
            box: The layout box
            container_width: Width of the containing block
            container_height: Height of the container
            start_x: Starting X position
            start_y: Starting Y position
            
        Returns:
            Tuple of (width, height) of the laid out box
        """
        # Set initial position
        box.box_metrics.x = start_x
        box.box_metrics.y = start_y
        
        # Get box dimensions from style
        width = self._parse_dimension(box.computed_style.get('width', '0'))
        height = self._parse_dimension(box.computed_style.get('height', '0'))
        
        # If width or height is auto/percentage, calculate based on container
        if isinstance(width, str):
            if width == 'auto':
                width = 0
            elif width.endswith('%'):
                try:
                    percentage = float(width[:-1]) / 100
                    width = int(container_width * percentage)
                except (ValueError, TypeError):
                    width = 0
            else:
                try:
                    width = float(width)
                except (ValueError, TypeError):
                    width = 0
        
        if isinstance(height, str):
            if height == 'auto':
                height = 0
            elif height.endswith('%'):
                try:
                    percentage = float(height[:-1]) / 100
                    height = int(container_height * percentage)
                except (ValueError, TypeError):
                    height = 0
            else:
                try:
                    height = float(height)
                except (ValueError, TypeError):
                    height = 0
        
        # Calculate content width based on display type
        if width == 0:
            if box.display == DisplayType.BLOCK:
                # Block elements take full container width
                box.box_metrics.content_width = container_width
            elif box.display == DisplayType.INLINE:
                # Inline elements size to content
                if box.element and hasattr(box.element, 'text_content') and box.element.text_content:
                    # Calculate width based on text content
                    text_length = len(box.element.text_content)
                    font_size = self._parse_dimension(box.computed_style.get('font-size', '16px'))
                    if isinstance(font_size, str):
                        font_size = 16 if font_size == 'auto' else float(font_size)
                    
                    # Rough estimate: each character is about 0.6 times the font size width
                    box.box_metrics.content_width = int(text_length * font_size * 0.6)
                else:
                    # Minimum width for empty inline elements
                    box.box_metrics.content_width = 0
            else:
                # Inline elements use a percentage of container width
                box.box_metrics.content_width = int(container_width * 0.8)  # 80% of container width
        
        # Update box dimensions
        try:
            box._update_box_dimensions()
        except Exception as e:
            logger.error(f"Error updating box dimensions: {e}")
        
        # Calculate layout based on display type
        if box.display == DisplayType.NONE:
            # Don't layout children for display: none elements
            return (0, 0)
        elif box.display == DisplayType.BLOCK:
            return self._layout_block(box, container_width, container_height)
        elif box.display == DisplayType.INLINE:
            return self._layout_inline(box, container_width, container_height)
        elif box.display == DisplayType.FLEX:
            return self._layout_flex(box, container_width, container_height)
        elif box.display == DisplayType.GRID:
            # Simplified grid layout for now
            return self._layout_block(box, container_width, container_height)
        elif box.display in [DisplayType.TABLE, DisplayType.TABLE_ROW, DisplayType.TABLE_CELL]:
            # Simplified table layout for now
            return self._layout_block(box, container_width, container_height)
        else:
            # Default to block layout for other display types
            return self._layout_block(box, container_width, container_height)
    
    def _calculate_box_dimensions(self, layout_box: LayoutBox, viewport_width: int, viewport_height: int) -> None:
        """
        Calculate dimensions for a layout box.
        
        Args:
            layout_box: Layout box to calculate dimensions for
            viewport_width: Width of the viewport
            viewport_height: Height of the viewport
        """
        # Check if content dimensions are specified in the style
        styles = layout_box.computed_style
        
        # Get width and height from styles
        width = self._parse_dimension(styles.get('width', 'auto'))
        height = self._parse_dimension(styles.get('height', 'auto'))
        
        # Calculate box model properties
        margin_top = self._parse_dimension(styles.get('margin-top', '0'))
        margin_right = self._parse_dimension(styles.get('margin-right', '0'))
        margin_bottom = self._parse_dimension(styles.get('margin-bottom', '0'))
        margin_left = self._parse_dimension(styles.get('margin-left', '0'))
        
        padding_top = self._parse_dimension(styles.get('padding-top', '0'))
        padding_right = self._parse_dimension(styles.get('padding-right', '0'))
        padding_bottom = self._parse_dimension(styles.get('padding-bottom', '0'))
        padding_left = self._parse_dimension(styles.get('padding-left', '0'))
        
        border_top = self._parse_dimension(styles.get('border-top-width', '0'))
        border_right = self._parse_dimension(styles.get('border-right-width', '0'))
        border_bottom = self._parse_dimension(styles.get('border-bottom-width', '0'))
        border_left = self._parse_dimension(styles.get('border-left-width', '0'))
        
        # Update the box metrics
        layout_box.box_metrics.width = width
        layout_box.box_metrics.height = height
        
        layout_box.box_metrics.margin_top = margin_top
        layout_box.box_metrics.margin_right = margin_right
        layout_box.box_metrics.margin_bottom = margin_bottom
        layout_box.box_metrics.margin_left = margin_left
        
        layout_box.box_metrics.padding_top = padding_top
        layout_box.box_metrics.padding_right = padding_right
        layout_box.box_metrics.padding_bottom = padding_bottom
        layout_box.box_metrics.padding_left = padding_left
        
        layout_box.box_metrics.border_top_width = border_top
        layout_box.box_metrics.border_right_width = border_right
        layout_box.box_metrics.border_bottom_width = border_bottom
        layout_box.box_metrics.border_left_width = border_left
        
        # Update content dimensions
        if width != 'auto':
            layout_box.box_metrics.content_width = width
        else:
            # For block elements, default to full width of container minus margins
            if layout_box.display == 'block':
                layout_box.box_metrics.content_width = viewport_width - margin_left - margin_right - padding_left - padding_right - border_left - border_right
            else:
                # For inline elements, content determines width (will be calculated later)
                layout_box.box_metrics.content_width = 'auto'
        
        if height != 'auto':
            layout_box.box_metrics.content_height = height
        else:
            # Height will be calculated based on content
            layout_box.box_metrics.content_height = 'auto'

    def create_layout_for_element(self, element, viewport_width=800, viewport_height=600):
        """
        Create a layout tree for a specific element.
        
        Args:
            element: The element to create layout for
            viewport_width: Width of the viewport
            viewport_height: Height of the viewport
            
        Returns:
            The root layout box for the element
        """
        # Create a layout box for the element
        layout_box = LayoutBox(element)
        
        # Set initial dimensions
        layout_box.box_metrics.width = viewport_width
        
        # If this is the body element, treat it as a block
        if hasattr(element, 'tag_name') and element.tag_name.lower() == 'body':
            layout_box.box_type = BoxType.BLOCK
        else:
            # Determine box type based on display property
            display = self._get_display_type(element)
            if display == DisplayType.BLOCK:
                layout_box.box_type = BoxType.BLOCK
            elif display == DisplayType.INLINE_BLOCK:
                layout_box.box_type = BoxType.INLINE_BLOCK
            else:
                layout_box.box_type = BoxType.INLINE
        
        # Set up computed styles
        layout_box.computed_style = self._get_computed_style(element)
        
        # Process children
        if hasattr(element, 'child_nodes'):
            for child in element.child_nodes:
                # Only process element nodes
                if hasattr(child, 'node_type') and child.node_type == 1:  # Element node
                    child_box = self.create_layout_for_element(child, viewport_width)
                    layout_box.children.append(child_box)
                    child_box.parent = layout_box
        
        return layout_box

class GridLayoutEngine:
    """
    Engine for handling CSS Grid layout calculations.
    """
    
    def __init__(self, parent_width, parent_height):
        """
        Initialize the grid layout engine.
        
        Args:
            parent_width: Width of the parent container
            parent_height: Height of the parent container
        """
        self.parent_width = parent_width
        self.parent_height = parent_height
        self.columns = []
        self.rows = []
        self.grid_items = []
        
    def parse_grid_container(self, element, computed_style):
        """
        Parse grid container properties.
        
        Args:
            element: The container element
            computed_style: The computed style for the element
        """
        # Parse grid-template-columns
        grid_template_columns = computed_style.get('grid-template-columns', 'none')
        self.columns = self._parse_track_list(grid_template_columns, self.parent_width)
        
        # Parse grid-template-rows
        grid_template_rows = computed_style.get('grid-template-rows', 'none')
        self.rows = self._parse_track_list(grid_template_rows, self.parent_height)
        
        # Set defaults if not specified
        if not self.columns:
            # Default to a single column that takes up 100% width
            self.columns = [('fr', 1)]
        
        if not self.rows:
            # Default to rows with auto height
            self.rows = [('auto', None)]
        
        # Parse grid-gap properties
        self.column_gap = self._parse_gap(computed_style.get('grid-column-gap', '0px'))
        self.row_gap = self._parse_gap(computed_style.get('grid-row-gap', '0px'))
        
        # For shorthand
        grid_gap = computed_style.get('grid-gap', None)
        if grid_gap:
            gaps = grid_gap.split()
            if len(gaps) == 1:
                # Same gap for rows and columns
                self.row_gap = self.column_gap = self._parse_gap(gaps[0])
            elif len(gaps) >= 2:
                # Different gaps for rows and columns
                self.row_gap = self._parse_gap(gaps[0])
                self.column_gap = self._parse_gap(gaps[1])
    
    def add_grid_item(self, element, computed_style):
        """
        Add a grid item to the layout calculation.
        
        Args:
            element: The grid item element
            computed_style: The computed style for the element
        """
        # Parse grid-column and grid-row
        grid_column = computed_style.get('grid-column', None)
        grid_row = computed_style.get('grid-row', None)
        
        # Default positioning
        column_start = 1
        column_end = 2
        row_start = 1
        row_end = 2
        
        # Parse grid-column
        if grid_column:
            column_positions = grid_column.split('/')
            if len(column_positions) >= 2:
                column_start = self._parse_grid_line(column_positions[0])
                column_end = self._parse_grid_line(column_positions[1])
            elif len(column_positions) == 1:
                column_start = self._parse_grid_line(column_positions[0])
                column_end = column_start + 1
        
        # Parse grid-row
        if grid_row:
            row_positions = grid_row.split('/')
            if len(row_positions) >= 2:
                row_start = self._parse_grid_line(row_positions[0])
                row_end = self._parse_grid_line(row_positions[1])
            elif len(row_positions) == 1:
                row_start = self._parse_grid_line(row_positions[0])
                row_end = row_start + 1
        
        # Add the item to the grid
        self.grid_items.append({
            'element': element,
            'column_start': column_start,
            'column_end': column_end,
            'row_start': row_start,
            'row_end': row_end,
            'computed_style': computed_style
        })
    
    def calculate_layout(self):
        """
        Calculate the layout positions and dimensions for all grid items.
        
        Returns:
            Dictionary mapping elements to their calculated positions and dimensions
        """
        # Calculate column widths
        column_widths = self._calculate_track_sizes(self.columns, self.parent_width, self.column_gap)
        
        # Calculate row heights
        row_heights = self._calculate_track_sizes(self.rows, self.parent_height, self.row_gap)
        
        # Extend rows if needed (implicit grid)
        max_row_end = max([item['row_end'] for item in self.grid_items], default=1)
        while len(row_heights) < max_row_end:
            row_heights.append(2)  # Default height for implicit rows
        
        # Extend columns if needed (implicit grid)
        max_column_end = max([item['column_end'] for item in self.grid_items], default=1)
        while len(column_widths) < max_column_end:
            column_widths.append(2)  # Default width for implicit columns
        
        # Calculate positions for each grid item
        layout_result = {}
        
        for item in self.grid_items:
            element = item['element']
            col_start = max(0, min(item['column_start'] - 1, len(column_widths) - 1))
            col_end = max(col_start + 1, min(item['column_end'] - 1, len(column_widths)))
            row_start = max(0, min(item['row_start'] - 1, len(row_heights) - 1))
            row_end = max(row_start + 1, min(item['row_end'] - 1, len(row_heights)))
            
            # Calculate x coordinate (sum of column widths and gaps before this column)
            x = sum(column_widths[:col_start]) + (col_start * self.column_gap)
            
            # Calculate y coordinate (sum of row heights and gaps before this row)
            y = sum(row_heights[:row_start]) + (row_start * self.row_gap)
            
            # Calculate width (sum of column widths in the span)
            width = sum(column_widths[col_start:col_end]) + ((col_end - col_start - 1) * self.column_gap)
            
            # Calculate height (sum of row heights in the span)
            height = sum(row_heights[row_start:row_end]) + ((row_end - row_start - 1) * self.row_gap)
            
            # Store the layout information
            layout_result[element] = {
                'x': x,
                'y': y,
                'width': width,
                'height': height
            }
        
        return layout_result
    
    def _parse_track_list(self, track_list_str, container_size):
        """
        Parse a grid track list (grid-template-columns or grid-template-rows).
        
        Args:
            track_list_str: The track list string
            container_size: The container dimension (width or height)
            
        Returns:
            List of track sizes
        """
        if not track_list_str or track_list_str == 'none':
            return []
        
        tracks = []
        for track in track_list_str.split():
            if track.endswith('px'):
                # Pixel values
                try:
                    value = int(track[:-2])
                    tracks.append(('px', value))
                except ValueError:
                    tracks.append(('px', 0))
            elif track.endswith('%'):
                # Percentage values
                try:
                    percentage = float(track[:-1]) / 100
                    value = container_size * percentage
                    tracks.append(('percentage', value))
                except ValueError:
                    tracks.append(('percentage', 0))
            elif track.endswith('fr'):
                # Fractional units
                try:
                    value = float(track[:-2])
                    tracks.append(('fr', value))
                except ValueError:
                    tracks.append(('fr', 1))
            elif track == 'auto':
                # Auto sizing
                tracks.append(('auto', None))
            else:
                # Default to auto if unrecognized
                tracks.append(('auto', None))
        
        return tracks
    
    def _parse_gap(self, gap_str):
        """
        Parse a grid gap value.
        
        Args:
            gap_str: The gap string
            
        Returns:
            Gap size in pixels
        """
        if not gap_str:
            return 0
        
        if gap_str.endswith('px'):
            try:
                return int(gap_str[:-2])
            except ValueError:
                return 0
        elif gap_str.endswith('%'):
            try:
                percentage = float(gap_str[:-1]) / 100
                # Use container's main axis for percentage calculations
                container_size = self.parent_width if self.direction in ['row', 'row-reverse'] else self.parent_height
                return container_size * percentage
            except ValueError:
                return 0
        else:
            # Default for unrecognized values
            return 0
    
    def _parse_grid_line(self, line_str):
        """
        Parse a grid line value.
        
        Args:
            line_str: The grid line string
            
        Returns:
            Line number
        """
        line_str = line_str.strip()
        
        if line_str == 'auto':
            return 1  # Default to first line
        
        try:
            return int(line_str)
        except ValueError:
            # For named lines or spans, default to 1 (simplified implementation)
            return 1
    
    def _calculate_track_sizes(self, tracks, container_size, gap):
        """
        Calculate the actual sizes for grid tracks.
        
        Args:
            tracks: List of track definitions
            container_size: The container dimension (width or height)
            gap: The gap between tracks
            
        Returns:
            List of track sizes in pixels
        """
        # First, handle all fixed sizes (px, %) and calculate remaining space
        fixed_sizes = []
        total_fr = 0
        auto_count = 0
        
        for track_type, track_value in tracks:
            if track_type == 'px':
                fixed_sizes.append(track_value)
            elif track_type == 'percentage':
                fixed_sizes.append(track_value)
            elif track_type == 'fr':
                fixed_sizes.append(0)  # Placeholder for fr units
                total_fr += track_value
            else:  # auto
                fixed_sizes.append(0)  # Placeholder for auto
                auto_count += 1
        
        # Calculate total fixed size including gaps
        total_fixed_size = sum(fixed_sizes)
        try:
            total_gap_size = float(gap) * (len(tracks) - 1) if len(tracks) > 0 else 0
        except:
            total_gap_size = 0
        
        # Calculate remaining space for fr units and auto tracks
        remaining_space = max(0, container_size - total_fixed_size - total_gap_size)
        
        # Distribute remaining space proportionally among fr units
        try:
            fr_unit_size = remaining_space / total_fr if total_fr > 0 else 0
        except:
            fr_unit_size = 0
        
        # Assign auto tracks a default size (share remaining space equally)
        try:
            auto_size = remaining_space / auto_count if auto_count > 0 else 0
        except:
            auto_size = 0
        
        # Calculate final sizes
        final_sizes = []
        for i, (track_type, track_value) in enumerate(tracks):
            if track_type == 'px' or track_type == 'percentage':
                final_sizes.append(fixed_sizes[i])
            elif track_type == 'fr':
                final_sizes.append(fr_unit_size * track_value)
            else:  # auto
                final_sizes.append(auto_size)
        
        return final_sizes

class FlexboxLayoutEngine:
    """
    Engine for handling CSS Flexbox layout calculations.
    """
    
    def __init__(self, parent_width, parent_height):
        """
        Initialize the flexbox layout engine.
        
        Args:
            parent_width: Width of the parent container
            parent_height: Height of the parent container
        """
        self.parent_width = parent_width
        self.parent_height = parent_height
        self.flex_items = []
        
        # Default flexbox properties
        self.direction = 'row'
        self.wrap = 'nowrap'
        self.justify_content = 'flex-start'
        self.align_items = 'stretch'
        self.align_content = 'stretch'
        self.gap = 0
    
    def parse_flex_container(self, element, computed_style):
        """
        Parse flexbox container properties.
        
        Args:
            element: The container element
            computed_style: The computed style for the element
        """
        # Parse flex-direction
        self.direction = computed_style.get('flex-direction', 'row')
        
        # Parse flex-wrap
        self.wrap = computed_style.get('flex-wrap', 'nowrap')
        
        # Parse justify-content
        self.justify_content = computed_style.get('justify-content', 'flex-start')
        
        # Parse align-items
        self.align_items = computed_style.get('align-items', 'stretch')
        
        # Parse align-content
        self.align_content = computed_style.get('align-content', 'stretch')
        
        # Parse gap
        self.gap = self._parse_gap(computed_style.get('gap', '0px'))
    
    def add_flex_item(self, element, computed_style, intrinsic_width, intrinsic_height):
        """
        Add a flex item to the layout calculation.
        
        Args:
            element: The flex item element
            computed_style: The computed style for the element
            intrinsic_width: The intrinsic (content) width of the element
            intrinsic_height: The intrinsic (content) height of the element
        """
        # Parse flex properties
        flex_grow = float(computed_style.get('flex-grow', '0'))
        flex_shrink = float(computed_style.get('flex-shrink', '1'))
        flex_basis = self._parse_flex_basis(computed_style.get('flex-basis', 'auto'), 
                                          intrinsic_width, intrinsic_height)
        
        # Parse margin
        margin = {
            'top': self._parse_margin(computed_style.get('margin-top', '0px')),
            'right': self._parse_margin(computed_style.get('margin-right', '0px')),
            'bottom': self._parse_margin(computed_style.get('margin-bottom', '0px')),
            'left': self._parse_margin(computed_style.get('margin-left', '0px')),
        }
        
        # Handle margin shorthand
        margin_shorthand = computed_style.get('margin', None)
        if margin_shorthand:
            margin_values = margin_shorthand.split()
            if len(margin_values) == 1:
                # Same margin for all sides
                margin_value = self._parse_margin(margin_values[0])
                margin = {'top': margin_value, 'right': margin_value, 
                          'bottom': margin_value, 'left': margin_value}
            elif len(margin_values) == 2:
                # Vertical and horizontal margins
                margin_vertical = self._parse_margin(margin_values[0])
                margin_horizontal = self._parse_margin(margin_values[1])
                margin = {'top': margin_vertical, 'right': margin_horizontal, 
                          'bottom': margin_vertical, 'left': margin_horizontal}
            elif len(margin_values) == 4:
                # All four sides specified separately
                margin = {
                    'top': self._parse_margin(margin_values[0]),
                    'right': self._parse_margin(margin_values[1]),
                    'bottom': self._parse_margin(margin_values[2]),
                    'left': self._parse_margin(margin_values[3]),
                }
        
        # Parse align-self (overrides align-items for this specific item)
        align_self = computed_style.get('align-self', 'auto')
        
        # Parse order
        try:
            order = int(computed_style.get('order', '0'))
        except ValueError:
            order = 0
        
        # Add the item to the flex container
        self.flex_items.append({
            'element': element,
            'flex_grow': flex_grow,
            'flex_shrink': flex_shrink,
            'flex_basis': flex_basis,
            'margin': margin,
            'align_self': align_self,
            'order': order,
            'intrinsic_width': intrinsic_width,
            'intrinsic_height': intrinsic_height,
            'computed_style': computed_style
        })
    
    def calculate_layout(self):
        """
        Calculate the layout positions and dimensions for all flex items.
        
        Returns:
            Dictionary mapping elements to their calculated positions and dimensions
        """
        # Sort items by order property
        sorted_items = sorted(self.flex_items, key=lambda item: item['order'])
        
        # Determine if we're working on the main or cross axis
        is_row = self.direction in ['row', 'row-reverse']
        is_reversed = self.direction in ['row-reverse', 'column-reverse']
        
        # Determine main axis and cross axis dimensions
        main_axis_size = self.parent_width if is_row else self.parent_height
        cross_axis_size = self.parent_height if is_row else self.parent_width
        
        # Calculate total flex basis and total flex grow units
        total_flex_basis = sum(item['flex_basis'] for item in sorted_items)
        try:
            total_flex_basis += float(self.gap) * (len(sorted_items) - 1) if len(sorted_items) > 0 else 0
        except:
            total_flex_basis += 0
        
        total_flex_grow = sum(item['flex_grow'] for item in sorted_items)
        
        # Calculate free space
        free_space = main_axis_size - total_flex_basis
        
        # Handle flex items
        layout_result = {}
        main_axis_position = 0
        
        for item in sorted_items:
            element = item['element']
            
            # Calculate main axis dimension
            try:
                if float(free_space) > 0 and float(total_flex_grow) > 0:
                    # Distribute extra space according to flex-grow
                    main_axis_dimension = float(item['flex_basis']) + (float(free_space) * (float(item['flex_grow']) / float(total_flex_grow)))
                elif float(free_space) < 0:
                    # Shrink items according to flex-shrink
                    shrink_ratio = item['flex_shrink'] / sum(i['flex_shrink'] for i in sorted_items)
                    main_axis_dimension = float(item['flex_basis']) + (free_space * shrink_ratio)
            except:
                main_axis_dimension = item['flex_basis']
            
            
            
            # Calculate cross axis dimension (using align-items or align-self)
            align = item['align_self'] if item['align_self'] != 'auto' else self.align_items
            
            if align == 'stretch':
                cross_axis_dimension = cross_axis_size
            else:
                # Use intrinsic dimensions for non-stretch alignment
                cross_axis_dimension = item['intrinsic_height'] if is_row else item['intrinsic_width']
            
            # Calculate cross axis position based on alignment
            if align == 'flex-start':
                cross_axis_position = 0
            elif align == 'flex-end':
                cross_axis_position = cross_axis_size - cross_axis_dimension
            elif align == 'center':
                cross_axis_position = (cross_axis_size - cross_axis_dimension) / 2
            else:  # stretch or baseline (simplified)
                cross_axis_position = 0
            
            # Handle main axis positioning based on direction
            if is_reversed:
                main_axis_position_effective = main_axis_size - main_axis_position - main_axis_dimension
            else:
                main_axis_position_effective = main_axis_position
            
            # Set x and y based on direction
            if is_row:
                x = main_axis_position_effective
                y = cross_axis_position
                width = main_axis_dimension
                height = cross_axis_dimension
            else:
                x = cross_axis_position
                y = main_axis_position_effective
                width = cross_axis_dimension
                height = main_axis_dimension
            
            # Store the layout information
            layout_result[element] = {
                'x': x,
                'y': y,
                'width': width,
                'height': height
            }
            
            # Move position for next item
            main_axis_position += main_axis_dimension + self.gap
        
        return layout_result
    
    def _parse_flex_basis(self, basis_str, intrinsic_width, intrinsic_height):
        """
        Parse a flex-basis value.
        
        Args:
            basis_str: The flex-basis string
            intrinsic_width: The intrinsic width of the element
            intrinsic_height: The intrinsic height of the element
            
        Returns:
            Flex basis in pixels
        """
        if basis_str == 'auto':
            # Use intrinsic size based on direction
            return intrinsic_width if self.direction in ['row', 'row-reverse'] else intrinsic_height
        
        if basis_str.endswith('px'):
            try:
                return float(basis_str[:-2])
            except ValueError:
                return 0
        elif basis_str.endswith('%'):
            try:
                percentage = float(basis_str[:-1]) / 100
                # Use container's main axis size for percentage calculations
                container_size = self.parent_width if self.direction in ['row', 'row-reverse'] else self.parent_height
                return container_size * percentage
            except ValueError:
                return 0
        else:
            # For other units (not implemented), default to auto
            return intrinsic_width if self.direction in ['row', 'row-reverse'] else intrinsic_height
    
    def _parse_margin(self, margin_str):
        """
        Parse a margin value.
        
        Args:
            margin_str: The margin string
            
        Returns:
            Margin size in pixels
        """
        if margin_str == 'auto':
            return 'auto'
        
        if margin_str.endswith('px'):
            try:
                return float(margin_str[:-2])
            except ValueError:
                return 0
        elif margin_str.endswith('%'):
            try:
                percentage = float(margin_str[:-1]) / 100
                # Use container width for percentage calculations
                return self.parent_width * percentage
            except ValueError:
                return 0
        else:
            # Default for unrecognized values
            return 0
    
    def _parse_gap(self, gap_str):
        """
        Parse a gap value.
        
        Args:
            gap_str: The gap string
            
        Returns:
            Gap size in pixels
        """
        if gap_str.endswith('px'):
            try:
                return float(gap_str[:-2])
            except ValueError:
                return 0
        elif gap_str.endswith('%'):
            try:
                percentage = float(gap_str[:-1]) / 100
                # Use container's main axis for percentage calculations
                container_size = self.parent_width if self.direction in ['row', 'row-reverse'] else self.parent_height
                return container_size * percentage
            except ValueError:
                return 0
        else:
            # Default for unrecognized values
            return 0 