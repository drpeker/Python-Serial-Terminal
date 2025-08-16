#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac Serial Terminal (40x28) — Tkinter + pySerial

- macOS seri portlarını listeler, seçim yaptırır
- Baud seçimi
- Donanım akış kontrolü: RTS/CTS ON veya No control
- 40 sütun x 28 satır terminal görünümü (monospace)
- Siyah arka plan + koyu yeşil metin
- Slave tarafından gönderilen ANSI SGR (önplan renkleri) desteklenir
- CR/LF çift satır boşluğu yaratmaz (CR yutulur, LF satır atlatır)
- Backspace (^H) ve TAB (4 boşluk) işlenir
- Terminale doğrudan yazıp Enter/Backspace gönderebilirsiniz
- Alt kısımda satır-gönderme ve EOL seçimi
- Bağlan/Kes, Temizle

Gereksinimler:
    pip install pyserial
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict
try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    raise SystemExit("pyserial not found. Install:  pip install pyserial") from e

APP_TITLE = "Python Serial Terminal V1.0 by Peker"
TERMINAL_COLS = 40
TERMINAL_ROWS = 28

COMMON_BAUDS = [
    300, 600, 1200, 2400, 4800, 9600,
    14400, 19200, 38400, 57600, 115200, 230400, 460800, 921600
]

EOL_OPTIONS = {
    "None": "",
    "CR (\\r)": "\r",
    "LF (\\n)": "\n",
    "CRLF (\\r\\n)": "\r\n",
}


class SerialTerminalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("")
        self.configure(padx=8, pady=8)

        self.ser: serial.Serial | None = None
        self.read_job = None
        self.connected = False

        # ----- Üst Kısım: Port, Yenile, Baud, Flow, Bağlan -----
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for c in range(4):
            top.columnconfigure(c, weight=0)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Port:").grid(row=0, column=0, padx=(0, 6), sticky="w")
        self.port_cmb = ttk.Combobox(top, width=38, state="readonly", values=[])
        self.port_cmb.grid(row=0, column=1, sticky="ew")
        self.refresh_btn = ttk.Button(top, text="Refresh", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=(6, 0))

        ttk.Label(top, text="Baud:").grid(row=1, column=0, padx=(0, 6), sticky="w", pady=(6, 0))
        self.baud_cmb = ttk.Combobox(top, width=12, state="readonly", values=[str(b) for b in COMMON_BAUDS])
        self.baud_cmb.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self.baud_cmb.set("115200")

        ttk.Label(top, text="Flow:").grid(row=1, column=2, padx=(6, 6), sticky="e", pady=(6, 0))
        self.flow_cmb = ttk.Combobox(top, width=14, state="readonly", values=["No control", "RTS/CTS"])
        self.flow_cmb.grid(row=1, column=3, sticky="w", pady=(6, 0))
        self.flow_cmb.set("No control")

        self.connect_btn = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=0, column=3, padx=(6, 0))

        # ----- Terminal (40x28) -----
        term_frame = ttk.Frame(self)
        term_frame.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.term = tk.Text(
            term_frame,
            width=TERMINAL_COLS,
            height=TERMINAL_ROWS,
            wrap="char",
            font=("Menlo", 13),
            undo=False,
            bg="#000000",
            fg="#00aa00",
            insertbackground="#00aa00",
            spacing1=0,
            spacing2=0,
            spacing3=0,
        )
        self.term.grid(row=0, column=0, sticky="nsew")
        term_frame.rowconfigure(0, weight=1)
        term_frame.columnconfigure(0, weight=1)

        self.scrollbar = ttk.Scrollbar(term_frame, orient="vertical", command=self.term.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.term.configure(yscrollcommand=self.scrollbar.set)

        # ANSI renk desteği (SGR: 30-37, 90-97)
        self._ansi_colors: Dict[int, str] = {
            30: "#000000", 31: "#aa0000", 32: "#00aa00", 33: "#aa5500",
            34: "#0000aa", 35: "#aa00aa", 36: "#00aaaa", 37: "#aaaaaa",
            90: "#555555", 91: "#ff5555", 92: "#55ff55", 93: "#ffff55",
            94: "#5555ff", 95: "#ff55ff", 96: "#55ffff", 97: "#ffffff",
        }
        for code, color in self._ansi_colors.items():
            self.term.tag_configure(f"fg{code}", foreground=color)
        self.term.tag_configure("fgdefault", foreground="#00aa00")
        self._current_tag = "fgdefault"
        self._ansi_state = {"in_esc": False, "buf": ""}

        # Terminal yazı alanını kullanıcı düzenleyemesin (yine de tuşları yakalayacağız)
        self.term.config(state="disabled")
        self.term.bind("<Key>", self._on_term_key)

        # ----- Alt Gönderme Satırı -----
        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        bottom.columnconfigure(1, weight=1)

        ttk.Label(bottom, text="Send:").grid(row=0, column=0, sticky="w")
        self.send_entry = ttk.Entry(bottom)
        self.send_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        self.send_entry.bind("<Return>", self._send_entry_return)

        ttk.Label(bottom, text="EOL:").grid(row=0, column=2, sticky="w")
        self.eol_cmb = ttk.Combobox(bottom, width=12, state="readonly", values=list(EOL_OPTIONS.keys()))
        self.eol_cmb.grid(row=0, column=3, sticky="w")
        self.eol_cmb.set("CR (\\r)")

        ttk.Label(bottom, text="Backspace:").grid(row=0, column=4, sticky="e", padx=(12,2))
        self.bs_cmb = ttk.Combobox(bottom, width=12, state="readonly", values=["^H (0x08)", "DEL (0x7F)"])
        self.bs_cmb.grid(row=0, column=5, sticky="w")
        self.bs_cmb.set("^H (0x08)")

        self.send_btn = ttk.Button(bottom, text="Send", command=self.send_line)
        self.send_btn.grid(row=0, column=6, padx=(6, 0))

        self.clear_btn = ttk.Button(bottom, text="Clear", command=self.clear_terminal)
        self.clear_btn.grid(row=0, column=7, padx=(6, 0))

        self.local_echo = tk.BooleanVar(value=False)
        self.echo_chk = ttk.Checkbutton(bottom, text="Local Echo", variable=self.local_echo)
        self.echo_chk.grid(row=0, column=8, padx=(12,0))

        # Durum çubuğu
        self.status = ttk.Label(self, text="Ready", anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        # İlk port listesi
        self.refresh_ports()

    # ----- Port Yönetimi -----
    def refresh_ports(self):
        ports = list_ports.comports()
        values: List[str] = []
        for p in ports:
            desc = f"{p.device} ({p.description})" if p.description else p.device
            values.append(desc)
        self.port_cmb["values"] = values
        if values and not self.port_cmb.get():
            self.port_cmb.current(0)

    def _parse_selected_port(self):
        sel = self.port_cmb.get().strip()
        if not sel:
            return None
        return sel.split(" (")[0]

    def toggle_connect(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self._parse_selected_port()
        if not port:
            messagebox.showwarning("Uyarı", "Bir seri port seçin.")
            return
        try:
            baud = int(self.baud_cmb.get())
        except ValueError:
            messagebox.showwarning("Uyarı", "Geçerli bir baud seçin.")
            return

        rtscts = (self.flow_cmb.get() == "RTS/CTS")
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,          # non-blocking
                xonxoff=False,
                rtscts=rtscts,
                dsrdtr=False,
                write_timeout=0
            )
        except Exception as e:
            messagebox.showerror("Connection Error", f"Cannot opened Port:\n{e}")
            self.ser = None
            return

        self.connected = True
        self.connect_btn.config(text="Disconnect")
        self.status.config(text=f"Connected: {port} @ {baud} bps | Flow: {'RTS/CTS' if rtscts else 'No'}")
        self.term_focus()
        self._schedule_reader()

    def disconnect(self):
        if self.read_job is not None:
            try:
                self.after_cancel(self.read_job)
            except Exception:
                pass
            self.read_job = None

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.connected = False
        self.connect_btn.config(text="Connect")
        self.status.config(text="Disconnected.")

    # ----- Okuyucu döngüsü -----
    def _schedule_reader(self):
        if not self.connected or self.ser is None or not self.ser.is_open:
            return
        try:
            n = self.ser.in_waiting
            if n:
                data = self.ser.read(n)
                if data:
                    self._process_ansi_and_append(data)
        except Exception as e:
            self._append_text(f"\n[Error: cannot read: {e}]\n")
            self.disconnect()
            return
        self.read_job = self.after(10, self._schedule_reader)  # ~100 Hz

    # ----- Terminal çıktı -----
    def clear_terminal(self):
        self.term.config(state="normal")
        self.term.delete("1.0", "end")
        self.term.config(state="disabled")

    def _append_text(self, s: str, tag: str | None = None):
        self.term.config(state="normal")
        if tag:
            self.term.insert("end", s, (tag,))
        else:
            self.term.insert("end", s)
        self.term.see("end")
        self.term.config(state="disabled")

    # ----- ANSI + CR/LF işleme -----
    def _process_ansi_and_append(self, b: bytes):
        """
        Minimal ANSI SGR parser: ESC [ ... m ile gelen önplan renklerini uygular.
        Diğer CSI komutlarını yok sayar. CR (0x0D) satır atlatmaz; LF (0x0A) atlatır.
        """
        def set_tag_from_sgr(params):
            if not params or params == [0]:
                self._current_tag = "fgdefault"
                return
            for p in params:
                if p == 0:
                    self._current_tag = "fgdefault"
                elif 30 <= p <= 37 or 90 <= p <= 97:
                    self._current_tag = f"fg{p}"
                # diğer nitelikler (bold/underline/bg) basitlik için yok sayıldı

        text_buf: List[str] = []
        st = self._ansi_state
        i = 0
        while i < len(b):
            ch = b[i]
            # Collapse classic erase sequence: BS SP BS -> single delete
            if ch == 0x08 and i+2 < len(b) and b[i+1] == 0x20 and b[i+2] == 0x08:
                self.term.config(state="normal")
                try:
                    self.term.mark_set("insert", "end-1c")
                    self.term.delete("insert-1c")
                except Exception:
                    pass
                self.term.config(state="disabled")
                i += 3
                continue
            # Backspace (BS or DEL)
            if ch in (0x08, 0x7F):
                self.term.config(state="normal")
                try:
                    self.term.mark_set("insert", "end-1c")
                    self.term.delete("insert-1c")
                except Exception:
                    pass
                self.term.config(state="disabled")
                i += 1
                continue
            # CR: yut (CRLF'de çift boşluk olmasın diye)
            if ch == 0x0D:
                i += 1
                continue
            # TAB: 4 boşluk
            if ch == 0x09:
                text_buf.append("    ")
                i += 1
                continue
            # ESC
            if ch == 0x1B:
                # akümülasyon flush
                if text_buf:
                    self._append_text("".join(text_buf), self._current_tag)
                    text_buf = []
                st["in_esc"] = True
                st["buf"] = ""
                i += 1
                continue
            if st.get("in_esc"):
                st["buf"] += chr(ch)
                i += 1
                # CSI bekleniyor: '[' ile başlamalı ve 'm' ile bitmeli
                if st["buf"].startswith("["):
                    if st["buf"].endswith("m"):
                        inside = st["buf"][1:-1]
                        if inside.strip() == "":
                            set_tag_from_sgr([0])
                        else:
                            try:
                                params = [int(x) if x else 0 for x in inside.split(";")]
                            except ValueError:
                                params = [0]
                            set_tag_from_sgr(params)
                        st["in_esc"] = False
                        st["buf"] = ""
                else:
                    # CSI değilse iptal
                    st["in_esc"] = False
                    st["buf"] = ""
                continue
            # Normal karakterler
            if ch == 0x0A:  # LF
                text_buf.append("\n")
            else:
                if ch < 32 or ch == 127:
                    text_buf.append(".")
                else:
                    text_buf.append(chr(ch))
            i += 1

        if text_buf:
            self._append_text("".join(text_buf), self._current_tag)

    # ====== KONTROL KARAKTERLERİ GÖNDERİMİ ======
    def _is_ctrl_pressed(self, event) -> bool:
        # Tk state bitmask: Control genellikle 0x0004 (platforma göre değişebilir ama Tk standardı budur)
        return bool(event.state & 0x0004)

    def _ctrl_code_from_event(self, event):
        """
        Ctrl+<key> için uygun ASCII kontrol kodunu döndürür (int) veya None.
        - A..Z / a..z  -> 0x01..0x1A
        - Özeller: @ (NUL), [ (ESC), \ (FS), ] (GS), ^ (RS), _ (US), ? (DEL), Space (NUL)
        """
        # Harfler
        if len(event.keysym) == 1 and event.keysym.isalpha():
            return ord(event.keysym.lower()) & 0x1F  # 'a'->1 ... 'z'->26

        # Özel tuş isimleri (Tk keysym)
        special_map = {
            "at": 0x00,              # Ctrl+@
            "space": 0x00,           # Ctrl+Space
            "bracketleft": 0x1B,     # Ctrl+[
            "backslash": 0x1C,       # Ctrl+\
            "bracketright": 0x1D,    # Ctrl+]
            "asciicircum": 0x1E,     # Ctrl+^
            "underscore": 0x1F,      # Ctrl+_
            "question": 0x7F,        # Ctrl+?
        }
        ks = event.keysym.lower()
        if ks in special_map:
            return special_map[ks]

        # Bazı düzenler '2' ile NUL göndermeyi ister (Ctrl+2)
        if ks in ("2",):
            return 0x00

        return None

    def _send_ctrl_byte(self, code: int):
        if not self.connected or self.ser is None or not self.ser.is_open:
            return
        try:
            self.ser.write(bytes([code]))
        except Exception as e:
            self._append_text(f"\n[Err: cannot write: {e}]\n")
            self.disconnect()

    # ----- Terminal içine yazma -----
    def _on_term_key(self, event):
        if not self.connected or self.ser is None or not self.ser.is_open:
            return "break"

        # 1) Ctrl kombinasyonlarını önce yakala (Ctrl+C, Ctrl+Q, Ctrl+...] vs)
        if self._is_ctrl_pressed(event):
            code = self._ctrl_code_from_event(event)
            if code is not None:
                self._send_ctrl_byte(code)
                return "break"
            # Control basılı ama tanımadığımız bir keysym ise düşmeye devam etme:
            return "break"

        # 2) Enter
        if event.keysym == "Return":
            eol = EOL_OPTIONS.get(self.eol_cmb.get(), "")
            try:
                self.ser.write(eol.encode("utf-8", "replace"))
            except Exception as e:
                self._append_text(f"\n[Err: Cannot write: {e}]\n")
                self.disconnect()
            if self.local_echo.get():
                # Show a newline locally to mimic typed EOL
                self._append_text("\n", self._current_tag)
            return "break"

        # 3) Backspace
        if event.keysym == "BackSpace":
            try:
                bs_mode = self.bs_cmb.get()
                if bs_mode.startswith("^H"):
                    self.ser.write(b"\x08")  # ^H
                else:
                    self.ser.write(b"\x7F")  # DEL
            except Exception as e:
                self._append_text(f"\n[Err: cannot write: {e}]\n")
                self.disconnect()
            if self.local_echo.get():
                # delete one char locally
                self.term.config(state="normal")
                try:
                    self.term.mark_set("insert", "end-1c")
                    self.term.delete("insert-1c")
                except Exception:
                    pass
                self.term.config(state="disabled")
            return "break"

        # 4) Yazılabilir tek karakterler
        if len(event.char) == 1:
            try:
                self.ser.write(event.char.encode("utf-8", "replace"))
            except Exception as e:
                self._append_text(f"\n[Error: cannot write: {e}]\n")
                self.disconnect()
            if self.local_echo.get():
                self._append_text(event.char, self._current_tag)
            return "break"

        return "break"

    def _send_entry_return(self, event):
        self.send_line()
        return "break"

    def send_line(self):
        if not self.connected or self.ser is None or not self.ser.is_open:
            return
        text = self.send_entry.get()
        eol = EOL_OPTIONS.get(self.eol_cmb.get(), "")
        try:
            self.ser.write(text.encode("utf-8", "replace") + eol.encode("utf-8"))
        except Exception as e:
            self._append_text(f"\n[Error: cannot write: {e}]\n")
            self.disconnect()
            return
        self.send_entry.delete(0, "end")

    def term_focus(self):
        self.term.focus_set()

    def on_close(self):
        self.disconnect()
        self.destroy()


def main():
    app = SerialTerminalApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
