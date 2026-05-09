# ◈ Card Scanner Overlay

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![EasyOCR](https://img.shields.io/badge/OCR-EasyOCR-green.svg)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-orange.svg)

An intelligent automation assistant featuring a semi-transparent, Always-on-Top interface. Designed to monitor specific screen regions, identify text via OCR, and execute automated keyboard actions. Perfect for card games or systems requiring fast reactions to visual elements.

## ✨ Key Features

- **Chroma Key Overlay**: A 100% "hollow" capture window (transparent background) that allows the OCR engine to read the original screen perfectly without UI interference.
- **Multi-Pass OCR**: An optimized system that first identifies the "Rank" to narrow down the "Name" search to specific buckets, saving CPU/GPU resources.
- **Telegram Integration**: Automatic notifications with interactive Inline Keyboard buttons to confirm collections or report OCR misreads remotely.
- **Anti-Spam & Cooldown**: Smart logic to prevent duplicate clicks and notification spam for the same target.
- **Human Input Detection**: Automatically pauses automation when mouse movement or keystrokes are detected to avoid interfering with manual control.
- **JSON Persistence**: Automatically saves collected items to a local database to ignore them in future sessions.

## 🛠️ Technology Stack

- **EasyOCR**: Optical Character Recognition with CUDA (GPU) acceleration support.
- **Tkinter**: Lightweight, customized GUI for the overlay.
- **MSS**: High-performance screen capture library.
- **PyAutoGUI & Pynput**: Peripheral simulation and global input monitoring.
- **Requests**: Communication with the Telegram Bot API.

## 🚀 Getting Started

1. **Requirements**: Python 3.11 or higher.
2. **Installation**:
   ```bash
   pip install -r requirements.txt

## ⚠️ Language Dependency (OCR Localization)

This tool is currently configured to work with the **Portuguese (PT-BR)** version of the game. 

Since the automation relies on Optical Character Recognition (OCR) to match names and ranks:
- **String Matching:** The `TARGETS_POR_RANK` dictionary uses Portuguese terms as keys and values.
- **Game Language:** If your game is set to English or any other language, the OCR will not find a match.

### How to Port to Other Languages:
If you wish to use this in a different language:
1. Create a new branch.
2. Update the keys in `TARGETS_POR_RANK` to match the exact text displayed in your game's UI.
3. Update the `_normalizar` function if your language uses special characters not covered by the current logic.
