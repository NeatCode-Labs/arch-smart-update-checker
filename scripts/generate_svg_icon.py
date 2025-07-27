#!/usr/bin/env python3
"""
Generate SVG version of ASUC icon
Creates scalable vector graphics version of the main ASUC icon
"""

def create_svg_icon():
    """Create SVG version of the main ASUC icon"""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Background circle (Arch Linux blue) -->
  <circle cx="64" cy="64" r="56" fill="#0D47A1" stroke="#FFFFFF" stroke-width="2" stroke-opacity="0.4"/>
  
  <!-- Inner circle (white) -->
  <circle cx="64" cy="64" r="37" fill="#FFFFFF"/>
  
  <!-- Update arrow (pointing up) -->
  <g fill="#0D47A1">
    <!-- Arrow head (triangle) -->
    <polygon points="64,48 56,64 72,64"/>
    
    <!-- Arrow stem (rectangle) -->
    <rect x="60" y="64" width="8" height="12"/>
  </g>
  
  <!-- Smart indicator dots (yellow) -->
  <g fill="#FFC107">
    <!-- Bottom left dot -->
    <circle cx="48" cy="80" r="3"/>
    
    <!-- Bottom right dot -->
    <circle cx="80" cy="80" r="3"/>
    
    <!-- Top center dot -->
    <circle cx="64" cy="56" r="3"/>
  </g>
</svg>'''
    
    return svg_content

def create_alternative_svg_icon():
    """Create SVG version of the alternative ASUC icon"""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Hexagon background -->
  <polygon points="64,16 96,32 96,80 64,96 32,80 32,32" 
           fill="#0D47A1" stroke="#FFFFFF" stroke-width="2" stroke-opacity="0.4"/>
  
  <!-- Inner circle -->
  <circle cx="64" cy="64" r="30" fill="#FFFFFF"/>
  
  <!-- Circular refresh arrow -->
  <g fill="none" stroke="#0D47A1" stroke-width="3" stroke-linecap="round">
    <!-- Arc -->
    <path d="M 64 40 A 20 20 0 1 1 64 88" stroke-linejoin="round"/>
    
    <!-- Arrow head -->
    <path d="M 64 88 L 56 80 M 64 88 L 72 80" stroke-width="2"/>
  </g>
</svg>'''
    
    return svg_content

def main():
    """Generate SVG icons"""
    import os
    
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    print("Generating SVG icons...")
    
    # Main SVG icon
    main_svg = create_svg_icon()
    with open('icons/asuc.svg', 'w') as f:
        f.write(main_svg)
    print("Created icons/asuc.svg")
    
    # Alternative SVG icon
    alt_svg = create_alternative_svg_icon()
    with open('icons/asuc-alt.svg', 'w') as f:
        f.write(alt_svg)
    print("Created icons/asuc-alt.svg")
    
    print("\nSVG icon generation complete!")
    print("SVG icons provide better scalability for high-DPI displays")

if __name__ == '__main__':
    main() 