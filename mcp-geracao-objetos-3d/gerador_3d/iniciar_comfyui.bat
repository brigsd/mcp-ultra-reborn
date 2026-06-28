@echo off
echo Iniciando ComfyUI com configuracao Low-VRAM para TRELLIS.2...
cd /d D:\ComfyUI
call venv\Scripts\activate
python main.py --lowvram --force-fp16
pause
