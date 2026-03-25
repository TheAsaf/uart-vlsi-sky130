#!/usr/bin/env python3
"""Generate architecture and register-map diagrams as SVG for the UART project."""

import os

IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMG_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 1.  Architecture block diagram
# ---------------------------------------------------------------------------

def gen_architecture_svg():
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 420" font-family="Inter, system-ui, -apple-system, sans-serif">
  <defs>
    <filter id="shadow" x="-4%" y="-4%" width="108%" height="108%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#00000018"/>
    </filter>
    <linearGradient id="headerGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1E40AF"/>
      <stop offset="100%" stop-color="#1E3A8A"/>
    </linearGradient>
    <linearGradient id="txGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#DBEAFE"/>
      <stop offset="100%" stop-color="#BFDBFE"/>
    </linearGradient>
    <linearGradient id="rxGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FEE2E2"/>
      <stop offset="100%" stop-color="#FECACA"/>
    </linearGradient>
    <linearGradient id="fifoGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FEF3C7"/>
      <stop offset="100%" stop-color="#FDE68A"/>
    </linearGradient>
    <linearGradient id="regGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#E0E7FF"/>
      <stop offset="100%" stop-color="#C7D2FE"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="880" height="420" rx="12" fill="#F8FAFC"/>

  <!-- uart_top boundary -->
  <rect x="120" y="50" width="640" height="340" rx="10" fill="white" stroke="#1E40AF" stroke-width="2" filter="url(#shadow)"/>
  <rect x="120" y="50" width="640" height="32" rx="10" fill="url(#headerGrad)"/>
  <rect x="120" y="72" width="640" height="10" fill="url(#headerGrad)"/>
  <text x="440" y="72" text-anchor="middle" fill="white" font-size="14" font-weight="700">uart_top</text>

  <!-- Register Interface block -->
  <rect x="150" y="120" width="160" height="240" rx="8" fill="url(#regGrad)" stroke="#6366F1" stroke-width="1.5"/>
  <text x="230" y="145" text-anchor="middle" fill="#312E81" font-size="12" font-weight="700">Register</text>
  <text x="230" y="162" text-anchor="middle" fill="#312E81" font-size="12" font-weight="700">Interface</text>

  <!-- Register names -->
  <rect x="168" y="180" width="124" height="24" rx="4" fill="white" stroke="#A5B4FC" stroke-width="1"/>
  <text x="230" y="196" text-anchor="middle" fill="#4338CA" font-size="10" font-weight="600">0x0  TX_DATA</text>
  <rect x="168" y="210" width="124" height="24" rx="4" fill="white" stroke="#A5B4FC" stroke-width="1"/>
  <text x="230" y="226" text-anchor="middle" fill="#4338CA" font-size="10" font-weight="600">0x1  RX_DATA</text>
  <rect x="168" y="240" width="124" height="24" rx="4" fill="white" stroke="#A5B4FC" stroke-width="1"/>
  <text x="230" y="256" text-anchor="middle" fill="#4338CA" font-size="10" font-weight="600">0x2  STATUS</text>
  <rect x="168" y="270" width="124" height="24" rx="4" fill="white" stroke="#A5B4FC" stroke-width="1"/>
  <text x="230" y="286" text-anchor="middle" fill="#4338CA" font-size="10" font-weight="600">0x3  CTRL</text>

  <!-- TX FIFO block -->
  <rect x="380" y="120" width="130" height="100" rx="8" fill="url(#fifoGrad)" stroke="#D97706" stroke-width="1.5"/>
  <text x="445" y="155" text-anchor="middle" fill="#92400E" font-size="12" font-weight="700">sync_fifo</text>
  <text x="445" y="175" text-anchor="middle" fill="#92400E" font-size="11">(8-deep TX)</text>
  <text x="445" y="195" text-anchor="middle" fill="#92400E" font-size="10">ptr-based</text>

  <!-- uart_tx block -->
  <rect x="580" y="120" width="150" height="100" rx="8" fill="url(#txGrad)" stroke="#2563EB" stroke-width="1.5"/>
  <text x="655" y="155" text-anchor="middle" fill="#1E3A8A" font-size="12" font-weight="700">uart_tx</text>
  <text x="655" y="175" text-anchor="middle" fill="#1E3A8A" font-size="11">8N1 / 8E1 / 8O1</text>
  <text x="655" y="195" text-anchor="middle" fill="#1E3A8A" font-size="10">baud generator</text>

  <!-- uart_rx block -->
  <rect x="440" y="270" width="190" height="100" rx="8" fill="url(#rxGrad)" stroke="#DC2626" stroke-width="1.5"/>
  <text x="535" y="300" text-anchor="middle" fill="#991B1B" font-size="12" font-weight="700">uart_rx</text>
  <text x="535" y="320" text-anchor="middle" fill="#991B1B" font-size="11">2-FF sync + mid-bit sample</text>
  <text x="535" y="340" text-anchor="middle" fill="#991B1B" font-size="10">parity check + frame detect</text>

  <!-- Arrows: Reg → FIFO -->
  <line x1="310" y1="170" x2="380" y2="170" stroke="#6366F1" stroke-width="2" marker-end="url(#arrowPurple)"/>
  <defs><marker id="arrowPurple" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 Z" fill="#6366F1"/></marker></defs>

  <!-- Arrows: FIFO → TX -->
  <line x1="510" y1="170" x2="580" y2="170" stroke="#D97706" stroke-width="2" marker-end="url(#arrowAmber)"/>
  <defs><marker id="arrowAmber" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 Z" fill="#D97706"/></marker></defs>

  <!-- Arrows: RX → Reg -->
  <line x1="440" y1="320" x2="310" y2="260" stroke="#DC2626" stroke-width="2" marker-end="url(#arrowRed)"/>
  <defs><marker id="arrowRed" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 Z" fill="#DC2626"/></marker></defs>

  <!-- External signals — Left side -->
  <text x="20" y="145" fill="#374151" font-size="11" font-weight="600">addr[2:0]</text>
  <line x1="95" y1="142" x2="150" y2="142" stroke="#374151" stroke-width="1.5" marker-end="url(#arrowGray)"/>
  <text x="20" y="175" fill="#374151" font-size="11" font-weight="600">wdata[7:0]</text>
  <line x1="95" y1="172" x2="150" y2="172" stroke="#374151" stroke-width="1.5" marker-end="url(#arrowGray)"/>
  <text x="20" y="205" fill="#374151" font-size="11" font-weight="600">wen / ren</text>
  <line x1="95" y1="202" x2="150" y2="202" stroke="#374151" stroke-width="1.5" marker-end="url(#arrowGray)"/>
  <text x="20" y="235" fill="#374151" font-size="11" font-weight="600">rdata[7:0]</text>
  <line x1="150" y1="232" x2="95" y2="232" stroke="#374151" stroke-width="1.5" marker-end="url(#arrowGrayL)"/>

  <defs>
    <marker id="arrowGray" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill="#374151"/></marker>
    <marker id="arrowGrayL" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">
      <path d="M8,0 L0,3 L8,6 Z" fill="#374151"/></marker>
  </defs>

  <!-- External signals — Right side (UART pins) -->
  <text x="790" y="175" fill="#2563EB" font-size="12" font-weight="700">TX →</text>
  <line x1="730" y1="170" x2="785" y2="170" stroke="#2563EB" stroke-width="2" marker-end="url(#arrowBlue)"/>
  <defs><marker id="arrowBlue" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 Z" fill="#2563EB"/></marker></defs>

  <text x="790" y="335" fill="#DC2626" font-size="12" font-weight="700">→ RX</text>
  <line x1="785" y1="330" x2="630" y2="330" stroke="#DC2626" stroke-width="2" marker-end="url(#arrowRedL)"/>
  <defs><marker id="arrowRedL" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">
    <path d="M8,0 L0,3 L8,6 Z" fill="#DC2626"/></marker></defs>

  <!-- Clock and Reset — Top -->
  <text x="20" y="330" fill="#6B7280" font-size="11" font-weight="600">clk</text>
  <text x="20" y="350" fill="#6B7280" font-size="11" font-weight="600">rst_n</text>

  <!-- IRQ — Bottom -->
  <text x="20" y="380" fill="#9333EA" font-size="11" font-weight="700">irq</text>
  <line x1="150" y1="376" x2="55" y2="376" stroke="#9333EA" stroke-width="1.5" marker-end="url(#arrowPurpleL)"/>
  <defs><marker id="arrowPurpleL" markerWidth="8" markerHeight="6" refX="0" refY="3" orient="auto">
    <path d="M8,0 L0,3 L8,6 Z" fill="#9333EA"/></marker></defs>

  <!-- Legend / feature callouts -->
  <rect x="580" y="245" width="150" height="18" rx="4" fill="#EFF6FF"/>
  <text x="655" y="258" text-anchor="middle" fill="#1E40AF" font-size="8" font-weight="600">configurable parity</text>
  <rect x="440" y="245" width="120" height="18" rx="4" fill="#FEF3C7"/>
  <text x="500" y="258" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">burst writes OK</text>
  <rect x="440" y="375" width="190" height="18" rx="4" fill="#FEE2E2"/>
  <text x="535" y="388" text-anchor="middle" fill="#991B1B" font-size="8" font-weight="600">metastability-safe async input</text>

</svg>'''

    path = os.path.join(IMG_DIR, "architecture.svg")
    with open(path, "w") as f:
        f.write(svg)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# 2.  Register map diagram
# ---------------------------------------------------------------------------

def gen_regmap_svg():
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 380" font-family="Inter, system-ui, -apple-system, sans-serif">
  <defs>
    <filter id="shadow" x="-2%" y="-2%" width="104%" height="108%">
      <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#00000012"/>
    </filter>
  </defs>
  <rect width="780" height="380" rx="10" fill="#F8FAFC"/>
  <text x="390" y="30" text-anchor="middle" fill="#111827" font-size="15" font-weight="700">UART Register Map</text>

  <!-- Bit position header -->
  <g transform="translate(170, 42)">
    <text x="0" y="14" fill="#6B7280" font-size="9" font-weight="600">Bit</text>
    <text x="560" y="14" text-anchor="end" fill="#6B7280" font-size="9">Addr</text>
  </g>
  <g transform="translate(200, 42)" font-size="9" fill="#6B7280" text-anchor="middle" font-weight="600">
    <text x="18" y="14">7</text><text x="78" y="14">6</text><text x="138" y="14">5</text><text x="198" y="14">4</text>
    <text x="258" y="14">3</text><text x="318" y="14">2</text><text x="378" y="14">1</text><text x="438" y="14">0</text>
  </g>

  <!-- Register 0x0: TX_DATA -->
  <g transform="translate(30, 62)">
    <text x="0" y="26" fill="#1E3A8A" font-size="12" font-weight="700">TX_DATA</text>
    <text x="0" y="42" fill="#6B7280" font-size="9">[W] Write-only</text>
    <text x="700" y="28" fill="#4B5563" font-size="11" font-weight="600" text-anchor="end">0x0</text>
    <rect x="170" y="8" width="480" height="36" rx="6" fill="#DBEAFE" stroke="#93C5FD" stroke-width="1.5" filter="url(#shadow)"/>
    <text x="410" y="32" text-anchor="middle" fill="#1E40AF" font-size="12" font-weight="600">tx_data[7:0]</text>
  </g>

  <!-- Register 0x1: RX_DATA -->
  <g transform="translate(30, 130)">
    <text x="0" y="26" fill="#991B1B" font-size="12" font-weight="700">RX_DATA</text>
    <text x="0" y="42" fill="#6B7280" font-size="9">[R] Clears rx_ready</text>
    <text x="700" y="28" fill="#4B5563" font-size="11" font-weight="600" text-anchor="end">0x1</text>
    <rect x="170" y="8" width="480" height="36" rx="6" fill="#FEE2E2" stroke="#FCA5A5" stroke-width="1.5" filter="url(#shadow)"/>
    <text x="410" y="32" text-anchor="middle" fill="#991B1B" font-size="12" font-weight="600">rx_data[7:0]</text>
  </g>

  <!-- Register 0x2: STATUS -->
  <g transform="translate(30, 198)">
    <text x="0" y="26" fill="#065F46" font-size="12" font-weight="700">STATUS</text>
    <text x="0" y="42" fill="#6B7280" font-size="9">[R/W1C] Errors are W1C</text>
    <text x="700" y="28" fill="#4B5563" font-size="11" font-weight="600" text-anchor="end">0x2</text>

    <!-- Reserved bits 7-6 -->
    <rect x="170" y="8" width="60" height="36" rx="0" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1"/>
    <rect x="230" y="8" width="60" height="36" rx="0" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1"/>
    <text x="200" y="30" text-anchor="middle" fill="#9CA3AF" font-size="9">—</text>
    <text x="260" y="30" text-anchor="middle" fill="#9CA3AF" font-size="9">—</text>

    <!-- parity_err [5] -->
    <rect x="290" y="8" width="60" height="36" rx="0" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="320" y="24" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">parity</text>
    <text x="320" y="36" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">_err</text>

    <!-- frame_err [4] -->
    <rect x="350" y="8" width="60" height="36" rx="0" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="380" y="24" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">frame</text>
    <text x="380" y="36" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">_err</text>

    <!-- rx_ready [3] -->
    <rect x="410" y="8" width="60" height="36" rx="0" fill="#D1FAE5" stroke="#34D399" stroke-width="1.5"/>
    <text x="440" y="24" text-anchor="middle" fill="#065F46" font-size="8" font-weight="600">rx</text>
    <text x="440" y="36" text-anchor="middle" fill="#065F46" font-size="8" font-weight="600">_ready</text>

    <!-- fifo_full [2] -->
    <rect x="470" y="8" width="60" height="36" rx="0" fill="#EDE9FE" stroke="#8B5CF6" stroke-width="1.5"/>
    <text x="500" y="24" text-anchor="middle" fill="#5B21B6" font-size="8" font-weight="600">fifo</text>
    <text x="500" y="36" text-anchor="middle" fill="#5B21B6" font-size="8" font-weight="600">_full</text>

    <!-- fifo_empty [1] -->
    <rect x="530" y="8" width="60" height="36" rx="0" fill="#EDE9FE" stroke="#8B5CF6" stroke-width="1.5"/>
    <text x="560" y="24" text-anchor="middle" fill="#5B21B6" font-size="8" font-weight="600">fifo</text>
    <text x="560" y="36" text-anchor="middle" fill="#5B21B6" font-size="8" font-weight="600">_empty</text>

    <!-- tx_busy [0] -->
    <rect x="590" y="8" width="60" height="36" rx="0" fill="#DBEAFE" stroke="#60A5FA" stroke-width="1.5"/>
    <text x="620" y="24" text-anchor="middle" fill="#1E40AF" font-size="8" font-weight="600">tx</text>
    <text x="620" y="36" text-anchor="middle" fill="#1E40AF" font-size="8" font-weight="600">_busy</text>

    <!-- Rounded corners on ends -->
    <rect x="170" y="8" width="480" height="36" rx="6" fill="none" stroke="#6B7280" stroke-width="0.5"/>
  </g>

  <!-- Register 0x3: CTRL -->
  <g transform="translate(30, 278)">
    <text x="0" y="26" fill="#4338CA" font-size="12" font-weight="700">CTRL</text>
    <text x="0" y="42" fill="#6B7280" font-size="9">[RW] Read-Write</text>
    <text x="700" y="28" fill="#4B5563" font-size="11" font-weight="600" text-anchor="end">0x3</text>

    <!-- Reserved bits 7-3 -->
    <rect x="170" y="8" width="300" height="36" rx="0" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1"/>
    <text x="320" y="30" text-anchor="middle" fill="#9CA3AF" font-size="10">— reserved —</text>

    <!-- irq_en [2] -->
    <rect x="470" y="8" width="60" height="36" rx="0" fill="#FCE7F3" stroke="#EC4899" stroke-width="1.5"/>
    <text x="500" y="24" text-anchor="middle" fill="#9D174D" font-size="8" font-weight="600">irq</text>
    <text x="500" y="36" text-anchor="middle" fill="#9D174D" font-size="8" font-weight="600">_en</text>

    <!-- parity_odd [1] -->
    <rect x="530" y="8" width="60" height="36" rx="0" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="560" y="24" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">parity</text>
    <text x="560" y="36" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">_odd</text>

    <!-- parity_en [0] -->
    <rect x="590" y="8" width="60" height="36" rx="0" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="620" y="24" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">parity</text>
    <text x="620" y="36" text-anchor="middle" fill="#92400E" font-size="8" font-weight="600">_en</text>

    <rect x="170" y="8" width="480" height="36" rx="6" fill="none" stroke="#6B7280" stroke-width="0.5"/>
  </g>

  <!-- W1C legend -->
  <g transform="translate(30, 340)">
    <rect x="0" y="0" width="14" height="14" rx="3" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1"/>
    <text x="22" y="12" fill="#6B7280" font-size="9">W1C (write-1-to-clear)</text>
    <rect x="180" y="0" width="14" height="14" rx="3" fill="#D1FAE5" stroke="#34D399" stroke-width="1"/>
    <text x="202" y="12" fill="#6B7280" font-size="9">Status flag</text>
    <rect x="310" y="0" width="14" height="14" rx="3" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1"/>
    <text x="332" y="12" fill="#6B7280" font-size="9">Reserved</text>
    <rect x="410" y="0" width="14" height="14" rx="3" fill="#EDE9FE" stroke="#8B5CF6" stroke-width="1"/>
    <text x="432" y="12" fill="#6B7280" font-size="9">FIFO status</text>
  </g>

</svg>'''

    path = os.path.join(IMG_DIR, "register_map.svg")
    with open(path, "w") as f:
        f.write(svg)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating SVG diagrams...")
    gen_architecture_svg()
    gen_regmap_svg()
    print("Done.")
