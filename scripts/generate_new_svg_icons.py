#!/usr/bin/env python3
"""
Generate SVG versions of new ASUC icons
Creates scalable vector graphics with Arch pyramid inside conversion symbol
"""

def create_main_svg_icon():
    """Create SVG version of the main ASUC icon"""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Conversion arrows (circular refresh symbol) -->
  <g fill="none" stroke="#0D47A1" stroke-width="3" stroke-linecap="round">
    <!-- Outer circle -->
    <circle cx="64" cy="64" r="51" stroke-width="3"/>
    
    <!-- First arrow (clockwise) -->
    <path d="M 64 20 A 44 44 0 1 1 64 108" stroke="#0D47A1" stroke-width="3"/>
    <path d="M 64 108 L 56 100 M 64 108 L 72 100" stroke-width="2"/>
    
    <!-- Second arrow (counter-clockwise) - smaller -->
    <path d="M 64 35 A 31 31 0 1 0 64 93" stroke="#1976D2" stroke-width="3"/>
    <path d="M 64 93 L 72 85 M 64 93 L 56 85" stroke-width="2"/>
  </g>
  
  <!-- Arch pyramid in center -->
  <g fill="#021440">
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

def create_alternative_svg_icon():
    """Create SVG version of the alternative ASUC icon"""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <!-- Hexagon background -->
  <polygon points="64,20 96,35 96,85 64,100 32,85 32,35" 
           fill="#0D47A1" stroke="#1976D2" stroke-width="2"/>
  
  <!-- Conversion arrow inside hexagon -->
  <g fill="none" stroke="#1976D2" stroke-width="3" stroke-linecap="round">
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
    """Generate SVG icons"""
    import os
    
    # Create icons directory if it doesn't exist
    os.makedirs('icons', exist_ok=True)
    
    print("Generating SVG icons with Arch pyramid and conversion symbol...")
    
    # Main SVG icon
    main_svg = create_main_svg_icon()
    with open('icons/asuc.svg', 'w') as f:
        f.write(main_svg)
    print("Created icons/asuc.svg")
    
    # Alternative SVG icon
    alt_svg = create_alternative_svg_icon()
    with open('icons/asuc-alt.svg', 'w') as f:
        f.write(alt_svg)
    print("Created icons/asuc-alt.svg")
    
    print("\nSVG icon generation complete!")
    print("SVG icons feature Arch pyramid inside conversion symbol")
    print("All backgrounds are transparent")

if __name__ == '__main__':
    main() 