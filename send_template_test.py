"""
Test script — generates a Telegram-style signal card image and sends it as a photo.
Matches the HTML template design exactly.
"""
import io
import json
import urllib.request
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = "8710452375:AAG-pqR8amkjx772hAYiLC_0WymUcoruVqE"
CHAT_ID = "6207722743"

# ── Colours (from the HTML template) ────────────────────────────────────────
C_BG        = (30,  58,  95)   # #1e3a5f  navy bubble
C_HEADER_SEP= (255,255,255, 30)# divider line
C_WHITE     = (255, 255, 255)
C_DIM       = (255, 255, 255, 115)  # labels
C_GREEN     = (74,  222, 128)  # #4ade80  up / BUY
C_RED       = (248, 113, 113)  # #f87171  down / SELL / SL
C_BLUE      = (96,  165, 250)  # #60a5fa  entry / neutral
C_AMBER     = (251, 191,  36)  # #fbbf24  RR / badge alert
C_BADGE_BG  = (26,  107,  60)  # #1a6b3c  BUY badge bg
C_ICON_BG   = (15,  52,   96)  # #0f3460  icon bg
C_TAG_BG    = (255, 255, 255, 18)   # hashtag pill bg
C_CONF_BG   = (255, 255, 255, 25)   # confidence bar bg
C_ANALYSIS  = (255, 255, 255, 153)  # 60% white

W = 420      # bubble width
PAD = 20     # horizontal padding


def load_font(size: int, bold: bool = False):
    """Try to load a nice font, fall back to default."""
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\verdana.ttf",
    ]
    bold_candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
    ]
    paths = bold_candidates if bold else candidates
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
    draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
    draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
    draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)


def draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
               bg, fg, font) -> int:
    """Draw a pill badge, return its width."""
    tw, th = draw.textlength(text, font=font), font.size
    pad_x, pad_y = 10, 4
    bw = int(tw) + pad_x * 2
    bh = th + pad_y * 2
    draw_rounded_rect(draw, (x, y, x + bw, y + bh), 4, bg)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=fg)
    return bw


def make_signal_card(
    pair: str, instrument_name: str, direction: str,
    entry: str, sl: str, sl_diff: str,
    tp1: str, tp1_diff: str,
    tp2: str, tp2_diff: str,
    rr: str, confidence: int, reason: str,
    tags: list[str],
    timeframe: str = "H1",
) -> Image.Image:
    """
    Render Template 1 — Forex/Crypto Trade Signal card.
    Returns a PIL Image.
    """
    # Fonts
    f10  = load_font(13)
    f11  = load_font(14)
    f12  = load_font(15)
    f13  = load_font(16)
    f15b = load_font(19, bold=True)
    f16b = load_font(20, bold=True)

    # ── Estimate height ──────────────────────────────────────────────────────
    height = (
        PAD          # top
        + 44         # header (icon + name)
        + 12         # separator
        + 28         # pair title
        + 18         # subtitle
        + 10         # gap
        + 1          # divider
        + 10         # gap
        + 5 * 26     # 5 data rows
        + 10         # gap
        + 1          # divider
        + 10         # gap
        + 14         # "AI confidence" label
        + 10         # confidence bar
        + 14         # conf label row
        + 10         # gap
        + 1          # divider
        + 10         # gap
        + 50         # reason text (2 lines)
        + 14         # gap
        + 28         # hashtag row
        + 10         # gap
        + 18         # disclaimer
        + PAD        # bottom
    )

    img = Image.new("RGBA", (W + PAD * 2, height), (18, 20, 30, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # Outer bubble (Telegram-style rounded rect — flat bottom-left)
    bx1, by1 = PAD, PAD
    bx2, by2 = W + PAD, height - PAD
    # Full rounded
    draw_rounded_rect(draw, (bx1, by1, bx2, by2), 16, C_BG)
    # Flatten bottom-left corner (Telegram style)
    draw.rectangle([bx1, by2 - 16, bx1 + 16, by2], fill=C_BG)

    cx = bx1 + PAD  # content left edge
    cy = by1 + PAD  # content top cursor
    cw = bx2 - PAD  # content right edge

    # ── Header: icon + bot name + badge ─────────────────────────────────────
    icon_size = 36
    draw_rounded_rect(draw, (cx, cy, cx + icon_size, cy + icon_size), 8, C_ICON_BG)
    draw.text((cx + 8, cy + 6), "📡", font=f16b, fill=C_WHITE)

    name_x = cx + icon_size + 10
    draw.text((name_x, cy + 2), "TradeSignal Pro", font=f13, fill=C_WHITE)
    draw.text((name_x, cy + 20), "AI-powered signals", font=f10, fill=(255, 255, 255, 128))

    badge_text = "BUY" if direction == "BUY" else "SELL"
    badge_bg   = C_BADGE_BG if direction == "BUY" else (107, 26, 26)
    badge_fg   = C_GREEN    if direction == "BUY" else C_RED
    bw = draw_badge(draw, cw - 60, cy + 8, badge_text, badge_bg, badge_fg, f10)

    cy += icon_size + 14

    # Separator line
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 30), width=1)
    cy += 12

    # ── Pair title + subtitle ────────────────────────────────────────────────
    dir_color = C_GREEN if direction == "BUY" else C_RED
    dir_icon  = "🟢 LONG" if direction == "BUY" else "🔴 SHORT"
    title_text = f"{pair}  ·  {dir_icon}  ·  {timeframe}"
    draw.text((cx, cy), title_text, font=f15b, fill=C_WHITE)
    cy += 26
    draw.text((cx, cy), instrument_name, font=f10, fill=(255, 255, 255, 115))
    cy += 20

    # ── Divider ──────────────────────────────────────────────────────────────
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 12

    # ── Data rows ────────────────────────────────────────────────────────────
    rows = [
        ("Entry price",   entry,              C_BLUE),
        ("Stop loss",     f"{sl}  (-{sl_diff})", C_RED),
        ("Take profit 1", f"{tp1}  (+{tp1_diff})", C_GREEN),
        ("Take profit 2", f"{tp2}  (+{tp2_diff})", C_GREEN),
        ("Risk : Reward", f"1 : {rr}",         C_AMBER),
    ]
    for label, value, val_color in rows:
        draw.text((cx, cy), label, font=f11, fill=(255, 255, 255, 115))
        draw.text((cw - int(draw.textlength(value, font=f12)), cy), value,
                  font=f12, fill=val_color)
        cy += 26

    # ── Divider ──────────────────────────────────────────────────────────────
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 12

    # ── Confidence bar ───────────────────────────────────────────────────────
    draw.text((cx, cy), "AI confidence", font=f10, fill=(255, 255, 255, 115))
    cy += 16
    bar_h = 6
    bar_w = cw - cx
    # Background
    draw_rounded_rect(draw, (cx, cy, cx + bar_w, cy + bar_h), 3, (255, 255, 255, 25))
    # Fill
    fill_w = int(bar_w * confidence / 100)
    draw_rounded_rect(draw, (cx, cy, cx + fill_w, cy + bar_h), 3, C_GREEN)
    cy += bar_h + 5
    # Labels
    draw.text((cx, cy), "0", font=f10, fill=(255, 255, 255, 100))
    conf_str = f"{confidence}%"
    conf_x = cx + fill_w - int(draw.textlength(conf_str, font=f10)) // 2
    draw.text((conf_x, cy), conf_str, font=f10, fill=C_GREEN)
    draw.text((cw - int(draw.textlength("100", font=f10)), cy), "100", font=f10, fill=(255, 255, 255, 100))
    cy += 16

    # ── Divider ──────────────────────────────────────────────────────────────
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 12

    # ── Reason text ──────────────────────────────────────────────────────────
    # Word-wrap the reason
    words = reason.split()
    lines_out = []
    line_buf = ""
    max_w = cw - cx
    for word in words:
        test = f"{line_buf} {word}".strip()
        if draw.textlength(test, font=f11) <= max_w:
            line_buf = test
        else:
            if line_buf:
                lines_out.append(line_buf)
            line_buf = word
    if line_buf:
        lines_out.append(line_buf)

    for line in lines_out[:3]:  # max 3 lines
        draw.text((cx, cy), line, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 6

    # ── Hashtag pills ────────────────────────────────────────────────────────
    tx = cx
    for tag in tags:
        tag_text = f"#{tag}"
        tw = int(draw.textlength(tag_text, font=f10)) + 12
        draw_rounded_rect(draw, (tx, cy, tx + tw, cy + 20), 4, (255, 255, 255, 18))
        draw.text((tx + 6, cy + 3), tag_text, font=f10, fill=(255, 255, 255, 100))
        tx += tw + 6
    cy += 26

    # ── Disclaimer ───────────────────────────────────────────────────────────
    disclaimer = "⚠️ Not financial advice. Trade at your own risk."
    draw.text((cx, cy), disclaimer, font=f10, fill=(255, 255, 255, 90))

    return img.convert("RGB")


def make_news_alert_card(
    title: str, asset: str, category: str, date_str: str,
    direction: str, confidence_pct: int, analysis: str,
    tags: list[str],
) -> Image.Image:
    """Template 2 — High-Impact News Alert card."""
    f10  = load_font(13)
    f11  = load_font(14)
    f12  = load_font(15)
    f13  = load_font(16)
    f15b = load_font(19, bold=True)

    height = (
        PAD + 44 + 12 + 28 + 18 + 10 + 1 + 10
        + 3 * 26   # impact rows
        + 10 + 1 + 10
        + 60       # analysis
        + 10 + 28 + PAD
    )

    img = Image.new("RGBA", (W + PAD * 2, height), (18, 20, 30, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    BG = (26, 39, 68)  # #1a2744
    bx1, by1 = PAD, PAD
    bx2, by2 = W + PAD, height - PAD
    draw_rounded_rect(draw, (bx1, by1, bx2, by2), 16, BG)
    draw.rectangle([bx1, by2 - 16, bx1 + 16, by2], fill=BG)

    cx = bx1 + PAD
    cy = by1 + PAD
    cw = bx2 - PAD

    # Header
    icon_size = 36
    draw_rounded_rect(draw, (cx, cy, cx + icon_size, cy + icon_size), 8, (26, 58, 107))
    draw.text((cx + 8, cy + 6), "📰", font=load_font(19, bold=True), fill=C_WHITE)

    name_x = cx + icon_size + 10
    draw.text((name_x, cy + 2),  "TradeSignal Pro", font=f13, fill=C_WHITE)
    draw.text((name_x, cy + 20), "Market news",     font=f10, fill=(255, 255, 255, 128))

    # HIGH IMPACT badge (blue)
    bw = draw_badge(draw, cw - 110, cy + 8, "HIGH IMPACT",
                    (26, 61, 107), C_BLUE, f10)

    cy += icon_size + 14
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 30), width=1)
    cy += 12

    # Title & subtitle
    draw.text((cx, cy), title[:40], font=f15b, fill=C_BLUE)
    cy += 26
    subtitle = f"{asset}  ·  {category}  ·  {date_str}"
    draw.text((cx, cy), subtitle, font=f10, fill=(255, 255, 255, 115))
    cy += 20

    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 12

    # Impact rows
    dir_icon = "🟢 Bullish" if direction == "Bullish" else ("🔴 Bearish" if direction == "Bearish" else "🟡 Neutral")
    dir_col  = C_GREEN if direction == "Bullish" else (C_RED if direction == "Bearish" else C_AMBER)
    rows = [
        ("Asset",      asset,     C_WHITE),
        ("Impact",     dir_icon,  dir_col),
        ("Confidence", f"{confidence_pct}%", C_AMBER),
    ]
    for label, value, val_color in rows:
        draw.text((cx, cy), label, font=f11, fill=(255, 255, 255, 115))
        draw.text((cw - int(draw.textlength(value, font=f12)), cy), value,
                  font=f12, fill=val_color)
        cy += 26

    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 12

    # Analysis
    draw.text((cx, cy), "⚡ Quick Analysis:", font=f11, fill=C_WHITE)
    cy += 18
    words = analysis.split()
    line_buf = ""
    max_w = cw - cx
    for word in words:
        test = f"{line_buf} {word}".strip()
        if draw.textlength(test, font=f11) <= max_w:
            line_buf = test
        else:
            draw.text((cx, cy), line_buf, font=f11, fill=(255, 255, 255, 153))
            cy += 18
            line_buf = word
    if line_buf:
        draw.text((cx, cy), line_buf, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    # Tags
    tx = cx
    for tag in tags:
        tag_text = f"#{tag}"
        tw = int(draw.textlength(tag_text, font=f10)) + 12
        draw_rounded_rect(draw, (tx, cy, tx + tw, cy + 20), 4, (255, 255, 255, 18))
        draw.text((tx + 6, cy + 3), tag_text, font=f10, fill=(255, 255, 255, 100))
        tx += tw + 6

    return img.convert("RGB")


def make_morning_briefing_card(
    date_str: str,
    signals: list[dict],   # [{"pair":"XAU/USD BUY","result":"TP1 HIT +16 pts","up":True}]
    events: list[dict],    # [{"time":"2:30 PM","name":"US Core PCE","impact":"HIGH"}]
    overview: str,
) -> Image.Image:
    """Template 4 — Morning Briefing card."""
    f10  = load_font(13)
    f11  = load_font(14)
    f12  = load_font(15)
    f13  = load_font(16)
    f11b = load_font(14, bold=True)
    f15b = load_font(19, bold=True)

    height = (
        PAD + 44 + 12 + 28 + 18 + 10 + 1 + 10
        + 16 + len(signals) * 26
        + 10 + 1 + 10
        + 16 + len(events) * 26
        + 10 + 1 + 10
        + 80   # overview
        + 10 + 28 + PAD
    )

    BG = (30, 30, 46)  # #1e1e2e
    img = Image.new("RGBA", (W + PAD * 2, height), (18, 20, 30, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    bx1, by1 = PAD, PAD
    bx2, by2 = W + PAD, height - PAD
    draw_rounded_rect(draw, (bx1, by1, bx2, by2), 16, BG)
    draw.rectangle([bx1, by2 - 16, bx1 + 16, by2], fill=BG)

    cx = bx1 + PAD
    cy = by1 + PAD
    cw = bx2 - PAD

    # Header
    icon_size = 36
    draw_rounded_rect(draw, (cx, cy, cx + icon_size, cy + icon_size), 8, (45, 26, 79))
    draw.text((cx + 6, cy + 5), "🌅", font=load_font(20, bold=True), fill=C_WHITE)

    name_x = cx + icon_size + 10
    draw.text((name_x, cy + 2),  "TradeSignal Pro", font=f13, fill=C_WHITE)
    draw.text((name_x, cy + 20), "Daily briefing",  font=f10, fill=(255, 255, 255, 128))

    bw = draw_badge(draw, cw - 90, cy + 8, "MORNING",
                    (61, 26, 92), (192, 132, 252), f10)

    cy += icon_size + 14
    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 30), width=1)
    cy += 12

    draw.text((cx, cy), f"Market Briefing — {date_str}", font=f15b, fill=C_WHITE)
    cy += 26
    draw.text((cx, cy), "Forex  ·  Crypto  ·  NSE  ·  Key events today",
              font=f10, fill=(255, 255, 255, 115))
    cy += 20

    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 10

    # Yesterday's signals
    draw.text((cx, cy), "📋 Yesterday's Signals", font=f11b, fill=(255, 255, 255, 128))
    cy += 18
    for s in signals:
        draw.text((cx, cy), s["pair"], font=f11, fill=(255, 255, 255, 115))
        val_col = C_GREEN if s.get("up") else C_RED
        draw.text((cw - int(draw.textlength(s["result"], font=f12)), cy),
                  s["result"], font=f12, fill=val_col)
        cy += 26

    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 10

    # Key events
    draw.text((cx, cy), "📅 Key Events Today (IST)", font=f11b, fill=(255, 255, 255, 128))
    cy += 18
    for ev in events:
        label = f"{ev['time']}  {ev['name']}"
        draw.text((cx, cy), label, font=f11, fill=(255, 255, 255, 115))
        impact_col = C_RED if ev["impact"] == "HIGH" else C_AMBER
        draw.text((cw - int(draw.textlength(ev["impact"], font=f12)), cy),
                  ev["impact"], font=f12, fill=impact_col)
        cy += 26

    draw.line([(cx, cy), (cw, cy)], fill=(255, 255, 255, 25), width=1)
    cy += 10

    # Market overview
    draw.text((cx, cy), "🔭 Market Overview", font=f11b, fill=(255, 255, 255, 128))
    cy += 18
    words = overview.split()
    line_buf = ""
    max_w = cw - cx
    for word in words:
        test = f"{line_buf} {word}".strip()
        if draw.textlength(test, font=f11) <= max_w:
            line_buf = test
        else:
            draw.text((cx, cy), line_buf, font=f11, fill=(255, 255, 255, 153))
            cy += 18
            line_buf = word
    if line_buf:
        draw.text((cx, cy), line_buf, font=f11, fill=(255, 255, 255, 153))
        cy += 18
    cy += 8

    # Tags
    tags = ["morning", "briefing", "forex", "NSE", "crypto"]
    tx = cx
    for tag in tags:
        tag_text = f"#{tag}"
        tw = int(draw.textlength(tag_text, font=f10)) + 12
        draw_rounded_rect(draw, (tx, cy, tx + tw, cy + 20), 4, (255, 255, 255, 18))
        draw.text((tx + 6, cy + 3), tag_text, font=f10, fill=(255, 255, 255, 100))
        tx += tw + 6

    return img.convert("RGB")


def send_photo(img: Image.Image, caption: str = "") -> dict:
    """Send a PIL image as a Telegram photo."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    img_bytes = buf.read()

    boundary = "----TGBoundary7821"
    body  = f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{CHAT_ID}\r\n'
    body += f"--{boundary}\r\n"
    if caption:
        body += f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        body += f"--{boundary}\r\n"
    body_bytes = body.encode()
    file_part  = (
        f'Content-Disposition: form-data; name="photo"; filename="signal.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    data = body_bytes + file_part + img_bytes + tail
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


if __name__ == "__main__":
    print("Generating Template 1 — Trade Signal...")
    signal_img = make_signal_card(
        pair="XAU/USD",
        instrument_name="Gold vs US Dollar",
        direction="BUY",
        entry="$2,318.50",
        sl="$2,305.00",   sl_diff="$13.50",
        tp1="$2,335.00",  tp1_diff="$16.50",
        tp2="$2,352.00",  tp2_diff="$33.50",
        rr="2.5",
        confidence=78,
        reason="Price broke H1 resistance at 2,315. DXY weakening. NFP release in 2 hrs — keep size small.",
        tags=["XAU", "forex", "gold", "H1"],
    )
    res1 = send_photo(signal_img, "📡 TradeSignal Pro — XAU/USD BUY Signal")
    print("Template 1 sent:", res1.get("ok"), "| MsgID:", res1.get("result", {}).get("message_id"))

    print("Generating Template 2 — News Alert...")
    news_img = make_news_alert_card(
        title="US Non-Farm Payrolls Released",
        asset="USD",
        category="Jobs Report",
        date_str="June 2025",
        direction="Bullish",
        confidence_pct=82,
        analysis="Blowout jobs number crushes estimates. Dollar likely to surge. Avoid USD/JPY shorts. Gold may dip short-term.",
        tags=["NFP", "USD", "highimpact", "news"],
    )
    res2 = send_photo(news_img, "📰 BREAKING — US NFP Data")
    print("Template 2 sent:", res2.get("ok"), "| MsgID:", res2.get("result", {}).get("message_id"))

    print("Generating Template 4 — Morning Briefing...")
    briefing_img = make_morning_briefing_card(
        date_str="25 June 2025",
        signals=[
            {"pair": "XAU/USD BUY",    "result": "TP1 HIT +16 pts", "up": True},
            {"pair": "EUR/USD SELL",   "result": "SL HIT -10 pts",  "up": False},
            {"pair": "BANKNIFTY CE",   "result": "TP2 +93%",        "up": True},
        ],
        events=[
            {"time": "2:30 PM", "name": "US Core PCE",      "impact": "HIGH"},
            {"time": "3:00 PM", "name": "Fed Powell Speech", "impact": "HIGH"},
            {"time": "All day", "name": "NSE Weekly Expiry", "impact": "MED"},
        ],
        overview="Dollar consolidating near key levels. Gold testing resistance at 2,320. BankNifty range 47,800–48,600. Trade light before PCE data release.",
    )
    res3 = send_photo(briefing_img, "🌅 Morning Market Briefing — 25 June 2025")
    print("Template 4 sent:", res3.get("ok"), "| MsgID:", res3.get("result", {}).get("message_id"))

    print("\n✅ All 3 template test messages sent!")
