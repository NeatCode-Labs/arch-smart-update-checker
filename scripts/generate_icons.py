#!/usr/bin/env python3
"""
Generate ASUC icons for AUR package
Creates icons in various sizes with a modern design representing smart update checking
"""

import os
from PIL import Image, ImageDraw, ImageFont
import math

def create_asuc_icon(size):
    """Create ASUC icon with given size"""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    padding = size // 8
    inner_size = size - 2 * padding
    center = size // 2
    
    # Background circle (Arch Linux blue)
    bg_color = (13, 71, 161, 255)  # Arch blue
    draw.ellipse([padding, padding, size - padding, size - padding], 
                 fill=bg_color, outline=(255, 255, 255, 100), width=max(1, size//64))
    
    # Inner circle (white)
    inner_padding = padding + inner_size // 6
    inner_circle_size = inner_size - inner_size // 3
    draw.ellipse([inner_padding, inner_padding, 
                  size - inner_padding, size - inner_padding], 
                 fill=(255, 255, 255, 255))
    
    # Update arrow (pointing up)
    arrow_color = (13, 71, 161, 255)  # Arch blue
    arrow_width = max(2, size // 32)
    
    # Arrow head
    arrow_head_size = inner_circle_size // 4
    arrow_head_y = center - arrow_head_size // 2
    arrow_head_x = center
    
    # Draw arrow head (triangle pointing up)
    arrow_points = [
        (arrow_head_x, arrow_head_y),
        (arrow_head_x - arrow_head_size // 2, arrow_head_y + arrow_head_size),
        (arrow_head_x + arrow_head_size // 2, arrow_head_y + arrow_head_size)
    ]
    draw.polygon(arrow_points, fill=arrow_color)
    
    # Arrow stem
    stem_width = arrow_head_size // 3
    stem_height = arrow_head_size // 2
    stem_x = center - stem_width // 2
    stem_y = arrow_head_y + arrow_head_size + stem_height // 4
    
    draw.rectangle([stem_x, stem_y, stem_x + stem_width, stem_y + stem_height], 
                   fill=arrow_color)
    
    # Smart indicator dots (representing intelligence/filtering)
    dot_size = max(2, size // 48)
    dot_color = (255, 193, 7, 255)  # Warning/attention yellow
    
    # Three dots in a triangle pattern
    dot_offset = inner_circle_size // 6
    dots = [
        (center - dot_offset, center + dot_offset),
        (center + dot_offset, center + dot_offset),
        (center, center - dot_offset // 2)
    ]
    
    for dot_x, dot_y in dots:
        draw.ellipse([dot_x - dot_size, dot_y - dot_size, 
                      dot_x + dot_size, dot_y + dot_size], 
                     fill=dot_color)
    
    return img

def create_alternative_icon(size):
    """Create alternative ASUC icon with different design"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate dimensions
    padding = size // 8
    center = size // 2
    
    # Hexagon background (representing package management)
    hex_radius = (size - 2 * padding) // 2
    hex_points = []
    for i in range(6):
        angle = i * math.pi / 3
        x = center + hex_radius * math.cos(angle)
        y = center + hex_radius * math.sin(angle)
        hex_points.append((x, y))
    
    # Draw hexagon
    draw.polygon(hex_points, fill=(13, 71, 161, 255), 
                 outline=(255, 255, 255, 100), width=max(1, size//64))
    
    # Inner circle
    inner_radius = hex_radius * 0.6
    draw.ellipse([center - inner_radius, center - inner_radius,
                  center + inner_radius, center + inner_radius],
                 fill=(255, 255, 255, 255))
    
    # Update symbol (refresh arrow)
    arrow_color = (13, 71, 161, 255)
    arrow_size = inner_radius * 0.4
    
    # Draw circular arrow
    arrow_thickness = max(2, size // 48)
    arrow_start = -math.pi / 4
    arrow_end = 3 * math.pi / 4
    
    # Draw arc
    bbox = [center - arrow_size, center - arrow_size,
            center + arrow_size, center + arrow_size]
    draw.arc(bbox, start=arrow_start * 180 / math.pi, 
             end=arrow_end * 180 / math.pi, 
             fill=arrow_color, width=arrow_thickness)
    
    # Arrow head
    arrow_head_angle = arrow_end
    head_x = center + arrow_size * math.cos(arrow_head_angle)
    head_y = center + arrow_size * math.sin(arrow_head_angle)
    
    head_size = arrow_size * 0.2
    head_angle = arrow_head_angle + math.pi / 2
    
    head_points = [
        (head_x, head_y),
        (head_x - head_size * math.cos(head_angle), 
         head_y - head_size * math.sin(head_angle)),
        (head_x - head_size * math.cos(head_angle - math.pi / 6), 
         head_y - head_size * math.sin(head_angle - math.pi / 6))
    ]
    draw.polygon(head_points, fill=arrow_color)
    
    return img

def main():
    """Generate all required icon sizes"""
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    # Standard icon sizes for AUR packages
    sizes = [16, 32, 48, 64, 128, 256, 512]
    
    print("Generating ASUC icons...")
    
    for size in sizes:
        # Main icon
        icon = create_asuc_icon(size)
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
    
    print("\nIcon generation complete!")
    print("Icons created in the 'icons/' directory")
    print("\nUsage in PKGBUILD:")
    print("install -Dm644 icons/asuc-128x128.png \"$pkgdir/usr/share/pixmaps/asuc.png\"")
    print("install -Dm644 icons/asuc-128x128.png \"$pkgdir/usr/share/icons/hicolor/128x128/apps/asuc.png\"")

if __name__ == '__main__':
    main() 