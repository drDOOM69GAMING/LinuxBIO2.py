<img width="600" height="550" alt="Screenshot from 2026-04-19 08-46-15" src="https://github.com/user-attachments/assets/b2e4cb52-16fc-412a-99c4-449ca07f3083" />


sudo apt install xdotool

# Resident Evil 2 Linux Modder

A PyQt5-based GUI tool for downloading, modding, and launching Resident Evil 2 on Linux using Wine/Proton.

## Features

- **Auto Download**: Downloads the RE2 Japanese PC (Source Next) ISO and Bio2_mod.zip, extracts the ISO, applies the mod, and creates a launch script
- **Mod Only**: Apply the Bio2_mod.zip to an existing game folder
- **Reset Proton Prefix**: Rebuild the Wine/Proton prefix if the game stops working
- **Automatic Launch Script**: Creates a `run_proton.sh` script that auto-detects Proton-GE
- **DLL Overrides**: Pre-configured for optimal compatibility (DXVK, DirectDraw, DirectInput, XAudio2)

## Requirements

### System Dependencies

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-pyqt5 p7zip-full curl wget
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip python3-pyqt5 p7zip
```

**Arch Linux:**
```bash
sudo pacman -S python python-pyqt5 p7zip
```

### Python Dependencies

```bash
pip install PyQt5 requests
```

### Additional Requirements

- **Proton-GE** (recommended for best compatibility):
  Install via [ProtonUp-Qt](https://davidotek.github.io/protonup-qt/)

- **Steam** with Resident Evil 2 installed (optional, for Proton-GE detection)

## Installation

1. Download or clone this repository
2. Install the required dependencies
3. Run the modder:
   ```bash
   python3 LinuxBIO2.py
   ```

Or make it executable:
```bash
chmod +x LinuxBIO2.py
./LinuxBIO2.py
```

## Usage

### Option 1: Auto Download (Recommended for New Users)

1. Click **A/D (Auto Download)**
2. The tool will:
   - Download the RE2 ISO from Archive.org
   - Download Bio2_mod.zip from GitHub
   - Extract the ISO to your Desktop
   - Apply the mod
   - Create a savedata folder
   - Delete the downloaded archives
   - Write the `run_proton.sh` launch script
3. Run the game with: `bash run_proton.sh`

### Option 2: Mod Only (If You Already Extracted the ISO)

1. Manually extract the RE2 ISO to your Desktop
2. Rename the folder to: `biohazard-2-apan-source-next`
3. Click **Auto - Apply Mod Only**
4. The mod will be applied to your existing folder
5. Run the game with: `bash run_proton.sh`

### Option 3: Reset Proton Prefix

If the game won't launch, shows black bars are missing, or you see startup errors:

1. Click **Reset Proton Prefix**
2. The tool will delete and rebuild the `proton_pfx` folder
3. Rewrite the `run_proton.sh` script
4. Try launching again

## Launching the Game

After setup, run the game from the game folder:

```bash
cd ~/Desktop/biohazard-2-apan-source-next
bash run_proton.sh
```

The script auto-detects:
- Proton-GE in `~/.steam-root/compatibilitytools.d/`
- Falls back to system Wine if Proton-GE not found
- Sets correct environment variables for DXVK and DLL overrides

## First Time Configuration

1. Run `bash run_proton.sh`
2. The configuration window will appear
3. Click **BEST**
4. Untick **Texture Filtering**
5. Click **OK**

## Controller Setup (In-Game)

1. Press **SELECT** in-game to open controller config
2. Set aim to the front right trigger (R2 / RT)

## The Black Side Bars

The black side bars are **intentional**. Classic REbirth enforces the correct 4:3 aspect ratio.

If the bars are missing, the Classic REbirth ddraw hook is not loading. Use **Reset Proton Prefix** to fix this.

## Xalia / "Invalid window handle" Errors

These messages are harmless. Xalia is a gamepad accessibility tool built into Proton-GE. It runs alongside every game and its handle errors are normal - they have no effect on gameplay.

## Slow Texture Loading (First Playthrough)

On the first playthrough, DXVK compiles shaders on the fly. This causes one-time hitches when opening doors or picking up items. After each transition is triggered once, the shader is cached and subsequent loads are smooth. This is normal.

## Required Game Folder Name

The game folder must be named exactly:
```
biohazard-2-apan-source-next
```

## DLL Overrides Explained

The modder configures these DLL overrides for optimal compatibility:

| DLL | Purpose |
|-----|---------|
| `d3d9` + `d3dcompiler_47` | DXVK handles D3D9 for HD textures |
| `ddraw` | Classic REbirth core renderer (keeps 4:3 bars) |
| `dinput8` | HD texture loader injection (ASI) |
| `dsound` + `libwebp` | TeamX HD mod audio/media |
| `xaudio2_9` | Classic REbirth audio subsystem |

## Troubleshooting

### "7z not found"
```bash
sudo apt install p7zip-full   # Debian/Ubuntu
sudo dnf install p7zip       # Fedora
sudo pacman -S p7zip         # Arch Linux
```

### Game won't launch
Use **Reset Proton Prefix** to rebuild the Wine prefix.

### Black bars missing
The ddraw hook isn't loading. Use **Reset Proton Prefix**.

### Mod download fails
Check your internet connection. The mod is hosted on GitHub.

### ISO download fails
The ISO is hosted on Archive.org. Check your connection.

## Game Info

- **Game**: Resident Evil 2 (1998)
- **Version**: Japanese PC (Source Next)
- **Mod**: Bio2_mod (Classic REbirth + HD mods)
- **Default Folder**: `biohazard-2-apan-source-next`

## License

MIT License - Copyright (c) 2024 drDOOM69GAMING

## Credits

- Bio2_mod by TheOtherGuy66
- Classic REbirth team
- DXVK developers
- Proton-GE contributors
