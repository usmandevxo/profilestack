#!/usr/bin/env python3
"""
Generate and render two creative logo concepts:
Concept 1: "The Interlocking PS Browser Stack" (Monogram of P + S formed from stacked browser viewports)
Concept 2: "The Isometric Browser Container Cube" (3D precision container with browser window controls and identity core)
"""

from pathlib import Path

OUT_DIR = Path("/www/wwwroot/profilestack/app/static/img/concepts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── CONCEPT 1: The "PS" Browser Stack Monogram ────────────────────────────────
# A freestanding, ultra-modern tech mark.
# The vertical container spine + 3 dynamic browser tab plates create:
#  - A bold "P" (Profile)
#  - An energetic "S" (Stack)
#  - Browser viewports with tab notch and status beacon
CONCEPT_1_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <linearGradient id="pStemGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#3b82f6" />
      <stop offset="50%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>

    <linearGradient id="tab1Grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>

    <linearGradient id="tab2Grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" />
      <stop offset="100%" stop-color="#2563eb" />
    </linearGradient>

    <linearGradient id="tab3Grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#818cf8" />
      <stop offset="100%" stop-color="#4f46e5" />
    </linearGradient>

    <filter id="c1Shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#1e3a8a" flood-opacity="0.32" />
    </filter>
  </defs>

  <g filter="url(#c1Shadow)">
    <!-- Vertical Backbone Spine (The Docker Host Rail) -->
    <rect x="20" y="16" width="16" height="88" rx="8" fill="url(#pStemGrad)" />

    <!-- Plate 1 (Top Browser Tab): Forms the top of 'P' -->
    <path d="M 28,16 L 82,16 C 91.9,16 100,24.1 100,34 C 100,43.9 91.9,52 82,52 L 36,52" 
          fill="none" stroke="url(#tab1Grad)" stroke-width="16" stroke-linecap="round" />
    
    <!-- Plate 2 (Middle S-Curve Ribbon): Connects 'P' loop into 'S' spine -->
    <path d="M 68,52 L 44,52 C 34.1,52 26,60.1 26,70 C 26,79.9 34.1,88 44,88 L 88,88" 
          fill="none" stroke="url(#tab2Grad)" stroke-width="14" stroke-linecap="round" />

    <!-- Plate 3 (Bottom Terminal Shelf): Finishes the 'S' flourish -->
    <rect x="52" y="88" width="44" height="16" rx="8" fill="url(#tab3Grad)" />

    <!-- Browser Controls Dots embedded in top plate (The Browser Signature) -->
    <circle cx="44" cy="34" r="3.2" fill="#ffffff" />
    <circle cx="56" cy="34" r="3.2" fill="#bae6fd" />
    <circle cx="68" cy="34" r="3.2" fill="#7dd3fc" />

    <!-- Active Shield Iris (Bottom of P loop) -->
    <circle cx="82" cy="34" r="4.5" fill="#ffffff" />
    <circle cx="82" cy="34" r="2.2" fill="#0284c7" />
  </g>
</svg>
"""

# ── CONCEPT 2: The "Layered Isometric Browser Sandbox" (High-Tech 3D Cube) ───
# An isometric container cube whose top facet is a live Chromium browser window,
# front facet is the anti-detect spoofing matrix, and side facet is proxy routing.
CONCEPT_2_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <!-- Top Face: Active Browser Window -->
    <linearGradient id="c2Top" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="50%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <!-- Left Face: Docker & Kernel Isolation -->
    <linearGradient id="c2Left" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e40af" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>

    <!-- Right Face: Fingerprint Spoofing & Network Tunnel -->
    <linearGradient id="c2Right" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1e3a8a" />
    </linearGradient>

    <linearGradient id="c2Glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>

    <filter id="c2Shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#0f172a" flood-opacity="0.38" />
    </filter>
  </defs>

  <g filter="url(#c2Shadow)" transform="translate(60, 60)">
    <!-- Base Isometric Cube -->
    <!-- Left Face (Docker Isolation) -->
    <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="url(#c2Left)" />
    <!-- Right Face (Proxy & Network) -->
    <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="url(#c2Right)" />
    <!-- Top Face (Chromium Viewport) -->
    <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="url(#c2Top)" />

    <!-- Precision Chamfer / Border Inset on Top Face -->
    <path d="M 0,-4 L 40,-24 L 0,-44 L -40,-24 Z" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-opacity="0.4" />

    <!-- 3 Browser Control Dots on Top Face (Red, Amber, Green in 3D perspective) -->
    <!-- Transformed to match isometric top plane -->
    <g transform="translate(-22, -26) skewX(-30) scale(1, 0.58)">
      <circle cx="-8" cy="0" r="3.2" fill="#ef4444" />
      <circle cx="0" cy="0" r="3.2" fill="#f59e0b" />
      <circle cx="8" cy="0" r="3.2" fill="#10b981" />
    </g>

    <!-- Address Bar Slot in Top Face -->
    <path d="M -12,-20 L 24,-20 L 16,-12 L -20,-12 Z" fill="#ffffff" opacity="0.2" />

    <!-- Stepped Containment Cuts on Left Face (Representing the 3 Stacked Layers) -->
    <line x1="-36" y1="-8" x2="0" y2="12" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.6" />
    <line x1="-36" y1="9" x2="0" y2="29" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.6" />

    <!-- Stepped Containment Cuts on Right Face -->
    <line x1="36" y1="-8" x2="0" y2="12" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.6" />
    <line x1="36" y1="9" x2="0" y2="29" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="4 3" stroke-opacity="0.6" />

    <!-- Floating Identity Shield Glyph on Front Spine -->
    <g transform="translate(0, 20)">
      <!-- Radiant Hexagonal Core Node -->
      <polygon points="0,-12 10,-6 10,6 0,12 -10,6 -10,-6" fill="url(#c2Glow)" />
      <!-- Stylized P cutout in center of node -->
      <path d="M -3,-6 L 1,-6 C 3.2,-6 5,-4.2 5,-2 C 5,0.2 3.2,2 1,2 L -3,2 Z M -1,-4 L -1,0 L 1,0 C 1.6,0 2.5,-0.4 2.5,-2 C 2.5,-3.6 1.6,-4 1,-4 Z" fill="#0f172a" />
      <line x1="-3" y1="2" x2="-3" y2="6" stroke="#0f172a" stroke-width="1.8" stroke-linecap="round" />
    </g>
  </g>
</svg>
"""

# ── CONCEPT 3: "The Stacked Browser Aperture" (Modernist Minimalist Icon) ─────
# Pure, iconic, freestanding geometry.
# Three overlapping browser cards sliding diagonally forward with precision rounded corners,
# featuring a clean tab bar, address pill, and an interlocking shield silhouette.
CONCEPT_3_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="100%" height="100%">
  <defs>
    <!-- Card 1: Foundation (Host / Docker) -->
    <linearGradient id="card1Grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e3a8a" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>

    <!-- Card 2: Middleware (Anti-Detect Sandbox) -->
    <linearGradient id="card2Grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#1d4ed8" />
    </linearGradient>

    <!-- Card 3: Top (Active Chromium Profile) -->
    <linearGradient id="card3Grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" />
      <stop offset="60%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#0369a1" />
    </linearGradient>

    <filter id="c3Shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="5" flood-color="#0f172a" flood-opacity="0.3" />
    </filter>
  </defs>

  <g filter="url(#c3Shadow)">
    <!-- CARD 1 (Bottom Back Layer, shifted top-right) -->
    <g transform="translate(36, 14)">
      <rect x="0" y="0" width="62" height="48" rx="8" fill="url(#card1Grad)" opacity="0.75" />
      <rect x="0" y="0" width="62" height="12" rx="8" fill="#1e293b" opacity="0.6" />
      <circle cx="8" cy="6" r="2" fill="#64748b" />
      <circle cx="14" cy="6" r="2" fill="#64748b" />
      <circle cx="20" cy="6" r="2" fill="#64748b" />
    </g>

    <!-- CARD 2 (Middle Layer, centered) -->
    <g transform="translate(24, 28)">
      <rect x="0" y="0" width="64" height="50" rx="9" fill="url(#card2Grad)" />
      <rect x="0" y="0" width="64" height="13" rx="9" fill="#1e40af" opacity="0.7" />
      <circle cx="9" cy="6.5" r="2.2" fill="#93c5fd" />
      <circle cx="16" cy="6.5" r="2.2" fill="#93c5fd" />
      <circle cx="23" cy="6.5" r="2.2" fill="#93c5fd" />
    </g>

    <!-- CARD 3 (Top Front Layer, shifted bottom-left) -->
    <g transform="translate(12, 42)">
      <!-- Main Window Frame -->
      <rect x="0" y="0" width="68" height="54" rx="10" fill="url(#card3Grad)" />
      
      <!-- Top Titlebar / Tab Area -->
      <path d="M 0,10 C 0,4.47 4.47,0 10,0 L 58,0 C 63.53,0 68,4.47 68,10 L 68,15 L 0,15 Z" fill="#0284c7" opacity="0.95" />
      
      <!-- Precision Window Control Dots (Red, Amber, Green) -->
      <circle cx="9" cy="7.5" r="2.5" fill="#f87171" />
      <circle cx="16" cy="7.5" r="2.5" fill="#fbbf24" />
      <circle cx="23" cy="7.5" r="2.5" fill="#34d399" />

      <!-- Active Tab Pill (Highlighting the Current Profile) -->
      <path d="M 31,3 L 56,3 C 58,3 59,4 59,6 L 59,15 L 28,15 L 28,6 C 28,4 29,3 31,3 Z" fill="#ffffff" opacity="0.25" />

      <!-- Centered Modernist "P" Anti-Detect Monogram Mask inside Viewport -->
      <g transform="translate(34, 34)">
        <!-- Outer Glow Ring -->
        <circle cx="0" cy="0" r="13" fill="#ffffff" opacity="0.15" />
        <!-- Sharp Vector P & Stack Arrow -->
        <path d="M -5,-8 L 1,-8 C 4.5,-8 7.5,-5.5 7.5,-1.5 C 7.5,2.5 4.5,5 1,5 L -2,5 L -2,8 C -2,9 -2.5,9.5 -3.5,9.5 C -4.5,9.5 -5,9 -5,8 Z M -2,-5 L -2,2 L 0.5,2 C 2.5,2 4.5,0.8 4.5,-1.5 C 4.5,-3.8 2.5,-5 0.5,-5 Z" fill="#ffffff" />
        <!-- Radiant Accent Dot -->
        <circle cx="10" cy="-6" r="2.5" fill="#38bdf8" />
      </g>
    </g>
  </g>
</svg>
"""

with open(OUT_DIR / "concept1.svg", "w") as f:
    f.write(CONCEPT_1_SVG.strip())

with open(OUT_DIR / "concept2.svg", "w") as f:
    f.write(CONCEPT_2_SVG.strip())

with open(OUT_DIR / "concept3.svg", "w") as f:
    f.write(CONCEPT_3_SVG.strip())

print("SUCCESS: 3 Concepts generated in app/static/img/concepts/")

# [ProfileStack v1.29.20] revision checkpoint
