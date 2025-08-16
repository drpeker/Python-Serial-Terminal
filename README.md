# Python-Serial-Terminal
Multiplatform serial terminal written on python.

# Python Serial Terminal — User Guide

This guide explains how to install, run, and use the **Python Serial Terminal** GUI (`mac_serial_terminal_v6_eng.py`). It also covers keyboard behavior (including **Ctrl** combinations), end‑of‑line settings, and common troubleshooting steps.

> Requires **Python 3.8+** and **pySerial**. The app runs on **macOS**, **Windows**, and **Linux** (GUI via Tkinter).

---

## 1) Features (at a glance)

- 40×28 terminal view (black background, green text; Menlo font or system fallback).
- **Ctrl key support:** sends true control bytes (e.g., Ctrl+C → `0x03`, Ctrl+Q → `0x11`, Ctrl+[ → `0x1B`, etc.).
- Minimal **ANSI color** handling (SGR foreground codes 30–37 and 90–97).
- **EOL selectable**: `CR`, `LF`, or `CRLF` when sending lines.
- **Backspace selectable**: `^H (0x08)` or `DEL (0x7F)`.
- **Local Echo** option (shows what you type locally).
- **RTS/CTS** hardware flow control option.
- Non‑blocking serial reads with smooth UI.

---

## 2) Installation

1. Ensure Python 3.8+ is installed.
2. Install pySerial:
   ```bash
   pip install pyserial
   ```
3. Download the app file:
   - `mac_serial_terminal_v6_eng.py`

> On macOS you may need vendor drivers for certain USB‑serial adapters (e.g., FTDI/CP210x). On Linux, ensure your user has permission to access serial devices (see **Troubleshooting**).

---

## 3) Launching the App

Run from a terminal or double‑click (depending on OS configuration):

```bash
python3 mac_serial_terminal_v6_eng.py
```

**Port naming by OS**

- **macOS:** `/dev/tty.*` or `/dev/cu.*` (e.g., `/dev/tty.usbserial-XXXX`)
- **Windows:** `COMx` (e.g., `COM3`)
- **Linux:** `/dev/ttyUSBx`, `/dev/ttyACMx`

Use the **Port** drop‑down and **Refresh** button to select the device, set **Baud**, optionally enable **RTS/CTS**, then click **Connect**.

---

## 4) UI Overview

- **Port / Refresh**: choose and refresh available serial ports.
- **Baud**: common baud rates; default `115200`.
- **Flow**: `No control` or `RTS/CTS`.
- **Connect / Disconnect**: open/close the serial port.
- **Terminal area (40×28)**: shows incoming data. Type here to send characters.
- **Send field + EOL**: type a line and click **Send** (or press **Enter** in the field). Chooses EOL: `CR`, `LF`, or `CRLF`.
- **Backspace mode**: selects what **Backspace** transmits: `^H (0x08)` or `DEL (0x7F)`.
- **Local Echo**: if enabled, characters you type are also shown locally.
- **Clear**: clears the terminal display.
- **Status bar**: shows connection state and settings.

---

## 5) Keyboard Behavior & Control Characters

### Typing in the terminal area
- **Printable characters** are sent directly.
- **Enter (Return)** sends only the selected EOL (no extra CR/LF is added by the terminal area itself).
- **Backspace** sends either `0x08` (**^H**) or `0x7F` (**DEL**) depending on the **Backspace** selector.

### Ctrl combinations (sent as control bytes)
- `Ctrl + A … Z` → `0x01 … 0x1A` (e.g., **Ctrl+C** → `0x03`, **Ctrl+Q** → `0x11`).
- Special cases:
  - **Ctrl+[@]** or **Ctrl+Space** → `0x00` (NUL)
  - **Ctrl+[** → `0x1B` (ESC)
  - **Ctrl+\\** → `0x1C` (FS)
  - **Ctrl+]** → `0x1D` (GS)
  - **Ctrl+^** → `0x1E` (RS)
  - **Ctrl+_** → `0x1F` (US)
  - **Ctrl+?** → `0x7F` (DEL)
  - **Ctrl+2** → `0x00` (NUL) on many layouts
- These control bytes are **not** echoed to the screen unless **Local Echo** is enabled.

### Notes
- The app does **not** paste clipboard text into the terminal area as a bulk send. To send a full line/string, use the **Send** field and press **Enter** (or click **Send**).

---

## 6) Receiving Data (Display Rules)

- **CR (0x0D)** is suppressed to avoid double spacing with `CRLF`. **LF (0x0A)** advances the line.
- **TAB (0x09)** is rendered as 4 spaces.
- Minimal **ANSI SGR** handling: foreground color changes for codes `30–37` and `90–97` (e.g., 31=red, 32=green). Other ANSI sequences are ignored.
- Non‑printable control bytes (except handled ones like BS, LF) display as `.` to keep the terminal compact.
- Backspace sequences like `BS SP BS` are collapsed into a single delete on screen.

---

## 7) End‑of‑Line (EOL) & Backspace Modes

| Setting | Effect |
|---|---|
| **EOL** = `None` | Sends nothing when transmitting a line via **Send**. |
| **EOL** = `CR` | Sends `\r` (0x0D). |
| **EOL** = `LF` | Sends `\n` (0x0A). |
| **EOL** = `CRLF` | Sends `\r\n` (0x0D 0x0A). |
| **Backspace** = `^H` | Terminal **Backspace** sends `0x08`. |
| **Backspace** = `DEL` | Terminal **Backspace** sends `0x7F`. |

Choose the combination that matches your device/firmware expectations.

---

## 8) Flow Control

- **No control** (default): no RTS/CTS signaling.
- **RTS/CTS**: enables hardware flow control. (XON/XOFF is not used by this app.)

---

## 9) Troubleshooting

**Port not listed**  
- Check cable and drivers (FTDI/CP210x). Click **Refresh**.  
- On Windows, verify the COM port number in Device Manager.  
- On macOS, look for `/dev/tty.*` or `/dev/cu.*` devices.

**“Permission denied” (Linux)**  
- Add your user to the `dialout` (or relevant) group, then log out/in:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
  Or run the app with `sudo` as a quick test.

**“Resource busy / already in use”**  
- Another program is holding the port (e.g., a terminal, debugger, or background service). Close it or reboot the device.

**Garbled text**  
- Mismatched **Baud**, **Parity**, or **Stop bits** on the target. This app uses 8‑N‑1 fixed; set your device to match.

**Backspace not working as expected**  
- Switch the **Backspace** mode between `^H` and `DEL`.

**Line endings not accepted**  
- Change **EOL** to the format expected by your device (`CR`, `LF`, or `CRLF`).

**Colors not showing**  
- Only minimal ANSI **foreground** color codes are handled (`30–37`, `90–97`). Other attributes are ignored.

---

## 10) Known Limitations

- The terminal is fixed to a 40×28 display area (you can resize the window, but the text area keeps that logical size).
- Only **hardware** flow control option is **RTS/CTS**; software XON/XOFF is not used.
- No session logging to file (can be added if needed).
- Minimal ANSI support (foreground colors only).

---

## 11) Tips

- Keep **Local Echo** **off** if your device echoes characters; otherwise you may see duplicates.
- For sending multi‑byte commands reliably, use the **Send** field with the proper **EOL** setting instead of typing fast in the terminal area.
- If your device expects **Ctrl** sequences (e.g., Ctrl+C to break), focus the terminal area and press the needed combination; the app sends the true control byte.

---

## 12) Uninstall / Remove

Simply delete the file `mac_serial_terminal_v6_eng.py`. The app stores no configuration files or registry entries.

---

**Enjoy tinkering!**

