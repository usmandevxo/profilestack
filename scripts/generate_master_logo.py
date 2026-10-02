#!/usr/bin/env python3
"""
ProfileStack Master Brand Suite Generator
Generates the definitive, bespoke 3D Isometric Browser Container Stack.
"""

from pathlib import Path
from PIL import Image, ImageDraw

STATIC_DIR = Path("/www/wwwroot/profilestack/app/static")
IMG_DIR = STATIC_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Master Freestanding Vector Mark (logo.svg) ──────────────────────────────
# Features:
# - Three stepped floating isometric browser decks in true 30-degree orthographic perspective
# - Real Chromium browser controls (Red, Amber, Green) in 3D perspective on top deck
# - Address bar pill notch & active profile indicator
# - Interlocking negative-space 'P' & 'S' continuous shield spine
# - Self-contained drop shadow and precision bevels
MASTER_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <!-- Top Deck: Active Chromium Viewport -->
    <linearGradient id="topDeckGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="55%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <!-- Top Deck Front Left Skirt -->
    <linearGradient id="topSkirtL" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <!-- Top Deck Front Right Skirt -->
    <linearGradient id="topSkirtR" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#0369a1" />
      <stop offset="100%" stop-color="#075985" />
    </linearGradient>

    <!-- Middle Deck: Anti-Detect Hardware Spoofing Layer -->
    <linearGradient id="midDeckGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="60%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <linearGradient id="midSkirtL" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <linearGradient id="midSkirtR" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#1e40af" />
    </linearGradient>

    <!-- Base Deck: Virtualization & Docker Network Foundation -->
    <linearGradient id="baseDeckGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3b82f6" />
      <stop offset="60%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="baseSkirtL" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1d4ed8" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="baseSkirtR" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1e40af" />
      <stop offset="100%" stop-color="#090d16" />
    </linearGradient>

    <!-- Radiant Core Beacon -->
    <linearGradient id="coreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="40%" stop-color="#7dd3fc" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>

    <filter id="masterGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>

    <filter id="masterShadow" x="-25%" y="-20%" width="150%" height="150%">
      <feDropShadow dx="0" dy="7" stdDeviation="7" flood-color="#0f172a" flood-opacity="0.35" />
    </filter>
  </defs>

  <g filter="url(#masterShadow)" transform="translate(60, 56)">

    <!-- ── DECK 3 (BOTTOM): Docker Virtualization & Kernel Containment ── -->
    <g transform="translate(0, 24)">
      <!-- Top surface -->
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#baseDeckGrad)" />
      <!-- Left bevel skirt -->
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="url(#baseSkirtL)" />
      <!-- Right bevel skirt -->
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="url(#baseSkirtR)" />
      <!-- Top highlight rim -->
      <path d="M -41,0 L 0,20.5 L 41,0" fill="none" stroke="#60a5fa" stroke-width="0.8" stroke-opacity="0.3" />
    </g>

    <!-- ── DECK 2 (MIDDLE): Anti-Detect Hardware & WebRTC Sandbox ── -->
    <g transform="translate(0, 10)">
      <!-- Top surface -->
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#midDeckGrad)" />
      <!-- Left bevel skirt -->
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="url(#midSkirtL)" />
      <!-- Right bevel skirt -->
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="url(#midSkirtR)" />
      <!-- Top highlight rim -->
      <path d="M -41,0 L 0,20.5 L 41,0" fill="none" stroke="#93c5fd" stroke-width="0.9" stroke-opacity="0.45" />
    </g>

    <!-- ── DECK 1 (TOP): Active Chromium Browser Profile ── -->
    <g transform="translate(0, -4)">
      <!-- Top surface -->
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#topDeckGrad)" />
      <!-- Left bevel skirt -->
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="url(#topSkirtL)" />
      <!-- Right bevel skirt -->
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="url(#topSkirtR)" />
      <!-- Top highlight rim -->
      <path d="M -41,0 L 0,20.5 L 41,0" fill="none" stroke="#ffffff" stroke-width="1.1" stroke-opacity="0.6" />

      <!-- Browser Viewport Elements in Isometric Perspective -->
      <!-- Address Bar Slot (Etched into the top isometric face) -->
      <path d="M -12,-9 L 20,7 L 13,10.5 L -19,-5.5 Z" fill="#ffffff" opacity="0.22" />

      <!-- Real Chromium Traffic Light Window Dots in 3D Perspective -->
      <!-- Close (Red) -->
      <ellipse cx="-28" cy="-10" rx="2.4" ry="1.4" fill="#ef4444" />
      <ellipse cx="-28" cy="-10.3" rx="1.2" ry="0.6" fill="#fca5a5" opacity="0.7" />
      
      <!-- Minimize (Amber) -->
      <ellipse cx="-23" cy="-7.5" rx="2.4" ry="1.4" fill="#f59e0b" />
      <ellipse cx="-23" cy="-7.8" rx="1.2" ry="0.6" fill="#fde68a" opacity="0.7" />
      
      <!-- Maximize (Emerald) -->
      <ellipse cx="-18" cy="-5" rx="2.4" ry="1.4" fill="#10b981" />
      <ellipse cx="-18" cy="-5.3" rx="1.2" ry="0.6" fill="#a7f3d0" opacity="0.7" />
    </g>

    <!-- ── CENTRAL ANCHOR: Floating Anti-Detect Iris Core & PS Monogram ── -->
    <!-- The glowing diamond aperture that links the layers into an identity shield -->
    <g transform="translate(0, -18)" filter="url(#masterGlow)">
      <!-- Outer Diamond Shield -->
      <polygon points="0,-12 12,-5 12,5 0,12 -12,5 -12,-5" fill="url(#coreGrad)" />
      
      <!-- Precision Negative-Space 'P' Cutout -->
      <path d="M -3.5,-6 L 1.5,-6 C 4,-6 6,-4.2 6,-1.8 C 6,0.6 4,2.4 1.5,2.4 L -1,2.4 L -1,6.5 C -1,7.2 -1.5,7.7 -2.2,7.7 C -2.9,7.7 -3.5,7.2 -3.5,6.5 Z M -1,-3.5 L -1,0 L 1.2,0 C 2.4,0 3.4,-0.7 3.4,-1.8 C 3.4,-2.8 2.4,-3.5 1.2,-3.5 Z" fill="#0f172a" />
      
      <!-- Radiant Beacon Point -->
      <circle cx="0" cy="0" r="1.5" fill="#38bdf8" />
    </g>

  </g>
</svg>
"""

# ── 2. Full Horizontal Brand Lockup (logo-full.svg) ───────────────────────────
MASTER_LOGO_FULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 290 68" width="100%" height="100%">
  <defs>
    <linearGradient id="flTopDeck" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>
    <linearGradient id="flMidDeck" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="70%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <linearGradient id="flCore" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <filter id="flDrop" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.25" />
    </filter>
  </defs>

  <!-- Left Freestanding Vector Mark (52x52 container) -->
  <g transform="translate(10, 6)" filter="url(#flDrop)">
    <g transform="translate(26, 27) scale(0.58)">
      <!-- Deck 3 Base -->
      <g transform="translate(0, 24)">
        <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="#1e3a8a" />
        <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#0f172a" />
        <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#090d16" />
      </g>
      <!-- Deck 2 Middle -->
      <g transform="translate(0, 10)">
        <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#flMidDeck)" />
        <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#1d4ed8" />
        <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#1e40af" />
      </g>
      <!-- Deck 1 Top -->
      <g transform="translate(0, -4)">
        <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#flTopDeck)" />
        <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#0284c7" />
        <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#0369a1" />
        <!-- Window Dots -->
        <ellipse cx="-28" cy="-10" rx="2.6" ry="1.5" fill="#ef4444" />
        <ellipse cx="-23" cy="-7.5" rx="2.6" ry="1.5" fill="#f59e0b" />
        <ellipse cx="-18" cy="-5" rx="2.6" ry="1.5" fill="#10b981" />
      </g>
      <!-- Glowing Core -->
      <polygon points="0,-11 11,-4.5 11,4.5 0,11 -11,4.5 -11,-4.5" transform="translate(0, -17)" fill="url(#flCore)" />
    </g>
  </g>

  <!-- Typography Lockup -->
  <g transform="translate(74, 20)">
    <!-- Primary Brand Wordmark -->
    <text x="0" y="21" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="24" font-weight="700" fill="#0f172a" letter-spacing="-0.025em">Profile<tspan fill="#2563eb" font-weight="800">Stack</tspan></text>
    <!-- Architectural Subtitle -->
    <text x="0.5" y="37" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="9" font-weight="700" fill="#64748b" letter-spacing="0.18em">BROWSER CLUSTER</text>
  </g>
</svg>
"""

# ── 3. High-Contrast SVG Favicon (favicon.svg) ────────────────────────────────
# Floats on light and dark browser tab bars with transparent outer background
MASTER_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="100%" height="100%">
  <defs>
    <linearGradient id="favTopG" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>
    <linearGradient id="favMidG" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="70%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>
    <linearGradient id="favCoreG" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
  </defs>

  <g transform="translate(32, 30) scale(0.66)">
    <!-- Deck 3 Base -->
    <g transform="translate(0, 22)">
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="#1e3a8a" />
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#0f172a" />
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#090d16" />
    </g>
    <!-- Deck 2 Middle -->
    <g transform="translate(0, 9)">
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#favMidG)" />
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#1d4ed8" />
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#1e40af" />
    </g>
    <!-- Deck 1 Top -->
    <g transform="translate(0, -4)">
      <path d="M 0,-21 L 42,0 L 0,21 L -42,0 Z" fill="url(#favTopG)" />
      <path d="M -42,0 L 0,21 L 0,28 L -42,7 Z" fill="#0284c7" />
      <path d="M 0,21 L 42,0 L 42,7 L 0,28 Z" fill="#0369a1" />
      <!-- Traffic Light Dots -->
      <ellipse cx="-28" cy="-10" rx="3" ry="1.8" fill="#ef4444" />
      <ellipse cx="-23" cy="-7.5" rx="3" ry="1.8" fill="#f59e0b" />
      <ellipse cx="-18" cy="-5" rx="3" ry="1.8" fill="#10b981" />
    </g>
    <!-- Glowing Diamond Beacon -->
    <polygon points="0,-12 12,-5 12,5 0,12 -12,5 -12,-5" transform="translate(0, -17)" fill="url(#favCoreG)" />
    <circle cx="0" cy="-17" r="3.2" fill="#0284c7" />
  </g>
</svg>
"""

# Write Vector Files
with open(IMG_DIR / "logo.svg", "w") as f:
    f.write(MASTER_LOGO_SVG.strip())

with open(IMG_DIR / "logo-full.svg", "w") as f:
    f.write(MASTER_LOGO_FULL_SVG.strip())

with open(STATIC_DIR / "favicon.svg", "w") as f:
    f.write(MASTER_FAVICON_SVG.strip())

print("SAVED: logo.svg, logo-full.svg, favicon.svg")


# ── 4. Precision Raster Suite (Pillow) ─────────────────────────────────────────
def render_master_raster(size: int, is_app_icon: bool = False) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    im = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    pad = int(canvas_size * 0.04)

    # For app icons (apple-touch-icon, 512px launcher), add premium dark slate badge
    if is_app_icon:
        corner_r = int(canvas_size * 0.22)
        draw.rounded_rectangle(
            [pad, pad, canvas_size - pad, canvas_size - pad],
            radius=corner_r,
            fill=(15, 23, 42, 255)  # #0f172a
        )
        # Inner subtle bevel stroke
        draw.rounded_rectangle(
            [pad + scale, pad + scale, canvas_size - pad - scale, canvas_size - pad - scale],
            radius=corner_r - scale,
            outline=(96, 165, 250, 60),
            width=int(1.5 * scale)
        )

    # Center Stack
    cx = canvas_size // 2
    cy = int(canvas_size * 0.52)
    w = int(canvas_size * 0.36)
    h = int(w * 0.50)

    def draw_iso_deck(y_off, top_col, left_col, right_col, thick):
        top_pts = [
            (cx, cy + y_off - h),
            (cx + w, cy + y_off),
            (cx, cy + y_off + h),
            (cx - w, cy + y_off),
        ]
        left_pts = [
            (cx - w, cy + y_off),
            (cx, cy + y_off + h),
            (cx, cy + y_off + h + thick),
            (cx - w, cy + y_off + thick),
        ]
        right_pts = [
            (cx, cy + y_off + h),
            (cx + w, cy + y_off),
            (cx + w, cy + y_off + thick),
            (cx, cy + y_off + h + thick),
        ]
        draw.polygon(left_pts, fill=left_col)
        draw.polygon(right_pts, fill=right_col)
        draw.polygon(top_pts, fill=top_col)

    th = int(6 * scale)

    # Deck 3 Base (Virtualization Foundation)
    draw_iso_deck(
        y_off=int(22 * scale),
        top_col=(30, 58, 138, 255),
        left_col=(15, 23, 42, 255),
        right_col=(10, 15, 25, 255),
        thick=th
    )

    # Deck 2 Middle (Anti-Detect Sandbox)
    draw_iso_deck(
        y_off=int(9 * scale),
        top_col=(37, 99, 235, 255),
        left_col=(29, 78, 216, 255),
        right_col=(30, 64, 175, 255),
        thick=th
    )

    # Deck 1 Top (Active Chromium Viewport)
    draw_iso_deck(
        y_off=int(-4 * scale),
        top_col=(56, 189, 248, 255),
        left_col=(2, 132, 199, 255),
        right_col=(3, 105, 161, 255),
        thick=th
    )

    # Top Deck: Address Bar Slot
    slot_pts = [
        (cx - int(12 * scale), cy - int(12 * scale)),
        (cx + int(18 * scale), cy + int(3 * scale)),
        (cx + int(12 * scale), cy + int(6 * scale)),
        (cx - int(18 * scale), cy - int(9 * scale)),
    ]
    draw.polygon(slot_pts, fill=(255, 255, 255, 60))

    # Traffic light window dots on top deck
    dot_r = int(2.5 * scale)
    dots = [
        (cx - int(24 * scale), cy - int(12 * scale), (239, 68, 68, 255)),   # Red
        (cx - int(19 * scale), cy - int(9.5 * scale), (245, 158, 11, 255)), # Amber
        (cx - int(14 * scale), cy - int(7 * scale), (16, 185, 129, 255)),   # Green
    ]
    for dx, dy, col in dots:
        draw.ellipse([dx - dot_r, dy - int(dot_r * 0.6), dx + dot_r, dy + int(dot_r * 0.6)], fill=col)

    # Center Radiant Aperture / Identity Diamond
    core_y = int(cy - 20 * scale)
    cw = int(10 * scale)
    ch = int(5 * scale)
    core_pts = [
        (cx, core_y - ch),
        (cx + cw, core_y),
        (cx, core_y + ch),
        (cx - cw, core_y),
    ]
    draw.polygon(core_pts, fill=(255, 255, 255, 255))
    draw.ellipse(
        [cx - int(3 * scale), core_y - int(1.8 * scale), cx + int(3 * scale), core_y + int(1.8 * scale)],
        fill=(2, 132, 199, 255)
    )

    # High quality downsampling
    return im.resize((size, size), Image.Resampling.LANCZOS)


# Generate Raster Suite
render_master_raster(16).save(STATIC_DIR / "favicon-16x16.png", "PNG")
render_master_raster(32).save(STATIC_DIR / "favicon-32x32.png", "PNG")
render_master_raster(180, is_app_icon=True).save(STATIC_DIR / "apple-touch-icon.png", "PNG")
render_master_raster(512, is_app_icon=True).save(STATIC_DIR / "favicon.png", "PNG")

# Multi-resolution ICO (16, 32, 48, 64)
ico_sizes = [16, 32, 48, 64]
ico_images = [render_master_raster(s) for s in ico_sizes]
ico_images[0].save(
    STATIC_DIR / "favicon.ico",
    format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print("SUCCESS: All master raster assets regenerated cleanly.")
