#!/usr/bin/env python3
"""
Generate efficient SVG icons for AUR package
Creates lightweight vector graphics instead of embedding PNG data
"""

import os
from PIL import Image
import numpy as np

def analyze_icon_colors(png_path):
    """Analyze the PNG to extract dominant colors and patterns"""
    try:
        img = Image.open(png_path)
        img_array = np.array(img)
        
        # Get unique colors
        unique_colors = np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0)
        
        # Find most common colors
        colors = []
        for color in unique_colors[:10]:  # Top 10 colors
            if len(color) >= 3:  # RGB or RGBA
                colors.append(tuple(color[:3]))
        
        return colors, img.size
    except Exception as e:
        print(f"Error analyzing PNG: {e}")
        return [], (128, 128)

def create_lightweight_svg_icon(size, colors, original_size):
    """Create a lightweight SVG icon with vector elements"""
    # Use Arch Linux colors if we can't extract from PNG
    if not colors:
        colors = [(13, 71, 161), (25, 118, 210), (2, 20, 64)]  # Arch blues
    
    primary_color = colors[0] if colors else (13, 71, 161)
    secondary_color = colors[1] if len(colors) > 1 else (25, 118, 210)
    
    # Convert RGB to hex
    primary_hex = f"#{primary_color[0]:02x}{primary_color[1]:02x}{primary_color[2]:02x}"
    secondary_hex = f"#{secondary_color[0]:02x}{secondary_color[1]:02x}{secondary_color[2]:02x}"
    
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Background circle -->
  <circle cx="64" cy="64" r="60" fill="{primary_hex}" opacity="0.1"/>
  
  <!-- Conversion arrows (circular refresh symbol) -->
  <g fill="none" stroke="{primary_hex}" stroke-width="4" stroke-linecap="round">
    <!-- Outer circle -->
    <circle cx="64" cy="64" r="50" stroke-width="3"/>
    
    <!-- First arrow (clockwise) -->
    <path d="M 64 20 A 44 44 0 1 1 64 108" stroke="{primary_hex}" stroke-width="3"/>
    <path d="M 64 108 L 56 100 M 64 108 L 72 100" stroke-width="2"/>
    
    <!-- Second arrow (counter-clockwise) - smaller -->
    <path d="M 64 35 A 31 31 0 1 0 64 93" stroke="{secondary_hex}" stroke-width="3"/>
    <path d="M 64 93 L 72 85 M 64 93 L 56 85" stroke-width="2"/>
  </g>
  
  <!-- Arch pyramid in center -->
  <g fill="{secondary_hex}">
    <!-- Main pyramid triangle -->
    <polygon points="64,40 48,80 80,80"/>
    
    <!-- 3D effect lines -->
    <g stroke="#FFFFFF" stroke-width="1" stroke-opacity="0.7" fill="none">
      <!-- Center line -->
      <line x1="64" y1="40" x2="64" y2="80"/>
      
      <!-- Side line for 3D effect -->
      <line x1="56" y1="50" x2="56" y2="80"/>
    </g>
    
    <!-- Highlight dots -->
    <g fill="#FFFFFF" fill-opacity="0.8">
      <!-- Top highlight -->
      <circle cx="64" cy="50" r="2"/>
      
      <!-- Side highlights -->
      <circle cx="56" cy="65" r="2"/>
      <circle cx="72" cy="65" r="2"/>
    </g>
  </g>
</svg>'''
    
    return svg_content

def create_alternative_lightweight_svg(size, colors):
    """Create alternative lightweight SVG design"""
    primary_color = colors[0] if colors else (13, 71, 161)
    secondary_color = colors[1] if len(colors) > 1 else (25, 118, 210)
    
    primary_hex = f"#{primary_color[0]:02x}{primary_color[1]:02x}{primary_color[2]:02x}"
    secondary_hex = f"#{secondary_color[0]:02x}{secondary_color[1]:02x}{secondary_color[2]:02x}"
    
    svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Hexagon background -->
  <polygon points="64,20 96,35 96,85 64,100 32,85 32,35" 
           fill="{primary_hex}" stroke="{secondary_hex}" stroke-width="2"/>
  
  <!-- Conversion arrow inside hexagon -->
  <g fill="none" stroke="{secondary_hex}" stroke-width="3" stroke-linecap="round">
    <path d="M 64 40 A 30 30 0 1 1 64 88" stroke-linejoin="round"/>
    <path d="M 64 88 L 56 80 M 64 88 L 72 80" stroke-width="2"/>
  </g>
  
  <!-- Arch pyramid in center -->
  <g fill="#021440">
    <!-- Main pyramid triangle -->
    <polygon points="64,50 54,75 74,75"/>
    
    <!-- 3D effect line -->
    <g stroke="#FFFFFF" stroke-width="1" stroke-opacity="0.7" fill="none">
      <line x1="64" y1="50" x2="64" y2="75"/>
    </g>
  </g>
</svg>'''
    
    return svg_content

def main():
    """Generate lightweight SVG icons"""
    png_path = 'icon.png'
    
    # Check if icon.png exists
    if not os.path.exists(png_path):
        print(f"Error: {png_path} not found!")
        return
    
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    # Analyze the PNG to extract colors
    print("Analyzing icon.png for color extraction...")
    colors, original_size = analyze_icon_colors(png_path)
    
    if colors:
        print(f"Extracted {len(colors)} colors from PNG")
    else:
        print("Using default Arch Linux colors")
    
    # Standard icon sizes for AUR packages
    sizes = [16, 32, 48, 64, 128, 256, 512]
    
    print("Generating lightweight SVG icons...")
    
    for size in sizes:
        # Create main lightweight SVG
        svg_content = create_lightweight_svg_icon(size, colors, original_size)
        
        filename = f'icons/asuc-{size}x{size}.svg'
        with open(filename, 'w') as f:
            f.write(svg_content)
        
        # Get file size
        file_size = os.path.getsize(filename)
        print(f"Created {filename} ({file_size:,} bytes)")
    
    # Create default icon (128x128)
    default_svg = create_lightweight_svg_icon(128, colors, original_size)
    with open('icons/asuc.svg', 'w') as f:
        f.write(default_svg)
    
    default_size = os.path.getsize('icons/asuc.svg')
    print(f"Created icons/asuc.svg (default) ({default_size:,} bytes)")
    
    # Create alternative design
    alt_svg = create_alternative_lightweight_svg(128, colors)
    with open('icons/asuc-alt.svg', 'w') as f:
        f.write(alt_svg)
    
    alt_size = os.path.getsize('icons/asuc-alt.svg')
    print(f"Created icons/asuc-alt.svg ({alt_size:,} bytes)")
    
    # Create symbolic link for default icon
    try:
        if os.path.exists('icons/asuc-128x128.svg'):
            os.symlink('asuc-128x128.svg', 'icons/asuc-default.svg')
            print("Created symbolic link: icons/asuc-default.svg")
    except FileExistsError:
        print("Symbolic link already exists: icons/asuc-default.svg")
    
    print("\nLightweight SVG icon generation complete!")
    print("Icons are now properly vector-based and much smaller")
    print("All icons are scalable and ready for AUR package use")

if __name__ == '__main__':
    main() 