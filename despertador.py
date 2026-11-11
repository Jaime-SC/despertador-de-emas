"""Despertador simple entre dos PCs de la misma red."""

from __future__ import annotations

import ctypes
import json
import shutil
import socket
import struct
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
SONIDOS_DIR = APP_DIR / "sonidos"
CONFIG_PATH = APP_DIR / "config.json"
PUERTO = 45678
EXTENSIONES = {".mp3", ".wav", ".ogg", ".wma", ".m4a", ".aac"}
NOMBRE_STARTUP = "DespertadorEmas.vbs"
ALIAS_AUDIO = "despertador_emas"


def ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def cargar_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"ip_companero": "", "puerto": PUERTO}


def guardar_config(data: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def listar_sonidos() -> list[Path]:
    SONIDOS_DIR.mkdir(exist_ok=True)
    return sorted(
        p
        for p in SONIDOS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES
    )


def _mci(comando: str) -> int:
    buf = ctypes.create_unicode_buffer(512)
    return ctypes.windll.winmm.mciSendStringW(comando, buf, 511, None)


def reproducir(ruta: Path, esperar: bool = False) -> None:
    """Reproduce audio con el motor MCI de Windows (mp3, wav, etc.)."""
    path = str(ruta.resolve())
    _mci(f"close {ALIAS_AUDIO}")
    codigo = _mci(f'open "{path}" type mpegvideo alias {ALIAS_AUDIO}')
    if codigo != 0:
        codigo = _mci(f'open "{path}" alias {ALIAS_AUDIO}')
    if codigo != 0:
        raise RuntimeError(
            "Windows no pudo abrir ese audio. Prueba con .mp3 o .wav."
        )
    wait = " wait" if esperar else ""
    if _mci(f"play {ALIAS_AUDIO}{wait}") != 0:
        _mci(f"close {ALIAS_AUDIO}")
        raise RuntimeError("No se pudo reproducir el audio.")
    if esperar:
        _mci(f"close {ALIAS_AUDIO}")


def enviar_sonido(ip: str, puerto: int, ruta: Path) -> None:
    datos = ruta.read_bytes()
    nombre = ruta.name.encode("utf-8")
    with socket.create_connection((ip, puerto), timeout=8) as sock:
        sock.sendall(struct.pack("!I", len(nombre)))
        sock.sendall(nombre)
        sock.sendall(struct.pack("!Q", len(datos)))
        sock.sendall(datos)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexión cerrada")
        buf.extend(chunk)
    return bytes(buf)


def manejar_cliente(conn: socket.socket) -> None:
    tmp_path: Path | None = None
    try:
        with conn:
            nlen = struct.unpack("!I", _recv_exact(conn, 4))[0]
            nombre = _recv_exact(conn, nlen).decode("utf-8")
            size = struct.unpack("!Q", _recv_exact(conn, 8))[0]
            if size > 30 * 1024 * 1024:
                raise ValueError("Archivo de audio demasiado grande")
            datos = _recv_exact(conn, size)

            sufijo = Path(nombre).suffix.lower() or ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=sufijo) as tmp:
                tmp.write(datos)
                tmp_path = Path(tmp.name)
            reproducir(tmp_path, esperar=True)
    except Exception as exc:  # noqa: BLE001
        print(f"Error al recibir sonido: {exc}")
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def servidor(puerto: int, stop: threading.Event) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", puerto))
        server.listen(5)
        server.settimeout(1.0)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            threading.Thread(target=manejar_cliente, args=(conn,), daemon=True).start()


def ruta_startup() -> Path:
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / NOMBRE_STARTUP
    )


def crear_acceso_startup() -> Path:
    destino = ruta_startup()
    pythonw = Path(sys.executable)
    if pythonw.name.lower() == "python.exe":
        candidato = pythonw.with_name("pythonw.exe")
        if candidato.exists():
            pythonw = candidato

    script = Path(__file__).resolve()
    contenido = (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.Run """{pythonw}"" ""{script}""", 0, False\r\n'
    )
    destino.write_text(contenido, encoding="utf-8")
    return destino


def quitar_acceso_startup() -> bool:
    destino = ruta_startup()
    if destino.exists():
        destino.unlink()
        return True
    return False


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Despertador de Emas")
        self.geometry("460x520")
        self.minsize(420, 480)
        self.configure(bg="#1a1f2e")

        self.config_data = cargar_config()
        self.stop_event = threading.Event()
        self.puerto = int(self.config_data.get("puerto", PUERTO))

        SONIDOS_DIR.mkdir(exist_ok=True)
        self._armar_ui()
        self._refrescar_lista()

        self.servidor_hilo = threading.Thread(
            target=servidor, args=(self.puerto, self.stop_event), daemon=True
        )
        self.servidor_hilo.start()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def _armar_ui(self) -> None:
        estilo = {"bg": "#1a1f2e", "fg": "#e8ecf4"}
        tk.Label(
            self,
            text="Despertador de Emas",
            font=("Segoe UI", 18, "bold"),
            **estilo,
        ).pack(pady=(18, 4))

        self.mi_ip = ip_local()
        marco_mi_ip = tk.Frame(self, bg="#1a1f2e")
        marco_mi_ip.pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(
            marco_mi_ip,
            text=f"Tu IP (dásela a tu compañero): {self.mi_ip}",
            font=("Segoe UI", 10),
            bg="#1a1f2e",
            fg="#8b95a8",
        ).pack(side="left")
        tk.Button(
            marco_mi_ip,
            text="Copiar IP",
            command=self._copiar_mi_ip,
            bg="#2f3b52",
            fg="#e8ecf4",
            activebackground="#3a4863",
            relief="flat",
            padx=8,
            pady=2,
        ).pack(side="left", padx=(10, 0))

        marco_ip = tk.Frame(self, bg="#1a1f2e")
        marco_ip.pack(fill="x", padx=24)
        tk.Label(
            marco_ip,
            text="IP del compañero (la que él te pase):",
            **estilo,
        ).pack(anchor="w")
        self.ip_var = tk.StringVar(value=self.config_data.get("ip_companero", ""))
        tk.Entry(
            marco_ip,
            textvariable=self.ip_var,
            font=("Segoe UI", 12),
            bg="#2a3142",
            fg="#e8ecf4",
            insertbackground="#e8ecf4",
            relief="flat",
        ).pack(fill="x", pady=(4, 0), ipady=6)

        marco_sonidos = tk.Frame(self, bg="#1a1f2e")
        marco_sonidos.pack(fill="both", expand=True, padx=24, pady=(16, 8))
        tk.Label(marco_sonidos, text="Sonidos:", **estilo).pack(anchor="w")

        lista_frame = tk.Frame(marco_sonidos, bg="#2a3142")
        lista_frame.pack(fill="both", expand=True, pady=(4, 8))
        self.lista = tk.Listbox(
            lista_frame,
            font=("Segoe UI", 11),
            bg="#2a3142",
            fg="#e8ecf4",
            selectbackground="#3d7ea6",
            selectforeground="#ffffff",
            activestyle="none",
            relief="flat",
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(lista_frame, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=scroll.set)
        self.lista.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        botones_sonido = tk.Frame(marco_sonidos, bg="#1a1f2e")
        botones_sonido.pack(fill="x")
        for texto, cmd in (
            ("Agregar sonido", self._agregar_sonido),
            ("Probar", self._probar_sonido),
            ("Eliminar", self._eliminar_sonido),
        ):
            tk.Button(
                botones_sonido,
                text=texto,
                command=cmd,
                bg="#2f3b52",
                fg="#e8ecf4",
                activebackground="#3a4863",
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=6,
            ).pack(side="left", padx=(0 if texto == "Agregar sonido" else 8, 0))

        self.btn_despertar = tk.Button(
            self,
            text="¡DESPERTAR!",
            command=self._despertar,
            font=("Segoe UI", 16, "bold"),
            bg="#c45c26",
            fg="#ffffff",
            activebackground="#d66a30",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            pady=14,
        )
        self.btn_despertar.pack(fill="x", padx=24, pady=(8, 12))

        marco_startup = tk.Frame(self, bg="#1a1f2e")
        marco_startup.pack(fill="x", padx=24, pady=(0, 16))
        tk.Button(
            marco_startup,
            text="Agregar al inicio de Windows",
            command=self._agregar_startup,
            bg="#2f3b52",
            fg="#e8ecf4",
            activebackground="#3a4863",
            relief="flat",
            padx=8,
            pady=5,
        ).pack(side="left")
        tk.Button(
            marco_startup,
            text="Quitar del inicio",
            command=self._quitar_startup,
            bg="#2f3b52",
            fg="#e8ecf4",
            activebackground="#3a4863",
            relief="flat",
            padx=8,
            pady=5,
        ).pack(side="left", padx=(8, 0))

        self.estado = tk.Label(
            self,
            text="Listo. Esperando alarmas…",
            font=("Segoe UI", 9),
            bg="#1a1f2e",
            fg="#8b95a8",
        )
        self.estado.pack(pady=(0, 12))

    def _copiar_mi_ip(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.mi_ip)
        self.estado.config(text=f"IP copiada: {self.mi_ip}")

    def _sonido_seleccionado(self) -> Path | None:
        sel = self.lista.curselection()
        if not sel:
            return None
        return SONIDOS_DIR / self.lista.get(sel[0])

    def _refrescar_lista(self) -> None:
        actual = None
        sel = self.lista.curselection()
        if sel:
            actual = self.lista.get(sel[0])
        self.lista.delete(0, tk.END)
        for p in listar_sonidos():
            self.lista.insert(tk.END, p.name)
        if actual:
            for i, nombre in enumerate(self.lista.get(0, tk.END)):
                if nombre == actual:
                    self.lista.selection_set(i)
                    break

    def _agregar_sonido(self) -> None:
        rutas = filedialog.askopenfilenames(
            title="Elegir sonidos",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.ogg *.wma *.m4a *.aac"),
                ("Todos", "*.*"),
            ],
        )
        if not rutas:
            return
        for ruta in rutas:
            origen = Path(ruta)
            if origen.suffix.lower() not in EXTENSIONES:
                messagebox.showwarning("Formato", f"No soportado: {origen.name}")
                continue
            destino = SONIDOS_DIR / origen.name
            if destino.exists():
                base, ext = origen.stem, origen.suffix
                i = 1
                while destino.exists():
                    destino = SONIDOS_DIR / f"{base}_{i}{ext}"
                    i += 1
            shutil.copy2(origen, destino)
        self._refrescar_lista()
        self.estado.config(text="Sonido(s) agregados.")

    def _eliminar_sonido(self) -> None:
        ruta = self._sonido_seleccionado()
        if not ruta:
            messagebox.showinfo("Sonidos", "Selecciona un sonido primero.")
            return
        if messagebox.askyesno("Eliminar", f"¿Eliminar {ruta.name}?"):
            ruta.unlink(missing_ok=True)
            self._refrescar_lista()

    def _probar_sonido(self) -> None:
        ruta = self._sonido_seleccionado()
        if not ruta:
            messagebox.showinfo("Probar", "Selecciona un sonido primero.")
            return

        def trabajo() -> None:
            try:
                reproducir(ruta, esperar=False)
                self.after(
                    0, lambda: self.estado.config(text=f"Reproduciendo: {ruta.name}")
                )
            except Exception as exc:  # noqa: BLE001
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"No se pudo reproducir:\n{exc}"
                    ),
                )

        threading.Thread(target=trabajo, daemon=True).start()

    def _despertar(self) -> None:
        ruta = self._sonido_seleccionado()
        if not ruta:
            messagebox.showinfo("Despertar", "Selecciona un sonido primero.")
            return
        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showinfo("Despertar", "Escribe la IP del compañero.")
            return

        self.config_data["ip_companero"] = ip
        self.config_data["puerto"] = self.puerto
        guardar_config(self.config_data)

        self.btn_despertar.config(state="disabled")
        self.estado.config(text=f"Enviando {ruta.name} a {ip}…")

        def trabajo() -> None:
            try:
                enviar_sonido(ip, self.puerto, ruta)
                self.after(
                    0,
                    lambda: self.estado.config(text=f"¡Enviado! {ruta.name} → {ip}"),
                )
            except Exception as exc:  # noqa: BLE001
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "No se pudo despertar",
                        "Revisa que el compañero tenga el programa abierto\n"
                        f"y que la IP sea correcta.\n\n{exc}",
                    ),
                )
                self.after(0, lambda: self.estado.config(text="Error al enviar."))
            finally:
                self.after(0, lambda: self.btn_despertar.config(state="normal"))

        threading.Thread(target=trabajo, daemon=True).start()

    def _agregar_startup(self) -> None:
        try:
            destino = crear_acceso_startup()
            messagebox.showinfo(
                "Inicio de Windows",
                f"Listo. Se abrirá al iniciar sesión:\n{destino}",
            )
            self.estado.config(text="Agregado al inicio de Windows.")
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo crear el acceso:\n{exc}")

    def _quitar_startup(self) -> None:
        if quitar_acceso_startup():
            messagebox.showinfo("Inicio de Windows", "Quitado del inicio.")
            self.estado.config(text="Quitado del inicio de Windows.")
        else:
            messagebox.showinfo(
                "Inicio de Windows", "No estaba agregado al inicio."
            )

    def _al_cerrar(self) -> None:
        self.config_data["ip_companero"] = self.ip_var.get().strip()
        self.config_data["puerto"] = self.puerto
        guardar_config(self.config_data)
        self.stop_event.set()
        _mci(f"close {ALIAS_AUDIO}")
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
