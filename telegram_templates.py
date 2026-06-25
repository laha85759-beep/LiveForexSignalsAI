"""
telegram_templates.py — Telegram card image generator.
Renders the 4 template designs from telegram_signal_templates.html as PNG images
so they can be sent via bot.send_photo().

Templates:
  1. make_signal_card()         — Forex / Crypto trade signal  (navy blue)
  2. make_news_alert_card()     — High-impact news alert       (dark navy)
  3. make_nse_signal_card()     — NSE / India market signal    (forest green)
  4. make_morning_briefing_card()— Daily morning briefing      (charcoal purple)
"""
import io
from PIL import Image, ImageDraw, ImageFont

# ── Palette (from HTML template CSS) ────────────────────────────────────────
C_WHITE  = (255, 255, 255)
C_GREEN  = ( 74, 222, 128)   # #4ade80  — BUY / up / TP
C_RED    = (248, 113, 113)   # #f87171  — SELL / down / SL
C_BLUE   = ( 96, 165, 250)   # #60a5fa  — entry / neutral
C_AMBER  = (251, 191,  36)   # #fbbf24  — R:R / amber
C_PURPLE = (192, 132, 252)   # #c084fc  — morning badge

BG_FOREX    = ( 30,  58,  95)   # Template 1  #1e3a5f  navy
BG_NEWS     = ( 26,  39,  68)   # Template 2  #1a2744  dark navy
BG_NSE      = ( 30,  45,  30)   # Template 3  #1e2d1e  forest green
BG_BRIEFING = ( 30,  30,  46)   # Template 4  #1e1e2e  charcoal

OUTER_BG = (18, 20, 30)         # outer canvas background

W   = 420   # bubble width (px)
PAD = 20    # outer canvas padding
IN  = 16    # inner bubble padding

# ── Font loading ─────────────────────────────────────────────────────────────
_FONT_REGULAR = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\verdana.ttf",
]
_FONT_BOLD = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\verdanab.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in (_FONT_BOLD if bold else _FONT_REGULAR):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Drawing helpers ──────────────────────────────────────────────────────────

def _rrect(draw: ImageDraw.ImageDraw, xy, r: int, fill) -> None:
    """Draw a filled rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)
    for ex, ey in [(x1, y1), (x2 - 2*r, y1), (x1, y2 - 2*r), (x2 - 2*r, y2 - 2*r)]:
        draw.ellipse([ex, ey, ex + 2*r, ey + 2*r], fill=fill)


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int,
           text: str, bg, fg, font) -> int:
    """Draw a pill-shaped badge. Returns badge width."""
    tw = int(draw.textlength(text, font=font))
    px, py = 10, 4
    bw = tw + px * 2
    bh = font.size + py * 2
    _rrect(draw, (x, y, x + bw, y + bh), 4, bg)
    draw.text((x + px, y + py), text, font=font, fill=fg)
    return bw


def _wrap_text(draw: ImageDraw.ImageDraw, text: str,
               font, max_w: int) -> list[str]:
    """Word-wrap text to fit max_w pixels."""
    words = text.split()
    lines, buf = [], ""
    for word in words:
        test = f"{buf} {word}".strip()
        if draw.textlength(test, font=font) <= max_w:
            buf = test
        else:
            if buf:
                lines.append(buf)
            buf = word
    if buf:
        lines.append(buf)
    return lines


def _divider(draw: ImageDraw.ImageDraw, cx: int, cw: int, cy: int) -> int:
    """Draw a 1-px separator line. Returns new cy."""
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    return cy + 10


def _row(draw: ImageDraw.ImageDraw,
         cx: int, cw: int, cy: int,
         label: str, value: str, val_col,
         f_label, f_val) -> int:
    """Draw a label │ value row. Returns new cy."""
    draw.text((cx, cy), label, font=f_label, fill=(255, 255, 255, 115))
    draw.text(
        (cw - int(draw.textlength(value, font=f_val)), cy),
        value, font=f_val, fill=val_col,
    )
    return cy + 26


def _header(draw: ImageDraw.ImageDraw,
            cx: int, cy: int, cw: int,
            icon_emoji: str, icon_bg,
            bot_sub: str,
            badge_text: str, badge_bg, badge_fg,
            f_sm, f_md, f_icon) -> int:
    """Draw standard Telegram-style header (icon + name + badge). Returns new cy."""
    icon_size = 36
    _rrect(draw, (cx, cy, cx + icon_size, cy + icon_size), 8, icon_bg)
    draw.text((cx + 5, cy + 4), icon_emoji, font=f_icon, fill=C_WHITE)

    name_x = cx + icon_size + 10
    draw.text((name_x, cy + 2),  "TradeSignal Pro", font=f_md,  fill=C_WHITE)
    draw.text((name_x, cy + 20), bot_sub,           font=f_sm,  fill=(255, 255, 255, 128))

    bw = len(badge_text) * 8 + 24  # rough badge width estimate
    _badge(draw, cw - bw, cy + 8, badge_text, badge_bg, badge_fg, f_sm)

    cy += icon_size + 14
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 30), width=1)
    return cy + 12


def _tag_row(draw: ImageDraw.ImageDraw, cx: int, cy: int, tags: list[str], font) -> int:
    """Draw a row of hashtag pills. Returns new cy."""
    tx = cx
    for tag in tags:
        t = f"#{tag}"
        tw = int(draw.textlength(t, font=font)) + 12
        _rrect(draw, (tx, cy, tx + tw, cy + 20), 4, (255, 255, 255, 18))
        draw.text((tx + 6, cy + 3), t, font=font, fill=(255, 255, 255, 100))
        tx += tw + 6
    return cy + 26


def _canvas(bg_color, bubble_w: int, height: int) -> tuple:
    """Create outer canvas + bubble, return (img, draw, cx, cy, cw, by2)."""
    total_w = bubble_w + PAD * 2
    img  = Image.new("RGBA", (total_w, height), OUTER_BG + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    bx1, by1 = PAD, PAD
    bx2, by2 = bubble_w + PAD, height - PAD

    _rrect(draw, (bx1, by1, bx2, by2), 16, bg_color)
    # Telegram-style flat bottom-left corner
    draw.rectangle([bx1, by2 - 16, bx1 + 16, by2], fill=bg_color)

    cx = bx1 + IN
    cw = bx2 - IN
    cy = by1 + IN
    return img, draw, cx, cy, cw, by2


# ─────────────────────────────────────────────────────────────────────────────
# Template 1 — Forex / Crypto Trade Signal  (navy #1e3a5f)
# ─────────────────────────────────────────────────────────────────────────────
def make_signal_card(
    pair: str,
    instrument_name: str,
    direction: str,          # "BUY" or "SELL"
    entry: str,
    sl: str,    sl_diff: str,
    tp1: str,   tp1_diff: str,
    tp2: str,   tp2_diff: str,
    rr: str,
    confidence: int,         # 0-100
    reason: str,
    tags: list[str],
    timeframe: str = "H1",
) -> Image.Image:
    """Render Template 1 — Trade Signal card. Returns PIL Image."""
    f10  = _font(13)
    f11  = _font(14)
    f12  = _font(15)
    f13  = _font(16)
    f15b = _font(19, bold=True)
    f20b = _font(22, bold=True)

    # Pre-calculate wrapped reason height
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    reason_lines = min(3, len(_wrap_text(dummy, reason, f11, W - IN * 2)))

    h = (PAD + 44 + 14 + 12   # header
         + 26 + 22             # title + subtitle
         + 10 + 1 + 10         # divider
         + 5 * 26              # 5 data rows
         + 10 + 1 + 10         # divider
         + 14 + 8 + 8 + 14     # confidence bar
         + 10 + 1 + 10         # divider
         + reason_lines * 18 + 8   # reason
         + 26                  # tags
         + 18                  # disclaimer
         + PAD)

    img, draw, cx, cy, cw, _ = _canvas(BG_FOREX, W, h)

    badge_bg = (26, 107, 60) if direction == "BUY" else (107, 26, 26)
    badge_fg = C_GREEN       if direction == "BUY" else C_RED

    cy = _header(draw, cx, cy, cw, "📡", (15, 52, 96), "AI-powered signals",
                 direction, badge_bg, badge_fg, f10, f13, f20b)

    dir_icon = "🟢 LONG" if direction == "BUY" else "🔴 SHORT"
    draw.text((cx, cy), f"{pair}  ·  {dir_icon}  ·  {timeframe}", font=f15b, fill=C_WHITE)
    cy += 26
    draw.text((cx, cy), instrument_name, font=f10, fill=(255, 255, 255, 115))
    cy += 22

    cy = _divider(draw, cx, cw, cy)

    rows = [
        ("Entry price",   entry,                    C_BLUE),
        ("Stop loss",     f"{sl}  (-{sl_diff})",    C_RED),
        ("Take profit 1", f"{tp1}  (+{tp1_diff})",  C_GREEN),
        ("Take profit 2", f"{tp2}  (+{tp2_diff})",  C_GREEN),
        ("Risk : Reward", f"1 : {rr}",              C_AMBER),
    ]
    for label, value, vc in rows:
        cy = _row(draw, cx, cw, cy, label, value, vc, f11, f12)

    cy = _divider(draw, cx, cw, cy)

    # Confidence bar
    draw.text((cx, cy), "AI confidence", font=f10, fill=(255, 255, 255, 115))
    cy += 14
    bar_w = cw - cx
    _rrect(draw, (cx, cy, cx + bar_w, cy + 6), 3, (255, 255, 255, 25))
    fill_w = max(4, int(bar_w * confidence / 100))
    _rrect(draw, (cx, cy, cx + fill_w, cy + 6), 3, C_GREEN)
    cy += 8
    draw.text((cx, cy), "0", font=f10, fill=(255, 255, 255, 100))
    conf_str = f"{confidence}%"
    conf_cx = cx + fill_w - int(draw.textlength(conf_str, font=f10)) // 2
    draw.text((conf_cx, cy), conf_str, font=f10, fill=C_GREEN)
    draw.text((cw - int(draw.textlength("100", font=f10)), cy), "100",
              font=f10, fill=(255, 255, 255, 100))
    cy += 14

    cy = _divider(draw, cx, cw, cy)

    for line in _wrap_text(draw, reason, f11, cw - cx)[:3]:
        draw.text((cx, cy), line, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    cy = _tag_row(draw, cx, cy, tags, f10)

    draw.text((cx, cy), "Not financial advice. Trade at your own risk.",
              font=f10, fill=(255, 255, 255, 90))

    return img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Template 2 — High-Impact News Alert  (dark navy #1a2744)
# ─────────────────────────────────────────────────────────────────────────────
def make_news_alert_card(
    title: str,
    asset: str,
    category: str,
    date_str: str,
    direction: str,       # "Bullish" | "Bearish" | "Neutral"
    confidence_pct: int,
    analysis: str,
    tags: list[str],
) -> Image.Image:
    """Render Template 2 — Breaking News Alert card. Returns PIL Image."""
    f10  = _font(13)
    f11  = _font(14)
    f11b = _font(14, bold=True)
    f12  = _font(15)
    f13  = _font(16)
    f15b = _font(19, bold=True)
    f20b = _font(22, bold=True)

    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    analysis_lines = min(4, len(_wrap_text(dummy, analysis, f11, W - IN * 2)))

    h = (PAD + 44 + 14 + 12
         + 26 + 22
         + 10 + 1 + 10
         + 3 * 26
         + 10 + 1 + 10
         + 18 + analysis_lines * 18 + 8
         + 26 + PAD)

    img, draw, cx, cy, cw, _ = _canvas(BG_NEWS, W, h)

    cy = _header(draw, cx, cy, cw, "📰", (26, 58, 107), "Market news",
                 "HIGH IMPACT", (26, 61, 107), C_BLUE, f10, f13, f20b)

    draw.text((cx, cy), title[:46], font=f15b, fill=C_BLUE)
    cy += 26
    draw.text((cx, cy), f"{asset}  ·  {category}  ·  {date_str}",
              font=f10, fill=(255, 255, 255, 115))
    cy += 22

    cy = _divider(draw, cx, cw, cy)

    dir_label = ("🟢 Bullish" if direction == "Bullish"
                 else "🔴 Bearish" if direction == "Bearish"
                 else "🟡 Neutral")
    dir_col   = (C_GREEN if direction == "Bullish"
                 else C_RED if direction == "Bearish"
                 else C_AMBER)
    rows = [
        ("Asset",       asset,                C_WHITE),
        ("Impact",      dir_label,            dir_col),
        ("Confidence",  f"{confidence_pct}%", C_AMBER),
    ]
    for label, value, vc in rows:
        cy = _row(draw, cx, cw, cy, label, value, vc, f11, f12)

    cy = _divider(draw, cx, cw, cy)

    draw.text((cx, cy), "Quick Analysis:", font=f11b, fill=C_WHITE)
    cy += 18
    for line in _wrap_text(draw, analysis, f11, cw - cx)[:4]:
        draw.text((cx, cy), line, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    _tag_row(draw, cx, cy, tags, f10)

    return img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Template 3 — NSE / India Market Signal  (forest green #1e2d1e)
# ─────────────────────────────────────────────────────────────────────────────
def make_nse_signal_card(
    index: str,
    asset: str,
    direction: str,          # "BUY" | "SELL" | "WATCH"
    entry: str,
    sl: str,    sl_diff: str,
    tp1: str,   tp1_diff: str,
    tp2: str,   tp2_diff: str,
    analysis: str,
    tags: list[str],
    exchange: str = "NSE/BSE",
) -> Image.Image:
    """Render Template 3 — India/NSE Signal card. Returns PIL Image."""
    f10  = _font(13)
    f11  = _font(14)
    f11b = _font(14, bold=True)
    f12  = _font(15)
    f13  = _font(16)
    f15b = _font(19, bold=True)
    f20b = _font(22, bold=True)

    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    analysis_lines = min(3, len(_wrap_text(dummy, analysis, f11, W - IN * 2)))

    h = (PAD + 44 + 14 + 12
         + 26 + 22
         + 10 + 1 + 10
         + 6 * 26
         + 10 + 1 + 10
         + 18 + analysis_lines * 18 + 8
         + 26 + PAD)

    img, draw, cx, cy, cw, _ = _canvas(BG_NSE, W, h)

    badge_text = ("BUY"  if direction in ("BUY",  "Bullish")
                  else "SELL" if direction in ("SELL", "Bearish")
                  else "WATCH")
    badge_bg   = ((26, 107, 60) if badge_text == "BUY"
                  else (107, 26, 26) if badge_text == "SELL"
                  else (60, 60, 26))
    badge_fg   = (C_GREEN if badge_text == "BUY"
                  else C_RED  if badge_text == "SELL"
                  else C_AMBER)

    cy = _header(draw, cx, cy, cw, "🇮🇳", (26, 61, 26), f"NSE · {exchange}",
                 badge_text, badge_bg, badge_fg, f10, f13, f20b)

    draw.text((cx, cy), f"{index}  ·  {asset}", font=f15b, fill=C_WHITE)
    cy += 26
    draw.text((cx, cy), f"{exchange}  ·  India Market Signal",
              font=f10, fill=(255, 255, 255, 115))
    cy += 22

    cy = _divider(draw, cx, cw, cy)

    dir_col = (C_GREEN if badge_text == "BUY"
               else C_RED if badge_text == "SELL"
               else C_AMBER)
    rows = [
        ("Asset / Index",  asset,                    C_BLUE),
        ("Signal",         badge_text,               dir_col),
        ("Entry zone",     entry,                    C_BLUE),
        ("Stop loss",      f"{sl}  (-{sl_diff})",    C_RED),
        ("Target 1",       f"{tp1}  (+{tp1_diff})",  C_GREEN),
        ("Target 2",       f"{tp2}  (+{tp2_diff})",  C_GREEN),
    ]
    for label, value, vc in rows:
        cy = _row(draw, cx, cw, cy, label, value, vc, f11, f12)

    cy = _divider(draw, cx, cw, cy)

    draw.text((cx, cy), "Analysis:", font=f11b, fill=C_WHITE)
    cy += 18
    for line in _wrap_text(draw, analysis, f11, cw - cx)[:3]:
        draw.text((cx, cy), line, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    _tag_row(draw, cx, cy, tags, f10)

    return img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Template 4 — Morning Market Briefing  (charcoal #1e1e2e)
# ─────────────────────────────────────────────────────────────────────────────
def make_morning_briefing_card(
    date_str: str,
    signals: list[dict],
    # Each dict: {"pair": "XAU/USD BUY", "result": "TP1 HIT +16 pts", "up": True}
    events: list[dict],
    # Each dict: {"time": "2:30 PM", "name": "US Core PCE", "impact": "HIGH"}
    overview: str,
) -> Image.Image:
    """Render Template 4 — Morning Briefing card. Returns PIL Image."""
    f10  = _font(13)
    f11  = _font(14)
    f11b = _font(14, bold=True)
    f12  = _font(15)
    f13  = _font(16)
    f15b = _font(19, bold=True)
    f20b = _font(22, bold=True)

    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    overview_lines = len(_wrap_text(dummy, overview, f11, W - IN * 2))

    h = (PAD + 44 + 14 + 12
         + 26 + 22
         + 10 + 1 + 10
         + 20 + max(1, len(signals)) * 26
         + 10 + 1 + 10
         + 20 + max(1, len(events)) * 26
         + 10 + 1 + 10
         + 20 + max(2, overview_lines) * 18 + 8
         + 26 + PAD)

    img, draw, cx, cy, cw, _ = _canvas(BG_BRIEFING, W, h)

    cy = _header(draw, cx, cy, cw, "🌅", (45, 26, 79), "Daily briefing",
                 "MORNING", (61, 26, 92), C_PURPLE, f10, f13, f20b)

    draw.text((cx, cy), f"Market Briefing — {date_str}", font=f15b, fill=C_WHITE)
    cy += 26
    draw.text((cx, cy), "Forex  ·  Crypto  ·  NSE  ·  Key events today",
              font=f10, fill=(255, 255, 255, 115))
    cy += 22

    cy = _divider(draw, cx, cw, cy)

    # Yesterday's signals
    draw.text((cx, cy), "Yesterday's Signals", font=f11b, fill=(255, 255, 255, 128))
    cy += 20
    if signals:
        for s in signals:
            vc = C_GREEN if s.get("up") else C_RED
            cy = _row(draw, cx, cw, cy, s["pair"], s["result"], vc, f11, f12)
    else:
        draw.text((cx, cy), "No signals sent yesterday.",
                  font=f11, fill=(255, 255, 255, 80))
        cy += 26

    cy = _divider(draw, cx, cw, cy)

    # Key events
    draw.text((cx, cy), "Key Events Today (IST)", font=f11b, fill=(255, 255, 255, 128))
    cy += 20
    if events:
        for ev in events:
            label = f"{ev['time']}  {ev['name']}"
            imp   = ev.get("impact", "MED")
            imp_col = C_RED if imp == "HIGH" else C_AMBER
            cy = _row(draw, cx, cw, cy, label, imp, imp_col, f11, f12)
    else:
        draw.text((cx, cy), "No major events today.",
                  font=f11, fill=(255, 255, 255, 80))
        cy += 26

    cy = _divider(draw, cx, cw, cy)

    # Market overview
    draw.text((cx, cy), "Market Overview", font=f11b, fill=(255, 255, 255, 128))
    cy += 20
    for line in _wrap_text(draw, overview, f11, cw - cx):
        draw.text((cx, cy), line, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    _tag_row(draw, cx, cy, ["morning", "briefing", "forex", "NSE", "crypto"], f10)

    return img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────
def img_to_bytes(img: Image.Image) -> io.BytesIO:
    """Convert a PIL Image to a BytesIO PNG buffer (ready for bot.send_photo)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
