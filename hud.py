import time
import socket
import psutil
import os
from PIL import Image, ImageDraw, ImageFont
from st7735s import ST7735S

# --------------------------------------------------
# CONFIGURATION & STYLE
# --------------------------------------------------

ROTATION = 270
WIDTH = 160
HEIGHT = 80
UPDATE_INTERVAL = 1.0

SCALE = 2  # high DPI supersampling

FONT_PATH = os.path.expanduser("~/.fonts/0xProtoNerdFontMono-Regular.ttf")

THEME = {
    "bg": "#000000",
    "bar_bg": "#2A2A2D",
    "text_main": "#FFFFFF",
    "text_dim": "#8E8E93",
    "accent_blue": "#0A84FF",
    "accent_green": "#30D158",
    "accent_yellow": "#FFD60A",
    "accent_red": "#FF453A",
    "accent_purple": "#BF5AF2",
}

# --------------------------------------------------
# SYSTEM MONITOR CLASS
# --------------------------------------------------

class SystemMonitor:
    def __init__(self):
        self.display = ST7735S(rotation=ROTATION, x_offset=24, y_offset=0, debug=False)
        self.width = self.display.width
        self.height = self.display.height

        # Expanded slightly to prevent footer clipping
        self.v_width = self.width * SCALE
        self.v_height = (self.height + 6) * SCALE

        # Load scaled fonts
        self.fonts = {
            "header": self._load_font(14 * SCALE),
            "value":  self._load_font(14 * SCALE),
            "icon":   self._load_font(18 * SCALE),
            "net":    self._load_font(12 * SCALE),
            "net_icon": self._load_font(20 * SCALE), 
        }

        # SLIM PROGRESS BAR HEIGHT
        self.BAR_HEIGHT = 8 * SCALE

    def _load_font(self, size):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except:
            return ImageFont.load_default()

    def get_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except:
            return 0.0

    def get_color_by_usage(self, value):
        if value >= 80: return THEME["accent_red"]
        if value >= 60: return THEME["accent_yellow"]
        return THEME["accent_green"]

    def draw_progress_bar(self, draw, x, y, w, percent, color):
        h = self.BAR_HEIGHT

        # Background
        draw.rectangle((x, y, x + w, y + h), fill=THEME["bar_bg"])

        # Fill amount
        fill_w = max(int(w * (percent / 100)), 3 * SCALE)

        draw.rectangle((x, y, x + fill_w, y + h), fill=color)

    # --------------------------------------------------
    # RENDER FRAME
    # --------------------------------------------------

    def render_frame(self):
        img = Image.new("RGB", (self.v_width, self.v_height), THEME["bg"])
        draw = ImageDraw.Draw(img)

        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        temp = self.get_temp()

        # Network (rounded MB, no decimals)
        net = psutil.net_io_counters()
        down = int(net.bytes_recv / (1024 * 1024))
        up   = int(net.bytes_sent / (1024 * 1024))

        host = socket.gethostname()[:12]

        # --------------------------------------------------
        # HEADER
        # --------------------------------------------------
        draw.text((8, 3), u'\ue712', font=self.fonts["icon"], fill=THEME["text_dim"])
        draw.text((42, 6), host, font=self.fonts["header"], fill=THEME["text_main"])

        temp_color = self.get_color_by_usage((temp - 30) * 2)
        temp_str = f"{temp:.0f}°"
        t_w = draw.textlength(temp_str, font=self.fonts["header"])
        draw.text((self.v_width - t_w - 10, 6), temp_str,
                  font=self.fonts["header"], fill=temp_color)

        # --------------------------------------------------
        # CPU ROW
        # --------------------------------------------------
        row_1_y = 50
        draw.text((12, row_1_y-7), "󰍛", font=self.fonts["icon"], fill=THEME["text_dim"])
        self.draw_progress_bar(draw, 48, row_1_y + 6, 170, cpu, self.get_color_by_usage(cpu))
        draw.text((237, row_1_y), f"{cpu:.0f}%", font=self.fonts["value"], fill=THEME["text_main"])

        # --------------------------------------------------
        # RAM ROW
        # --------------------------------------------------
        row_2_y = 86
        draw.text((12, row_2_y-7), "", font=self.fonts["icon"], fill=THEME["text_dim"])
        self.draw_progress_bar(draw, 48, row_2_y + 6, 170, ram, self.get_color_by_usage(ram))
        draw.text((237, row_2_y), f"{ram:.0f}%", font=self.fonts["value"], fill=THEME["text_main"])

        # --------------------------------------------------
        # NETWORK FOOTER — WITH LIGHT GREY BACKGROUND
        # --------------------------------------------------

        footer_y = 130                          # Text baseline
        footer_height = 40 * SCALE              # Adjustable height
        footer_top = footer_y - (2.5 * SCALE)    # Adjust spacing above icons

        # Light grey footer background (change color here)
        draw.rectangle(
            (0, footer_top, self.v_width, footer_top + footer_height),
            fill="#510909"    # light grey
        )

        # Icons that always work in Nerd Fonts
        down_icon = u'\ueb6e' # Material Design Download icon
        up_icon   = u'\ueb71' # Material Design Upload icon

        def format_mb(value):
            if value >= 1000:
                gb = value / 1024
                return f"{gb:.1f}GB"
            else:
                return f"{value}MB"

        # Down
        draw.text((22, footer_y-5), down_icon, font=self.fonts["net_icon"], fill=THEME["accent_blue"])
        draw.text((52, footer_y), format_mb(down), font=self.fonts["value"], fill=THEME["text_main"])

        # Up
        draw.text((170, footer_y-5), up_icon, font=self.fonts["net_icon"], fill=THEME["accent_purple"])
        draw.text((200, footer_y), format_mb(up), font=self.fonts["value"], fill=THEME["text_main"])

        # --------------------------------------------------
        # FINAL RESIZE & DISPLAY
        # --------------------------------------------------
        final_img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        self.display.display(final_img)

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------

    def run(self):
        try:
            psutil.cpu_percent(None)
            while True:
                t0 = time.time()
                self.render_frame()
                time.sleep(max(0.1, UPDATE_INTERVAL - (time.time() - t0)))
        except KeyboardInterrupt:
            pass
        finally:
            self.display.close()

# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":
    SystemMonitor().run()
