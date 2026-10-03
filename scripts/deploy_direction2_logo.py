#!/usr/bin/env python3
"""
Deploy Direction 02: "The Isometric Container Cube"
Generates:
  - app/static/img/logo.svg (Master Freestanding Mark)
  - app/static/img/logo-full.svg (Horizontal Brand Lockup)
  - app/static/favicon.svg (Scalable SVG Favicon)
  - app/static/favicon-16x16.png
  - app/static/favicon-32x32.png
  - app/static/apple-touch-icon.png (180x180)
  - app/static/favicon.png (512x512)
  - app/static/favicon.ico (Multi-size ICO)
"""

from pathlib import Path
from PIL import Image, ImageDraw

STATIC_DIR = Path("/www/wwwroot/profilestack/app/static")
IMG_DIR = STATIC_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Master Freestanding Mark (logo.svg) ────────────────────────────────────
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <!-- Top Face: Active Chromium Viewport -->
    <linearGradient id="cubeTop" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="50%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <!-- Left Face: Docker & Kernel Isolation -->
    <linearGradient id="cubeLeft" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e40af" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>

    <!-- Right Face: Fingerprint Spoofing & Network Tunnel -->
    <linearGradient id="cubeRight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1e3a8a" />
    </linearGradient>

    <!-- Radiant P-Shield Core -->
    <linearGradient id="cubeGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="60%" stop-color="#7dd3fc" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>

    <filter id="cubeDropShadow" x="-25%" y="-20%" width="150%" height="150%">
      <feDropShadow dx="0" dy="8" stdDeviation="7" flood-color="#0f172a" flood-opacity="0.32" />
    </filter>
  </defs>

  <g filter="url(#cubeDropShadow)" transform="translate(60, 58)">
    <!-- Base Isometric Container Cube -->
    <!-- Left Face (Docker Isolation) -->
    <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="url(#cubeLeft)" />
    <!-- Right Face (Proxy & Network Tunnel) -->
    <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="url(#cubeRight)" />
    <!-- Top Face (Chromium Viewport) -->
    <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="url(#cubeTop)" />

    <!-- Precision Chamfer / Inset Rim on Top Face -->
    <path d="M 0,-4 L 40,-24 L 0,-44 L -40,-24 Z" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-opacity="0.45" />

    <!-- 3 Browser Control Dots in Isometric 3D Perspective -->
    <g transform="translate(-22, -26) skewX(-30) scale(1, 0.58)">
      <circle cx="-8" cy="0" r="3.2" fill="#ef4444" />
      <circle cx="-8" cy="-0.6" r="1.4" fill="#fca5a5" opacity="0.6" />

      <circle cx="0" cy="0" r="3.2" fill="#f59e0b" />
      <circle cx="0" cy="-0.6" r="1.4" fill="#fde68a" opacity="0.6" />

      <circle cx="8" cy="0" r="3.2" fill="#10b981" />
      <circle cx="8" cy="-0.6" r="1.4" fill="#a7f3d0" opacity="0.6" />
    </g>

    <!-- Address Bar Slot in Top Face -->
    <path d="M -12,-20 L 24,-20 L 16,-12 L -20,-12 Z" fill="#ffffff" opacity="0.22" />

    <!-- Stepped Containment Cuts on Left Face (Representing the 3 Stacked Layers) -->
    <line x1="-36" y1="-8" x2="0" y2="12" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.65" />
    <line x1="-36" y1="9" x2="0" y2="29" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.65" />

    <!-- Stepped Containment Cuts on Right Face -->
    <line x1="36" y1="-8" x2="0" y2="12" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.65" />
    <line x1="36" y1="9" x2="0" y2="29" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.65" />

    <!-- Floating Identity Shield Node on Front Center Spine -->
    <g transform="translate(0, 20)">
      <!-- Radiant Hexagonal Core Shield -->
      <polygon points="0,-12 11,-6 11,6 0,12 -11,6 -11,-6" fill="url(#cubeGlow)" />
      <!-- Precision P Monogram Cutout -->
      <path d="M -3.2,-6 L 1.2,-6 C 3.6,-6 5.4,-4.2 5.4,-2 C 5.4,0.2 3.6,2 1.2,2 L -1,2 L -1,6 C -1,6.6 -1.4,7 -2,7 C -2.6,7 -3.2,6.6 -3.2,6 Z M -1,-4 L -1,0 L 1,0 C 1.8,0 2.8,-0.4 2.8,-2 C 2.8,-3.6 1.8,-4 1,-4 Z" fill="#0f172a" />
      <circle cx="0" cy="0" r="1.2" fill="#38bdf8" />
    </g>
  </g>
</svg>
"""

# ── 2. Full Horizontal Brand Lockup (logo-full.svg) ───────────────────────────
LOGO_FULL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 290 68" width="100%" height="100%">
  <defs>
    <linearGradient id="flCubeTop" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>
    <linearGradient id="flCubeLeft" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e40af" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="flCubeRight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1e3a8a" />
    </linearGradient>
    <linearGradient id="flCore" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <filter id="flDrop" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.25" />
    </filter>
  </defs>

  <!-- Left Freestanding Cube Mark -->
  <g transform="translate(10, 6)" filter="url(#flDrop)">
    <g transform="translate(26, 27) scale(0.55)">
      <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="url(#flCubeLeft)" />
      <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="url(#flCubeRight)" />
      <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="url(#flCubeTop)" />
      
      <!-- Top Chamfer -->
      <path d="M 0,-4 L 40,-24 L 0,-44 L -40,-24 Z" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-opacity="0.45" />
      
      <!-- Window Dots -->
      <g transform="translate(-22, -26) skewX(-30) scale(1, 0.58)">
        <circle cx="-8" cy="0" r="3.2" fill="#ef4444" />
        <circle cx="0" cy="0" r="3.2" fill="#f59e0b" />
        <circle cx="8" cy="0" r="3.2" fill="#10b981" />
      </g>
      
      <!-- Front Shield Core -->
      <polygon points="0,-12 11,-6 11,6 0,12 -11,6 -11,-6" transform="translate(0, 20)" fill="url(#flCore)" />
      <path d="M -3.2,14 L 1.2,14 C 3.6,14 5.4,15.8 5.4,18 C 5.4,20.2 3.6,22 1.2,22 L -1,22 L -1,26 C -1,26.6 -1.4,27 -2,27 C -2.6,27 -3.2,26.6 -3.2,26 Z" fill="#0f172a" />
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
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="100%" height="100%">
  <defs>
    <linearGradient id="favCubeTop" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="50%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>
    <linearGradient id="favCubeLeft" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e40af" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="favCubeRight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1e3a8a" />
    </linearGradient>
    <linearGradient id="favCore" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
  </defs>

  <g transform="translate(32, 32) scale(0.62)">
    <!-- Base Isometric Cube -->
    <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="url(#favCubeLeft)" />
    <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="url(#favCubeRight)" />
    <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="url(#favCubeTop)" />

    <!-- Rim highlight -->
    <path d="M 0,-4 L 40,-24 L 0,-44 L -40,-24 Z" fill="none" stroke="#ffffff" stroke-width="1.4" stroke-opacity="0.5" />

    <!-- 3 Window Dots in 3D Perspective -->
    <g transform="translate(-22, -26) skewX(-30) scale(1, 0.58)">
      <circle cx="-9" cy="0" r="4.2" fill="#ef4444" />
      <circle cx="0" cy="0" r="4.2" fill="#f59e0b" />
      <circle cx="9" cy="0" r="4.2" fill="#10b981" />
    </g>

    <!-- Address slot -->
    <path d="M -12,-20 L 24,-20 L 16,-12 L -20,-12 Z" fill="#ffffff" opacity="0.25" />

    <!-- Shield Core -->
    <polygon points="0,-13 12,-6 12,6 0,13 -12,6 -12,-6" transform="translate(0, 20)" fill="url(#favCore)" />
    <circle cx="0" cy="20" r="3.2" fill="#0284c7" />
  </g>
</svg>
"""

# Save Vectors
with open(IMG_DIR / "logo.svg", "w") as f:
    f.write(LOGO_SVG.strip())

with open(IMG_DIR / "logo-full.svg", "w") as f:
    f.write(LOGO_FULL_SVG.strip())

with open(STATIC_DIR / "favicon.svg", "w") as f:
    f.write(FAVICON_SVG.strip())

print("SAVED: logo.svg, logo-full.svg, favicon.svg")


# ── 4. Precision Raster Rendering via Pillow ──────────────────────────────────
def render_direction2_raster(size: int, is_app_icon: bool = False) -> Image.Image:
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
        draw.rounded_rectangle(
            [pad + scale, pad + scale, canvas_size - pad - scale, canvas_size - pad - scale],
            radius=corner_r - scale,
            outline=(96, 165, 250, 60),
            width=int(1.5 * scale)
        )

    # Center Cube Coordinates
    cx = canvas_size // 2
    cy = int(canvas_size * 0.52)
    w = int(canvas_size * 0.38)
    h = int(w * 0.52)
    depth = int(w * 1.08)

    # Left Face (Docker Isolation)
    left_pts = [
        (cx, cy),
        (cx - w, cy - h),
        (cx - w, cy - h + depth),
        (cx, cy + depth),
    ]
    draw.polygon(left_pts, fill=(20, 45, 120, 255))

    # Right Face (Proxy & Network)
    right_pts = [
        (cx, cy),
        (cx + w, cy - h),
        (cx + w, cy - h + depth),
        (cx, cy + depth),
    ]
    draw.polygon(right_pts, fill=(37, 99, 235, 255))

    # Top Face (Chromium Viewport)
    top_pts = [
        (cx, cy),
        (cx + w, cy - h),
        (cx, cy - 2 * h),
        (cx - w, cy - h),
    ]
    draw.polygon(top_pts, fill=(56, 189, 248, 255))

    # Top Inset Rim
    inset = int(3 * scale)
    top_inset = [
        (cx, cy - inset),
        (cx + w - inset, cy - h),
        (cx, cy - 2 * h + inset),
        (cx - w + inset, cy - h),
    ]
    draw.polygon(top_inset, outline=(255, 255, 255, 120), fill=(2, 132, 199, 255))

    # Browser Window Dots on Top Face
    dot_r = int(2.8 * scale)
    dots = [
        (cx - int(20 * scale), cy - int(24 * scale), (239, 68, 68, 255)),   # Red
        (cx - int(14 * scale), cy - int(21 * scale), (245, 158, 11, 255)),  # Amber
        (cx - int(8 * scale), cy - int(18 * scale), (16, 185, 129, 255)),   # Green
    ]
    for dx, dy, col in dots:
        draw.ellipse([dx - dot_r, dy - int(dot_r * 0.6), dx + dot_r, dy + int(dot_r * 0.6)], fill=col)

    # Address bar slot on top face
    slot_pts = [
        (cx - int(4 * scale), cy - int(16 * scale)),
        (cx + int(20 * scale), cy - int(16 * scale)),
        (cx + int(14 * scale), cy - int(10 * scale)),
        (cx - int(10 * scale), cy - int(10 * scale)),
    ]
    draw.polygon(slot_pts, fill=(255, 255, 255, 60))

    # Center Radiant Shield Node on Front Center Spine
    core_y = int(cy + depth * 0.42)
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

    return im.resize((size, size), Image.Resampling.LANCZOS)


# Generate Raster Suite
render_direction2_raster(16).save(STATIC_DIR / "favicon-16x16.png", "PNG")
render_direction2_raster(32).save(STATIC_DIR / "favicon-32x32.png", "PNG")
render_direction2_raster(180, is_app_icon=True).save(STATIC_DIR / "apple-touch-icon.png", "PNG")
render_direction2_raster(512, is_app_icon=True).save(STATIC_DIR / "favicon.png", "PNG")

# Multi-resolution ICO (16, 32, 48, 64)
ico_sizes = [16, 32, 48, 64]
ico_images = [render_direction2_raster(s) for s in ico_sizes]
ico_images[0].save(
    STATIC_DIR / "favicon.ico",
    format="ICO",
    sizes=[(s, s) for s in ico_sizes],
    append_images=ico_images[1:]
)
print("SUCCESS: Direction 02 master assets deployed cleanly.")
