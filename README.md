# 🖥️ Pi Rack HUD

A compact, production-quality hardware dashboard for Raspberry Pi mini-rack setups.

![HUD Preview](./images/hud-preview.jpg)
_(placeholder — add your real HUD photo here)_

---

## ✨ Features & Overview

The Pi Rack HUD runs on a **0.96” ST7735S IPS display (80×160)**, providing a clean, Apple-like UI designed for 24/7 low-load operation (Raspberry Pi OS Lite recommended).

- **Key Metrics Displayed:** CPU usage, RAM usage (both color-coded), Temperature, Network throughput (Up/Down), and Hostname (with Nerd Font icons).
- **Design:** Professional dark theme with meaningful color accents and smooth **2× supersampled rendering** for crisp text.
- **Deployment:** Auto-start on boot via `systemd` and ultra-low CPU usage (typically <1%).

---

## 🧰 Hardware & Wiring

This project requires a standard Raspberry Pi 3B/3B+ or newer with SPI support, and a small IPS display.

### 🔌 Requirements

| Component    | Notes                                                 |
| :----------- | :---------------------------------------------------- |
| Raspberry Pi | 3B/3B+ or any Pi with SPI support.                    |
| Display      | **0.96” 80×160 IPS ST7735S** (SPI-based mini screen). |
| Power        | Standard Pi PSU.                                      |

### 📌 Wiring Guide

Below is the complete mapping between the **ST7735S display pins** and the **Raspberry Pi GPIO pins**.

| Display Pin | Pi Pin | Pi Function       | Description       |
| :---------- | :----- | :---------------- | :---------------- |
| **VCC**     | Pin 1  | 3.3V Power        | Power (3.3V only) |
| **GND**     | Pin 6  | GND               | Ground            |
| **SCL**     | Pin 23 | GPIO11 (SPI CLK)  | Clock             |
| **SDA**     | Pin 19 | GPIO10 (SPI MOSI) | MOSI (Data Out)   |
| **CS**      | Pin 24 | GPIO8 (SPI CE0)   | Chip Select       |
| **DC**      | Pin 16 | GPIO23            | Data/Command      |
| **RES**     | Pin 18 | GPIO24            | Reset             |
| **BLK**     | Pin 12 | GPIO18 (PWM/ON)   | Backlight         |

> **Note:** You must enable SPI before running the installer.
>
> ```bash
> sudo raspi-config
> Interface Options → SPI → Enable
> sudo reboot
> ```

---

## 📦 Installation & Management

### 🚀 One-Step Install

Run the following command on your Raspberry Pi to install the HUD and set up auto-start:

```bash
curl -s [https://raw.githubusercontent.com/atefalvi/pi-rack-hud/main/install.sh](https://raw.githubusercontent.com/atefalvi/pi-rack-hud/main/install.sh) | bash
```

## 📦 Installation & Management

**The installer will:**

- Install Nerd Fonts.
- Clone the GitHub repository.
- Install Python dependencies.
- Create and enable a `systemd` service for auto-start.
- Start the Pi Rack HUD service immediately.

### 🛠️ Service Management

| Action                 | Command                                              |
| :--------------------- | :--------------------------------------------------- |
| **Check status**       | `systemctl status pi-rack-hud.service`               |
| **Restart**            | `sudo systemctl restart pi-rack-hud.service`         |
| **View logs**          | `journalctl -u pi-rack-hud.service -n 50 --no-pager` |
| **Disable Auto-start** | `sudo systemctl disable pi-rack-hud.service`         |

### 🔄 Updating

To pull the latest code and restart the service:

```bash
cd ~/pi-rack-hud
./update.sh
```

_(Alternatively, run `sudo systemctl restart pi-rack-hud.service`)_

---

## 🎨 HUD Layout & Components

![HUD Layout Placeholder](./images/hud-layout.jpg)
_(placeholder — add real screenshot of the layout here)_

The HUD utilizes **Nerd Font 0xProto** for all icons and displays:

- Linux icon + **Hostname** (top left)
- **Temperature** (top right)
- **CPU** + **RAM** usage bars (middle)
- Network **Up/Down MB** counters (bottom)

**Color Thresholds:** Metrics change color based on usage thresholds (Green → normal, Yellow → moderate, Red → high usage).

---

## 📁 Project Structure

pi-rack-hud/
│
├── hud.py                  # Main HUD program
├── st7735s.py              # Display driver
├── install.sh              # One-command installer
├── update.sh               # Git pull + service restart
├── hud.service.template    # Systemd service template
├── requirements.txt        # Python dependencies
└── README.md               # This file

---

## 🧪 Troubleshooting

| Issue                            | Solution                                                                                                                                                     |
| :------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Blank screen**                 | Ensure wiring matches the table exactly, display uses 3.3V, and SPI is enabled (`sudo raspi-config`). Check logs: `journalctl -u pi-rack-hud.service -n 50`. |
| **Icons are squares**            | The font is missing. Reinstall fonts by running the full install command again, or manually run: `fc-cache -f -v`                                            |
| **Text is misaligned / rotated** | Adjust the rotational settings in `hud.py`: `ROTATION = 270`, `x_offset = 24`, `y_offset = 0` (your values may vary).                                        |
