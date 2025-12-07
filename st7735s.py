import time
import logging
from typing import Optional, Tuple, List, Union

import spidev
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont

# -----------------------------
# Low-level ST7735S definitions
# -----------------------------

# Display command constants
_CMD_SWRESET = 0x01
_CMD_SLPOUT = 0x11
_CMD_INVON = 0x21
_CMD_NORON = 0x20
_CMD_DISPON = 0x29
_CMD_CASET = 0x2A
_CMD_RASET = 0x2B
_CMD_RAMWR = 0x2C
_CMD_MADCTL = 0x36
_CMD_COLMOD = 0x3A
_CMD_FRMCTR1 = 0xB1
_CMD_FRMCTR2 = 0xB2
_CMD_FRMCTR3 = 0xB3
_CMD_INVCTR = 0xB4
_CMD_PWCTR1 = 0xC0
_CMD_PWCTR2 = 0xC1
_CMD_PWCTR3 = 0xC2
_CMD_PWCTR4 = 0xC3
_CMD_PWCTR5 = 0xC4
_CMD_VMCTR1 = 0xC5

# MADCTL orientation bits
_MADCTL_MH = 0x04
_MADCTL_RGB = 0x00
_MADCTL_BGR = 0x08
_MADCTL_ML = 0x10
_MADCTL_MV = 0x20
_MADCTL_MX = 0x40
_MADCTL_MY = 0x80

# Color mode
_COLMOD_16BIT = 0x05

# Default display dimensions (0.96" bar: 80x160)
_DISPLAY_WIDTH = 80
_DISPLAY_HEIGHT = 160

# SPI transfer limits (avoid OverflowError in kernel driver)
_MAX_SPI_CHUNK = 4096  # Max bytes per SPI transfer


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Hex color must be 6 hex digits (RRGGBB)")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


class ST7735S:
    """
    Driver for ST7735S-based 0.96\" 80x160 TFT display.

    Design goals:
    - Safe SPI chunking (no >4096 byte writes).
    - Minimal CPU overhead (no numpy; tiny image).
    - Simple high-level API: create_canvas(), display(), fill().
    """

    _DEFAULT_FONT: Optional[ImageFont.FreeTypeFont] = None

    def __init__(
        self,
        dc: int = 25,
        rst: int = 27,
        bl: int = 24,
        port: int = 0,
        cs: int = 0,
        speed_hz: int = 24_000_000,
        rotation: int = 0,
        invert: bool = False,
        x_offset: int = 24,
        y_offset: int = 0,
        debug: bool = False,
    ):
        # -----------------
        # Logging setup
        # -----------------
        self.logger = logging.getLogger("ST7735S")
        # Avoid adding multiple handlers if user re-imports / re-inits
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG if debug else logging.WARNING)

        # -----------------
        # Geometry / offsets
        # -----------------
        self.orig_width = _DISPLAY_WIDTH
        self.orig_height = _DISPLAY_HEIGHT

        # Hardware offsets (for common 0.96" boards)
        self._hw_x_offset = x_offset
        self._hw_y_offset = y_offset

        # Active offsets (may get swapped on rotation)
        self._x_offset = x_offset
        self._y_offset = y_offset

        # Will be set properly in set_rotation()
        self.width = self.orig_width
        self.height = self.orig_height
        self.rotation = 0

        # -----------------
        # GPIO setup
        # -----------------
        self._dc = dc
        self._rst = rst
        self._bl = bl

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._dc, GPIO.OUT)
            GPIO.setup(self._rst, GPIO.OUT)
            GPIO.setup(self._bl, GPIO.OUT)
            GPIO.output(self._bl, GPIO.LOW)
        except Exception:
            self.logger.exception("GPIO initialization failed")
            raise

        # -----------------
        # SPI setup
        # -----------------
        self.spi = spidev.SpiDev()
        try:
            self.spi.open(port, cs)
            self.spi.max_speed_hz = speed_hz
            self.spi.mode = 0
            self.spi.lsbfirst = False
        except Exception:
            self.logger.exception("SPI initialization failed")
            GPIO.cleanup([dc, rst, bl])
            raise

        # -----------------
        # Default font cache
        # -----------------
        if ST7735S._DEFAULT_FONT is None:
            try:
                # Built-in font on Raspberry Pi OS
                ST7735S._DEFAULT_FONT = ImageFont.truetype(
                    "DejaVuSansMono-Bold.ttf", 12
                )
            except Exception:
                self.logger.warning("Falling back to PIL default font")
                ST7735S._DEFAULT_FONT = ImageFont.load_default()

        # -----------------
        # Panel init
        # -----------------
        self.reset()
        self.backlight(True)
        self._init_display(invert)
        self.set_rotation(rotation)
        self.fill((0, 0, 0))
        self.logger.info(
            "Display initialized (rotation=%s, x_offset=%s, y_offset=%s)",
            rotation,
            x_offset,
            y_offset,
        )

    # -------------
    # Context mgr
    # -------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # -------------
    # HW control
    # -------------
    def reset(self) -> None:
        """Hardware reset sequence."""
        try:
            GPIO.output(self._rst, GPIO.HIGH)
            time.sleep(0.005)
            GPIO.output(self._rst, GPIO.LOW)
            time.sleep(0.01)
            GPIO.output(self._rst, GPIO.HIGH)
            time.sleep(0.15)
        except Exception:
            self.logger.error("Reset failed", exc_info=True)

    def backlight(self, state: bool) -> None:
        """Turn display backlight on/off."""
        try:
            GPIO.output(self._bl, GPIO.HIGH if state else GPIO.LOW)
        except Exception:
            self.logger.warning("Backlight control failed", exc_info=True)

    def close(self) -> None:
        """Release SPI and GPIO resources."""
        try:
            self.spi.close()
        except Exception:
            self.logger.warning("Error closing SPI", exc_info=True)
        finally:
            try:
                GPIO.cleanup([self._dc, self._rst, self._bl])
            except Exception:
                self.logger.warning("GPIO cleanup failed", exc_info=True)

    # -------------
    # SPI helpers
    # -------------
    def _write_command(self, command: int) -> None:
        try:
            GPIO.output(self._dc, GPIO.LOW)
            self.spi.xfer2([command & 0xFF])
        except Exception:
            self.logger.error("Command write failed", exc_info=True)
            self._recover_spi()

    def _write_data(self, data: Union[bytes, bytearray, List[int]]) -> None:
        """
        Send data to the display, chunked so we never exceed _MAX_SPI_CHUNK.

        Accepts:
          - bytes / bytearray
          - list of ints (0-255)
        """
        try:
            GPIO.output(self._dc, GPIO.HIGH)

            if isinstance(data, int):
                data = [data]

            length = len(data)
            for i in range(0, length, _MAX_SPI_CHUNK):
                chunk = data[i : i + _MAX_SPI_CHUNK]
                # spidev accepts list or bytes; both are fine
                self.spi.xfer2(chunk)
        except Exception:
            self.logger.error("Data write failed", exc_info=True)
            self._recover_spi()

    def _recover_spi(self) -> None:
        """Best-effort SPI recovery without killing your app."""
        self.logger.warning("Attempting SPI recovery...")
        try:
            self.spi.close()
            time.sleep(0.1)
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 24_000_000
            self.reset()
            self._init_display(False)
            self.set_rotation(self.rotation)
            self.logger.info("SPI recovery successful")
        except Exception:
            self.logger.critical("SPI recovery failed", exc_info=True)

    # -------------
    # Panel init / rotation
    # -------------
    def _init_display(self, invert: bool) -> None:
        try:
            self._write_command(_CMD_SWRESET)
            time.sleep(0.15)

            self._write_command(_CMD_SLPOUT)
            time.sleep(0.5)

            # Frame rate control
            self._write_command(_CMD_FRMCTR1)
            self._write_data([0x01, 0x2C, 0x2D])

            self._write_command(_CMD_FRMCTR2)
            self._write_data([0x01, 0x2C, 0x2D])

            self._write_command(_CMD_FRMCTR3)
            self._write_data([0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D])

            self._write_command(_CMD_INVCTR)
            self._write_data([0x07])

            # Power control
            self._write_command(_CMD_PWCTR1)
            self._write_data([0xA2, 0x02, 0x84])

            self._write_command(_CMD_PWCTR2)
            self._write_data([0xC5])

            self._write_command(_CMD_PWCTR3)
            self._write_data([0x0A, 0x00])

            self._write_command(_CMD_PWCTR4)
            self._write_data([0x8A, 0x2A])

            self._write_command(_CMD_PWCTR5)
            self._write_data([0x8A, 0xEE])

            self._write_command(_CMD_VMCTR1)
            self._write_data([0x0E])

            # Color mode
            self._write_command(_CMD_COLMOD)
            self._write_data([_COLMOD_16BIT])

            # Normal / inverted mode
            self._write_command(_CMD_INVON if invert else _CMD_NORON)

            # Turn on
            time.sleep(0.01)
            self._write_command(_CMD_DISPON)
            time.sleep(0.1)
        except Exception:
            self.logger.critical("Display init failed", exc_info=True)
            raise

    def set_rotation(self, rotation: int) -> None:
        """Rotate display: 0, 90, 180, or 270 degrees."""
        rotation = rotation % 360
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Rotation must be 0, 90, 180, or 270")

        madctl = _MADCTL_RGB

        if rotation == 0:
            madctl |= _MADCTL_MX | _MADCTL_MY
            self.width, self.height = self.orig_width, self.orig_height
            self._x_offset = self._hw_x_offset
            self._y_offset = self._hw_y_offset
        elif rotation == 90:
            madctl |= _MADCTL_MY | _MADCTL_MV
            self.width, self.height = self.orig_height, self.orig_width
            self._x_offset = self._hw_y_offset
            self._y_offset = self._hw_x_offset
        elif rotation == 180:
            # raw panel orientation
            self.width, self.height = self.orig_width, self.orig_height
            self._x_offset = self._hw_x_offset
            self._y_offset = self._hw_y_offset
        else:  # 270
            madctl |= _MADCTL_MX | _MADCTL_MV
            self.width, self.height = self.orig_height, self.orig_width
            self._x_offset = self._hw_y_offset
            self._y_offset = self._hw_x_offset

        self._write_command(_CMD_MADCTL)
        self._write_data([madctl])

        self._set_window(0, 0, self.width - 1, self.height - 1)
        self.rotation = rotation
        self.logger.debug("Rotation set to %d°", rotation)

    def _set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Set active drawing window."""
        x0 += self._x_offset
        x1 += self._x_offset
        y0 += self._y_offset
        y1 += self._y_offset

        # Column
        self._write_command(_CMD_CASET)
        self._write_data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])

        # Row
        self._write_command(_CMD_RASET)
        self._write_data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])

        # Memory write
        self._write_command(_CMD_RAMWR)

    # -------------
    # Color helpers
    # -------------
    def _rgb_to_565(self, color: Union[Tuple[int, int, int], str]) -> int:
        """Convert RGB tuple or '#RRGGBB' to 16-bit 565."""
        if isinstance(color, str):
            r, g, b = hex_to_rgb(color)
        else:
            r, g, b = color
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def _image_to_data(self, image: Image.Image) -> bytes:
        """
        Convert PIL Image (mode 'RGB') to RGB565 byte stream.

        This uses pure Python loops. For 160x80 this is cheap enough and avoids
        pulling numpy onto the Pi.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        buf = bytearray()
        append = buf.extend

        for r, g, b in image.getdata():
            color565 = self._rgb_to_565((r, g, b))
            append(color565.to_bytes(2, "big"))

        return bytes(buf)

    # -------------
    # High-level API
    # -------------
    def display(self, image: Image.Image) -> None:
        """Blit a PIL image to the panel."""
        try:
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height), Image.LANCZOS)

            pixel_data = self._image_to_data(image)

            self._set_window(0, 0, self.width - 1, self.height - 1)
            self._write_data(pixel_data)
        except Exception:
            self.logger.error("Display update failed", exc_info=True)

    def fill(self, color: Union[Tuple[int, int, int], str, int]) -> None:
        """Fill the screen with a solid color."""
        try:
            if isinstance(color, (tuple, str)):
                color = self._rgb_to_565(color)

            hi = (color >> 8) & 0xFF
            lo = color & 0xFF
            pair = [hi, lo]

            total_pixels = self.width * self.height
            self._set_window(0, 0, self.width - 1, self.height - 1)
            GPIO.output(self._dc, GPIO.HIGH)

            pixels_per_chunk = _MAX_SPI_CHUNK // 2
            for offset in range(0, total_pixels, pixels_per_chunk):
                chunk_size = min(pixels_per_chunk, total_pixels - offset)
                self.spi.xfer2(pair * chunk_size)
        except Exception:
            self.logger.error("Fill operation failed", exc_info=True)

    # -------------------------
    # DRAWING CONVENIENCES
    # -------------------------
    def create_canvas(
        self,
        bg_color: Union[Tuple[int, int, int], str] = "#000000",
    ) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
        """
        Create an RGB canvas sized to the current rotation.

        Returns (PIL.Image, ImageDraw.Draw).
        """
        if isinstance(bg_color, str):
            bg_color = hex_to_rgb(bg_color)
        img = Image.new("RGB", (self.width, self.height), bg_color)
        return img, ImageDraw.Draw(img)

    def draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: Tuple[int, int],
        font: Optional[ImageFont.FreeTypeFont] = None,
        color: Tuple[int, int, int] = (255, 255, 255),
        align: str = "left",
        max_width: Optional[int] = None,
    ) -> None:
        """
        Helper to draw text with optional alignment and truncation.
        Used by HUD code if you want future extensions.
        """
        font = font or ST7735S._DEFAULT_FONT

        # Truncate if needed
        if max_width is not None:
            try:
                bbox = font.getbbox(text)
                width = bbox[2] - bbox[0]
            except AttributeError:
                width, _ = draw.textsize(text, font=font)

            if width > max_width:
                while text and len(text) > 1:
                    test = text + "..."
                    try:
                        bbox = font.getbbox(test)
                        width = bbox[2] - bbox[0]
                    except AttributeError:
                        width, _ = draw.textsize(test, font=font)
                    if width <= max_width:
                        text = test
                        break
                    text = text[:-1]

        x, y = position
        if align != "left":
            try:
                bbox = font.getbbox(text)
                t_w = bbox[2] - bbox[0]
            except AttributeError:
                t_w, _ = draw.textsize(text, font=font)

            if align == "center":
                x -= t_w // 2
            elif align == "right":
                x -= t_w

        draw.text((x, y), text, font=font, fill=color)
