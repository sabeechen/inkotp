#include "ui.h"

#include <M5Unified.h>

namespace ui {
namespace {

constexpr int kWidth = 200;
constexpr int kHeight = 200;
constexpr int kTitleHeight = 26;
constexpr int kBarX = 20, kBarY = 112, kBarW = 160, kBarH = 12;
// Compact view: row height, and where the label, code and bar sit within a row.
constexpr int kRowHeight = 66, kRowLabelY = 10, kRowCodeY = 35, kRowBarY = 54, kRowBarH = 6;

// 24-bit colours. The panel is 1-bit and dithers anything that is not pure
// black or white, so nothing else is ever drawn.
constexpr uint32_t kInk = 0x000000u;
constexpr uint32_t kPaper = 0xFFFFFFu;

bool clean = true;

auto& d = M5.Display;

// Starts a frame. Clean frames use the slow, ghost-free waveform.
void frame() {
    d.setEpdMode(clean ? epd_mode_t::epd_quality : epd_mode_t::epd_fast);
    clean = false;
    d.startWrite();
    d.fillScreen(kPaper);
}

void endFrame() {
    d.endWrite();
    d.display();
}

void text(const char* s, int x, int y, const lgfx::IFont* font, textdatum_t datum,
          uint32_t color = kInk) {
    d.setFont(font);
    d.setTextDatum(datum);
    d.setTextColor(color);
    d.drawString(s, x, y);
}

// The largest of `fonts` in which `s` is no wider than `width`; the last one
// if none fits.
template <size_t N>
const lgfx::IFont* widestFit(const char* s, int width, const lgfx::IFont* const (&fonts)[N]) {
    for (const lgfx::IFont* font : fonts) {
        d.setFont(font);
        if (d.textWidth(s) <= width) return font;
    }
    return fonts[N - 1];
}

const lgfx::IFont* const kBodyFonts[] = {&fonts::FreeSansBold9pt7b, &fonts::FreeSans9pt7b,
                                         &fonts::DejaVu12, &fonts::Font2};
const lgfx::IFont* const kSmallFonts[] = {&fonts::FreeSans9pt7b, &fonts::DejaVu12, &fonts::Font2};

// Centred body text that drops to a narrower font when it would not fit.
void fitted(const char* s, int y, uint32_t color = kInk) {
    text(s, kWidth / 2, y, widestFit(s, kWidth - 8, kBodyFonts), textdatum_t::middle_center, color);
}

// Secondary text: hints, footers and status. Thin 1-pixel fonts are hard to
// read on this panel, so they are only a last resort for long strings.
void small(const char* s, int x, int y, textdatum_t datum = textdatum_t::middle_center,
           int width = kWidth - 8) {
    text(s, x, y, widestFit(s, width, kSmallFonts), datum);
}

void title(const char* s) {
    d.fillRect(0, 0, kWidth, kTitleHeight, kInk);
    fitted(s, kTitleHeight / 2, kPaper);
}

void bar(int y, int height, uint32_t secondsLeft, uint32_t period) {
    d.fillRect(kBarX, y, kBarW, height, kPaper);
    d.drawRect(kBarX, y, kBarW, height, kInk);
    int fill = (int)((uint64_t)(kBarW - 4) * secondsLeft / period);
    d.fillRect(kBarX + 2, y + 2, fill, height - 4, kInk);
}

// Starts an update of part of the screen. It stays in the same refresh mode as
// ordinary frames: switching modes makes some panels redraw everything.
void partial() {
    d.setEpdMode(epd_mode_t::epd_fast);
    d.startWrite();
}

}  // namespace

void begin() {
    d.setRotation(0);
    d.setTextWrap(false);
}

void cleanNext() { clean = true; }

void code(const otp::Account& account, int index, int total, time_t now, int batteryPercent,
          const char* warning) {
    char current[10], next[10], buf[24];
    otp::formatCode(otp::totp(account, (uint64_t)now), account.digits, current);
    otp::formatCode(otp::totp(account, (uint64_t)now + account.period), account.digits, next);

    frame();
    fitted(account.label, 16);
    d.drawFastHLine(0, 32, kWidth, kInk);

    text(current, kWidth / 2, 74,
         account.digits == 6 ? &fonts::FreeSansBold24pt7b : &fonts::FreeSansBold18pt7b,
         textdatum_t::middle_center);
    bar(kBarY, kBarH, otp::secondsLeft(account, (uint64_t)now), account.period);

    snprintf(buf, sizeof(buf), "next  %s", next);
    text(buf, kWidth / 2, 148, &fonts::FreeSans9pt7b, textdatum_t::middle_center);

    d.drawFastHLine(0, 176, kWidth, kInk);
    snprintf(buf, sizeof(buf), "%d/%d", index + 1, total);
    small(buf, 4, 189, textdatum_t::middle_left, 50);
    snprintf(buf, sizeof(buf), "%d%%", batteryPercent);
    small(buf, kWidth - 4, 189, textdatum_t::middle_right, 50);
    if (warning) small(warning, kWidth / 2, 189, textdatum_t::middle_center, 96);
    endFrame();
}

void codeBar(uint32_t secondsLeft, uint32_t period) {
    partial();
    bar(kBarY, kBarH, secondsLeft, period);
    endFrame();
}

void compact(const CompactRow* rows, int count, const char* warning) {
    frame();
    for (int i = 0; i < count; i++) {
        const int y = i * kRowHeight;
        // A warning shares the first row's label line.
        int labelWidth = kWidth - 8;
        if (i == 0 && warning) {
            small(warning, kWidth - 4, y + kRowLabelY, textdatum_t::middle_right, 84);
            labelWidth -= 92;
        }
        text(rows[i].label, 4, y + kRowLabelY, widestFit(rows[i].label, labelWidth, kBodyFonts),
             textdatum_t::middle_left);
        text(rows[i].code, kWidth / 2, y + kRowCodeY, &fonts::FreeSansBold18pt7b,
             textdatum_t::middle_center);
        bar(y + kRowBarY, kRowBarH, rows[i].secondsLeft, rows[i].period);
        if (i > 0) d.drawFastHLine(0, y - 1, kWidth, kInk);
    }
    endFrame();
}

void compactBars(const CompactRow* rows, int count) {
    partial();
    for (int i = 0; i < count; i++) {
        bar(i * kRowHeight + kRowBarY, kRowBarH, rows[i].secondsLeft, rows[i].period);
    }
    endFrame();
}

void menu(const char* heading, const char* const* items, int count, int selected) {
    constexpr int kRow = 28;
    frame();
    title(heading);
    for (int i = 0; i < count; i++) {
        int y = kTitleHeight + 4 + i * kRow;
        bool on = i == selected;
        if (on) d.fillRect(0, y, kWidth, kRow - 2, kInk);
        text(items[i], 10, y + kRow / 2 - 1, &fonts::FreeSans9pt7b, textdatum_t::middle_left,
             on ? kPaper : kInk);
    }
    endFrame();
}

void message(const char* heading, const char* line1, const char* line2, const char* line3,
             const char* line4, const char* footer) {
    const char* lines[] = {line1, line2, line3, line4};
    frame();
    title(heading);
    int y = 50;
    for (const char* line : lines) {
        if (!line) continue;
        fitted(line, y);
        y += 26;
    }
    if (footer) small(footer, kWidth / 2, 188);
    endFrame();
}

void pinEntry(const char* heading, int entered, int length, const char* note) {
    frame();
    title(heading);
    const int step = length > 10 ? 12 : 18;
    const int radius = length > 10 ? 4 : 6;
    int x = kWidth / 2 - step * (length - 1) / 2;
    for (int i = 0; i < length; i++, x += step) {
        if (i < entered) {
            d.fillCircle(x, 90, radius, kInk);
        } else {
            d.drawCircle(x, 90, radius, kInk);
        }
    }
    if (note) fitted(note, 136);
    small("Side button: sleep", kWidth / 2, 188);
    endFrame();
}

void qr(const char* heading, const char* payload, const char* line1, const char* line2) {
    constexpr int kSize = 130;
    frame();
    title(heading);
    d.qrcode(payload, (kWidth - kSize) / 2, kTitleHeight + 4, kSize);
    if (line1) small(line1, kWidth / 2, 171);
    if (line2) small(line2, kWidth / 2, 189);
    endFrame();
}

void typed(const char* heading, const char* line, const char* caption, const char* value,
           const char* footer) {
    // Up to 8 characters a row, each row split in the middle so it is easy to
    // keep your place.
    constexpr int kMaxRow = 8, kRowHeight = 36;
    const int len = (int)strlen(value);
    const int rows = (len + kMaxRow - 1) / kMaxRow;
    const int perRow = (len + rows - 1) / rows;
    frame();
    title(heading);
    if (line) fitted(line, 44);
    if (caption) small(caption, kWidth / 2, 68);
    int y = 124 - kRowHeight * (rows - 1) / 2;
    for (int start = 0; start < len; start += perRow, y += kRowHeight) {
        char row[kMaxRow + 2];
        int n = 0;
        for (int i = start; i < start + perRow && i < len; i++) {
            if (i == start + (perRow + 1) / 2) row[n++] = ' ';
            row[n++] = value[i];
        }
        row[n] = '\0';
        text(row, kWidth / 2, y, &fonts::FreeMonoBold18pt7b, textdatum_t::middle_center);
    }
    if (footer) small(footer, kWidth / 2, 188);
    endFrame();
}

void sleepScreen(const char* owner) {
    clean = true;
    frame();
    // A padlock: shackle, body, keyhole.
    const int cx = kWidth / 2;
    d.fillArc(cx, 46, 20, 14, 180, 360, kInk);
    d.fillRect(cx - 20, 46, 6, 14, kInk);
    d.fillRect(cx + 14, 46, 6, 14, kInk);
    d.fillRoundRect(cx - 30, 58, 60, 46, 6, kInk);
    d.fillCircle(cx, 76, 6, kPaper);
    d.fillRect(cx - 2, 78, 4, 14, kPaper);

    text("InkOTP", cx, 122, &fonts::FreeSansBold9pt7b, textdatum_t::middle_center);
    small("Press the dial to wake", cx, 144);

    if (owner && owner[0]) {
        // Owner text is often longer than one line: break it at the space
        // nearest the middle when it would otherwise need a smaller font.
        const char* split = nullptr;
        if (widestFit(owner, kWidth - 8, kSmallFonts) != kSmallFonts[0]) {
            const char* middle = owner + strlen(owner) / 2;
            for (const char* p = owner; *p; p++) {
                if (*p == ' ' && (!split || abs(p - middle) < abs(split - middle))) split = p;
            }
        }
        if (split) {
            char first[49];
            const size_t n = (size_t)(split - owner) < sizeof(first) - 1 ? (size_t)(split - owner)
                                                                         : sizeof(first) - 1;
            memcpy(first, owner, n);
            first[n] = '\0';
            small(first, cx, 171);
            small(split + 1, cx, 189);
        } else {
            small(owner, cx, 180);
        }
    }
    endFrame();
}

}  // namespace ui
