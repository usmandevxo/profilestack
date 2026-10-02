#!/usr/bin/env python3
"""
ProfileStack Logo & Favicon Generator
Generates:
  - app/static/img/logo.svg (Master Vector Mark)
  - app/static/img/logo-full.svg (Horizontal Brand Lockup)
  - app/static/favicon.svg (Scalable SVG Favicon)
  - app/static/favicon-16x16.png
  - app/static/favicon-32x32.png
  - app/static/apple-touch-icon.png (180x180)
  - app/static/favicon.png (512x512)
  - app/static/favicon.ico (Multi-size ICO: 16, 32, 48, 64)
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw

STATIC_DIR = Path("/www/wwwroot/profilestack/app/static")
IMG_DIR = STATIC_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Master Symbol SVG ──────────────────────────────────────────────────────
# The mark features three precision-engineered isometric containment plates
# representing the layered browser isolation stack (Container, Sandbox, Identity)
# with a centered, glowing aperture prism.
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <!-- Background glow / gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="50%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>

    <!-- Top Plate: Active Chromium Viewport -->
    <linearGradient id="topPlate" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <!-- Mid Plate: Hardware Anti-Detect Sandbox -->
    <linearGradient id="midPlate" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="70%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1e40af" />
    </linearGradient>

    <!-- Base Plate: Network & Docker Virtualization -->
    <linearGradient id="basePlate" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3b82f6" />
      <stop offset="80%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>

    <!-- Aperture Core / Shield Light -->
    <linearGradient id="coreLight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="40%" stop-color="#7dd3fc" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>

    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3.5" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>

    <filter id="shadowFilter" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.28" />
    </filter>
  </defs>

  <!-- Base Rounded Container Badge -->
  <rect x="6" y="6" width="108" height="108" rx="26" fill="url(#bgGrad)" filter="url(#shadowFilter)" />
  
  <!-- Subtle Internal Border Highlight -->
  <rect x="7" y="7" width="106" height="106" rx="25" fill="none" stroke="#60a5fa" stroke-width="1.2" stroke-opacity="0.35" />

  <!-- ── 3D Isometric Stack Plates ── -->
  <g filter="url(#shadowFilter)" transform="translate(60, 60)">

    <!-- LAYER 3: Bottom Virtualization Foundation Plate -->
    <!-- Top face -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 24)" fill="url(#basePlate)" opacity="0.85" />
    <!-- Front left face -->
    <path d="M -36,20 L 0,40 L 0,47 L -36,27 Z" fill="#0f172a" opacity="0.9" />
    <!-- Front right face -->
    <path d="M 0,40 L 36,20 L 36,27 L 0,47 Z" fill="#1e3a8a" opacity="0.95" />

    <!-- LAYER 2: Middle Anti-Detect & Proxy Sandbox Plate -->
    <!-- Top face -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 10)" fill="url(#midPlate)" />
    <!-- Front left face -->
    <path d="M -36,6 L 0,26 L 0,33 L -36,13 Z" fill="#1d4ed8" />
    <!-- Front right face -->
    <path d="M 0,26 L 36,6 L 36,13 L 0,33 Z" fill="#1e40af" />

    <!-- LAYER 1: Top Isolated Chromium Viewport Plate -->
    <!-- Top face -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, -4)" fill="url(#topPlate)" />
    <!-- Front left face -->
    <path d="M -36,-8 L 0,12 L 0,19 L -36,-1 Z" fill="#0284c7" />
    <!-- Front right face -->
    <path d="M 0,12 L 36,-8 L 36,-1 L 0,19 Z" fill="#0369a1" />

    <!-- Viewport Header Strip (Simulating Browser Tab Bar on Top Isometric Face) -->
    <path d="M -24,-17 L -10,-24 L 20,-7 L 6,0 Z" fill="#ffffff" opacity="0.22" />

    <!-- Aperture Core: The Floating Sandboxed Profile Node -->
    <g transform="translate(0, -18)" filter="url(#softGlow)">
      <!-- Outer Core Diamond -->
      <polygon points="0,-10 11,-4 11,4 0,10 -11,4 -11,-4" fill="url(#coreLight)" />
      <!-- Center Pivot Glow -->
      <circle cx="0" cy="0" r="3.2" fill="#ffffff" />
    </g>

  </g>
</svg>
"""

# ── 2. Full Horizontal Lockup SVG ─────────────────────────────────────────────
LOGO_FULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 64" width="100%" height="100%">
  <defs>
    <linearGradient id="flBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="60%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="flTop" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>
    <linearGradient id="flMid" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="100%" stop-color="#2563eb" />
    </linearGradient>
    <linearGradient id="flCore" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
  </defs>

  <!-- Left Icon Mark (48x48) -->
  <g transform="translate(6, 8)">
    <rect x="0" y="0" width="48" height="48" rx="12" fill="url(#flBgGrad)" />
    <rect x="0.5" y="0.5" width="47" height="47" rx="11.5" fill="none" stroke="#60a5fa" stroke-width="0.8" stroke-opacity="0.4" />
    
    <!-- Isometric Mini-Stack -->
    <g transform="translate(24, 25) scale(0.48)">
      <!-- Layer 3 Base -->
      <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 22)" fill="#1e3a8a" opacity="0.8" />
      <path d="M -36,18 L 0,38 L 0,44 L -36,24 Z" fill="#0f172a" />
      <path d="M 0,38 L 36,18 L 36,24 L 0,44 Z" fill="#1e3a8a" />

      <!-- Layer 2 Middle -->
      <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 9)" fill="url(#flMid)" />
      <path d="M -36,5 L 0,25 L 0,31 L -36,11 Z" fill="#1d4ed8" />
      <path d="M 0,25 L 36,5 L 36,11 L 0,31 Z" fill="#1e40af" />

      <!-- Layer 1 Top -->
      <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, -4)" fill="url(#flTop)" />
      <path d="M -36,-8 L 0,12 L 0,18 L -36,-2 Z" fill="#0284c7" />
      <path d="M 0,12 L 36,-8 L 36,-2 L 0,18 Z" fill="#0369a1" />

      <!-- Center Glow Core -->
      <polygon points="0,-9 9,-4 9,4 0,9 -9,4 -9,-4" transform="translate(0, -14)" fill="url(#flCore)" />
    </g>
  </g>

  <!-- Typography Lockup -->
  <g transform="translate(64, 18)">
    <!-- Primary Brand Wordmark -->
    <text x="0" y="19" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#0f172a" letter-spacing="-0.02em">Profile<tspan fill="#2563eb" font-weight="800">Stack</tspan></text>
    <!-- Architecture Sub-Label -->
    <text x="0.5" y="34" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="8.5" font-weight="700" fill="#64748b" letter-spacing="0.16em">BROWSER CLUSTER</text>
  </g>
</svg>
"""

# ── 3. Transparent Favicon SVG (Floats cleanly on light & dark browser tabs) ───
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="100%" height="100%">
  <defs>
    <linearGradient id="favBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="60%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="favTop" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>
    <linearGradient id="favMid" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="100%" stop-color="#2563eb" />
    </linearGradient>
  </defs>

  <!-- Rounded Squircle Badge with transparent outer edges -->
  <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#favBg)" />
  <rect x="3" y="3" width="58" height="58" rx="15" fill="none" stroke="#93c5fd" stroke-width="1.2" stroke-opacity="0.45" />

  <g transform="translate(32, 33) scale(0.62)">
    <!-- Base Plate -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 22)" fill="#1e3a8a" opacity="0.85" />
    <path d="M -36,18 L 0,38 L 0,44 L -36,24 Z" fill="#0f172a" />
    <path d="M 0,38 L 36,18 L 36,24 L 0,44 Z" fill="#1e3a8a" />

    <!-- Middle Plate -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, 9)" fill="url(#favMid)" />
    <path d="M -36,5 L 0,25 L 0,31 L -36,11 Z" fill="#1d4ed8" />
    <path d="M 0,25 L 36,5 L 36,11 L 0,31 Z" fill="#1e40af" />

    <!-- Top Plate -->
    <path d="M 0,16 L 36,-4 L 0,-24 L -36,-4 Z" transform="translate(0, -4)" fill="url(#favTop)" />
    <path d="M -36,-8 L 0,12 L 0,18 L -36,-2 Z" fill="#0284c7" />
    <path d="M 0,12 L 36,-8 L 36,-2 L 0,18 Z" fill="#0369a1" />

    <!-- Radiant Core Diamond -->
    <polygon points="0,-10 10,-4 10,4 0,10 -10,4 -10,-4" transform="translate(0, -15)" fill="#ffffff" />
    <circle cx="0" cy="-15" r="3.2" fill="#38bdf8" />
  </g>
</svg>
"""

# Write Vector Assets
with open(IMG_DIR / "logo.svg", "w") as f:
    f.write(LOGO_SVG.strip())

with open(IMG_DIR / "logo-full.svg", "w") as f:
    f.write(LOGO_FULL_SVG.strip())

with open(STATIC_DIR / "favicon.svg", "w") as f:
    f.write(FAVICON_SVG.strip())

print("SAVED: logo.svg, logo-full.svg, favicon.svg")


# ── 4. High-Fidelity Rasterization via Pillow ──────────────────────────────────
# Render precision raster assets matching the exact brand geometry
def render_brand_bitmap(size: int) -> Image.Image:
    # 4x supersampling for ultra-crisp antialiasing
    scale = 4
    canvas_size = size * scale
    im = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    pad = 2 * scale
    corner_radius = int(canvas_size * 0.26)
    
    # Outer Squircle Background
    # Draw vertical linear gradient from Royal Blue to Dark Navy
    c_top = (37, 99, 235, 255)    # #2563eb
    c_bottom = (15, 23, 42, 255)  # #0f172a
    
    # Base shape mask
    mask = Image.new("L", (canvas_size, canvas_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [pad, pad, canvas_size - pad, canvas_size - pad],
        radius=corner_radius,
        fill=255
    )

    # Gradient fill
    for y in range(canvas_size):
        factor = y / canvas_size
        r = int(c_top[0] + (c_bottom[0] - c_top[0]) * factor)
        g = int(c_top[1] + (c_bottom[1] - c_top[1]) * factor)
        b = int(c_top[2] + (c_bottom[2] - c_top[2]) * factor)
        draw.line([(0, y), (canvas_size, y)], fill=(r, g, b, 255))
    
    # Apply squircle mask
    im.putalpha(mask)
    draw = ImageDraw.Draw(im)

    # Inner Border Highlight
    draw.rounded_rectangle(
        [pad + scale, pad + scale, canvas_size - pad - scale, canvas_size - pad - scale],
        radius=corner_radius - scale,
        outline=(96, 165, 250, 90),
        width=int(1.2 * scale)
    )

    # Isometric Stack Geometry
    cx = canvas_size // 2
    cy = int(canvas_size * 0.52)
    w = int(canvas_size * 0.32)
    h = int(w * 0.55)

    def draw_iso_slab(y_offset, top_color, left_color, right_color, thickness):
        top_pts = [
            (cx, cy + y_offset - h),
            (cx + w, cy + y_offset),
            (cx, cy + y_offset + h),
            (cx - w, cy + y_offset),
        ]
        left_pts = [
            (cx - w, cy + y_offset),
            (cx, cy + y_offset + h),
            (cx, cy + y_offset + h + thickness),
            (cx - w, cy + y_offset + thickness),
        ]
        right_pts = [
            (cx, cy + y_offset + h),
            (cx + w, cy + y_offset),
            (cx + w, cy + y_offset + thickness),
            (cx, cy + y_offset + h + thickness),
        ]
        draw.polygon(left_pts, fill=left_color)
        draw.polygon(right_pts, fill=right_color)
        draw.polygon(top_pts, fill=top_color)

    t = int(4.5 * scale)
    
    # Bottom Layer: Docker Virtualization
    draw_iso_slab(
        y_offset=int(16 * scale),
        top_color=(30, 58, 138, 220),
        left_color=(15, 23, 42, 255),
        right_color=(30, 58, 138, 255),
        thickness=t
    )

    # Middle Layer: Anti-Detect Hardware Spoofing
    draw_iso_slab(
        y_offset=int(4 * scale),
        top_color=(59, 130, 246, 240),
        left_color=(29, 78, 216, 255),
        right_color=(30, 64, 175, 255),
        thickness=t
    )

    # Top Layer: Active Chromium Profile Viewport
    draw_iso_slab(
        y_offset=int(-8 * scale),
        top_color=(56, 189, 248, 255),
        left_color=(2, 132, 199, 255),
        right_color=(3, 105, 161, 255),
        thickness=t
    )

    # Center Radiant Aperture / Identity Core
    core_y = int(cy - 21 * scale)
    cw = int(9 * scale)
    ch = int(5 * scale)
    core_pts = [
        (cx, core_y - ch),
        (cx + cw, core_y),
        (cx, core_y + ch),
        (cx - cw, core_y),
    ]
    draw.polygon(core_pts, fill=(255, 255, 255, 255))
    draw.ellipse(
        [cx - int(2.5 * scale), core_y - int(2.5 * scale), cx + int(2.5 * scale), core_y + int(2.5 * scale)],
        fill=(56, 189, 248, 255)
    )

    # High quality downsampling to target size
    return im.resize((size, size), Image.Resampling.LANCZOS)


# Generate Raster Suite
sizes = {
    "favicon-16x16.png": 16,
    "favicon-32x32.png": 32,
    "apple-touch-icon.png": 180,
    "favicon.png": 512,
}

bitmaps = {}
for filename, s in sizes.items():
    img = render_brand_bitmap(s)
    img.save(STATIC_DIR / filename, "PNG")
    bitmaps[s] = img
    print(f"RENDERED: {filename} ({s}x{s})")

# Generate Multi-Resolution favicon.ico (16, 32, 48, 64)
ico_sizes = [16, 32, 48, 64]
ico_images = [render_brand_bitmap(s) for s in ico_sizes]
ico_images[0].save(
    STATIC_DIR / "favicon.ico",
    format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print("GENERATED: favicon.ico (multi-resolution 16, 32, 48, 64)")

# [ProfileStack v1.29.18] revision checkpoint
