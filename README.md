# Despertador de Emas

Programa simple para despertar al compañero del escritorio de al lado: eliges un sonido, pulsas el botón y suena en su PC (y al revés).

## Descargar

[![Descargar .exe](https://img.shields.io/badge/Descargar-DespertadorEmas.exe-2ea44f?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Jaime-SC/despertador-de-emas/raw/master/bin/DespertadorEmas.exe)

1. Descarga [**DespertadorEmas.exe**](https://github.com/Jaime-SC/despertador-de-emas/raw/master/bin/DespertadorEmas.exe).
2. Ejecútalo (no hace falta instalar Python).
3. Copia tu IP (botón **Copiar IP**) y pásasela al compañero.
4. Pega la IP de él en **IP del compañero**.
5. Agrega sonidos, elige uno y pulsa **¡DESPERTAR!**

> Si Windows SmartScreen avisa la primera vez: *Más información* → *Ejecutar de todas formas* (el programa no está firmado digitalmente).

## Requisitos (solo si usas el código fuente)

- Windows
- Python 3 (ya viene con `tkinter`)

No hace falta instalar paquetes extra.

## Cómo usarlo desde el código fuente

1. Descarga el ZIP del repo (**Code → Download ZIP**) y descomprímelo.
2. Ejecuta `iniciar_sin_consola.vbs` (o `iniciar.bat`).
3. Sigue los mismos pasos de IP / sonidos / despertar.
4. Opcional: **Agregar al inicio de Windows** para que abra solo al encender el PC.

Para regenerar el `.exe`: `build_exe.bat` (necesita `pip install pyinstaller`).

## ¿Hay que tener los mismos sonidos?

**No.** Al despertar, el archivo de audio se envía por la red y se reproduce en el otro equipo. Solo quien lanza la alarma necesita tener el sonido.

## Nota de red

Ambos PCs deben estar en la misma red y con el programa abierto. Si Windows pregunta por el firewall, acepta para redes privadas.
