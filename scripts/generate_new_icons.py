#!/usr/bin/env python3
"""
Generate new ASUC icons for AUR package
Creates icons with Arch pyramid inside conversion/refresh symbol
"""

import os
from PIL import Image, ImageDraw
import math

def create_arch_pyramid_icon(size):
    """Create ASUC icon with Arch pyramid inside conversion arrows"""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    center = size // 2
    outer_radius = int(size * 0.4)  # Conversion arrows radius
    inner_radius = int(size * 0.25)  # Inner circle radius
    
    # Arch Linux colors
    arch_blue = (13, 71, 161, 255)  # #0D47A1
    arch_light_blue = (25, 118, 210, 255)  # #1976D2
    arch_dark_blue = (2, 20, 64, 255)  # #021440
    
    # Draw conversion arrows (circular refresh symbol)
    arrow_thickness = max(2, size // 32)
    
    # Outer circle for arrows
    draw.ellipse([center - outer_radius, center - outer_radius,
                  center + outer_radius, center + outer_radius],
                 outline=arch_blue, width=arrow_thickness)
    
    # Draw two circular arrows (conversion symbol)
    arrow_radius = outer_radius - arrow_thickness // 2
    arrow_start = -math.pi / 4
    arrow_end = 3 * math.pi / 4
    
    # First arrow (clockwise)
    bbox = [center - arrow_radius, center - arrow_radius,
            center + arrow_radius, center + arrow_radius]
    draw.arc(bbox, start=arrow_start * 180 / math.pi, 
             end=arrow_end * 180 / math.pi, 
             fill=arch_blue, width=arrow_thickness)
    
    # Arrow head for first arrow
    head_angle = arrow_end
    head_x = center + arrow_radius * math.cos(head_angle)
    head_y = center + arrow_radius * math.sin(head_angle)
    head_size = arrow_radius * 0.15
    
    head_points = [
        (head_x, head_y),
        (head_x - head_size * math.cos(head_angle + math.pi / 2), 
         head_y - head_size * math.sin(head_angle + math.pi / 2)),
        (head_x - head_size * math.cos(head_angle + math.pi / 2 - math.pi / 6), 
         head_y - head_size * math.sin(head_angle + math.pi / 2 - math.pi / 6))
    ]
    draw.polygon(head_points, fill=arch_blue)
    
    # Second arrow (counter-clockwise) - smaller and offset
    arrow2_radius = arrow_radius * 0.7
    arrow2_start = arrow_start + math.pi
    arrow2_end = arrow_end + math.pi
    
    bbox2 = [center - arrow2_radius, center - arrow2_radius,
             center + arrow2_radius, center + arrow2_radius]
    draw.arc(bbox2, start=arrow2_start * 180 / math.pi, 
             end=arrow2_end * 180 / math.pi, 
             fill=arch_light_blue, width=arrow_thickness)
    
    # Arrow head for second arrow
    head2_angle = arrow2_end
    head2_x = center + arrow2_radius * math.cos(head2_angle)
    head2_y = center + arrow2_radius * math.sin(head2_angle)
    head2_size = arrow2_radius * 0.15
    
    head2_points = [
        (head2_x, head2_y),
        (head2_x - head2_size * math.cos(head2_angle + math.pi / 2), 
         head2_y - head2_size * math.sin(head2_angle + math.pi / 2)),
        (head2_x - head2_size * math.cos(head2_angle + math.pi / 2 - math.pi / 6), 
         head2_y - head2_size * math.sin(head2_angle + math.pi / 2 - math.pi / 6))
    ]
    draw.polygon(head2_points, fill=arch_light_blue)
    
    # Draw Arch pyramid in the center
    pyramid_size = inner_radius * 0.8
    pyramid_top = center - pyramid_size // 2
    pyramid_bottom = center + pyramid_size // 2
    pyramid_left = center - pyramid_size // 2
    pyramid_right = center + pyramid_size // 2
    
    # Pyramid points (triangle)
    pyramid_points = [
        (center, pyramid_top),  # Top point
        (pyramid_left, pyramid_bottom),  # Bottom left
        (pyramid_right, pyramid_bottom)  # Bottom right
    ]
    
    # Draw pyramid with gradient effect
    draw.polygon(pyramid_points, fill=arch_dark_blue)
    
    # Add pyramid details (lines for 3D effect)
    line_color = (255, 255, 255, 180)
    line_width = max(1, size // 64)
    
    # Center line
    draw.line([(center, pyramid_top), (center, pyramid_bottom)], 
              fill=line_color, width=line_width)
    
    # Side lines for 3D effect
    side_offset = pyramid_size // 6
    draw.line([(center - side_offset, pyramid_top + pyramid_size // 4), 
               (center - side_offset, pyramid_bottom)], 
              fill=line_color, width=line_width)
    
    # Add small highlight dots on pyramid
    highlight_color = (255, 255, 255, 200)
    dot_size = max(1, size // 48)
    
    # Top highlight
    draw.ellipse([center - dot_size, pyramid_top + pyramid_size // 6 - dot_size,
                  center + dot_size, pyramid_top + pyramid_size // 6 + dot_size],
                 fill=highlight_color)
    
    # Side highlights
    draw.ellipse([center - pyramid_size // 4 - dot_size, pyramid_bottom - pyramid_size // 3 - dot_size,
                  center - pyramid_size // 4 + dot_size, pyramid_bottom - pyramid_size // 3 + dot_size],
                 fill=highlight_color)
    
    draw.ellipse([center + pyramid_size // 4 - dot_size, pyramid_bottom - pyramid_size // 3 - dot_size,
                  center + pyramid_size // 4 + dot_size, pyramid_bottom - pyramid_size // 3 + dot_size],
                 fill=highlight_color)
    
    return img

def create_alternative_icon(size):
    """Create alternative ASUC icon with different style"""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    center = size // 2
    outer_radius = int(size * 0.45)
    
    # Arch Linux colors
    arch_blue = (13, 71, 161, 255)
    arch_light_blue = (25, 118, 210, 255)
    arch_dark_blue = (2, 20, 64, 255)
    
    # Draw hexagon background (representing package management)
    hex_radius = outer_radius
    hex_points = []
    for i in range(6):
        angle = i * math.pi / 3
        x = center + hex_radius * math.cos(angle)
        y = center + hex_radius * math.sin(angle)
        hex_points.append((x, y))
    
    # Draw hexagon with gradient effect
    draw.polygon(hex_points, fill=arch_blue, outline=arch_light_blue, width=max(1, size//64))
    
    # Draw conversion arrows inside hexagon
    arrow_radius = hex_radius * 0.6
    arrow_thickness = max(2, size // 48)
    
    # Draw circular arrows
    arrow_start = -math.pi / 4
    arrow_end = 3 * math.pi / 4
    
    bbox = [center - arrow_radius, center - arrow_radius,
            center + arrow_radius, center + arrow_radius]
    draw.arc(bbox, start=arrow_start * 180 / math.pi, 
             end=arrow_end * 180 / math.pi, 
             fill=arch_light_blue, width=arrow_thickness)
    
    # Arrow head
    head_angle = arrow_end
    head_x = center + arrow_radius * math.cos(head_angle)
    head_y = center + arrow_radius * math.sin(head_angle)
    head_size = arrow_radius * 0.2
    
    head_points = [
        (head_x, head_y),
        (head_x - head_size * math.cos(head_angle + math.pi / 2), 
         head_y - head_size * math.sin(head_angle + math.pi / 2)),
        (head_x - head_size * math.cos(head_angle + math.pi / 2 - math.pi / 6), 
         head_y - head_size * math.sin(head_angle + math.pi / 2 - math.pi / 6))
    ]
    draw.polygon(head_points, fill=arch_light_blue)
    
    # Draw Arch pyramid in center
    pyramid_size = arrow_radius * 0.5
    pyramid_top = center - pyramid_size // 2
    pyramid_bottom = center + pyramid_size // 2
    
    pyramid_points = [
        (center, pyramid_top),
        (center - pyramid_size // 2, pyramid_bottom),
        (center + pyramid_size // 2, pyramid_bottom)
    ]
    
    draw.polygon(pyramid_points, fill=arch_dark_blue)
    
    # Add pyramid details
    line_color = (255, 255, 255, 180)
    line_width = max(1, size // 64)
    
    draw.line([(center, pyramid_top), (center, pyramid_bottom)], 
              fill=line_color, width=line_width)
    
    return img

def main():
    """Generate all required icon sizes"""
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    # Standard icon sizes for AUR packages
    sizes = [16, 32, 48, 64, 128, 256, 512]
    
    print("Generating new ASUC icons with Arch pyramid and conversion symbol...")
    
    for size in sizes:
        # Main icon
        icon = create_arch_pyramid_icon(size)
        filename = f'icons/asuc-{size}x{size}.png'
        icon.save(filename, 'PNG')
        print(f"Created {filename}")
        
        # Alternative icon
        alt_icon = create_alternative_icon(size)
        alt_filename = f'icons/asuc-alt-{size}x{size}.png'
        alt_icon.save(alt_filename, 'PNG')
        print(f"Created {alt_filename}")
    
    # Create symbolic link for default icon
    if os.path.exists('icons/asuc-128x128.png'):
        try:
            os.symlink('asuc-128x128.png', 'icons/asuc.png')
            print("Created symbolic link: icons/asuc.png")
        except FileExistsError:
            print("Symbolic link already exists: icons/asuc.png")
    
    print("\nNew icon generation complete!")
    print("Icons feature Arch pyramid inside conversion/refresh symbol")
    print("All backgrounds are transparent")

if __name__ == '__main__':
    main() 