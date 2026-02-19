# HashCash GUI Miner (HCC)

A small cross-platform GUI wrapper around the **HCC CLI Miner**. It launches the CLI miner, shows live output, supports profiles, and can automatically download the newest CLI miner release for your OS/CPU.

## What this app does

- Starts/stops the HCC CLI miner with the options you choose
- Shows the miner output in a log window
- **Auto-downloads** the latest CLI miner from GitHub Releases (optional)
- Saves and loads **profiles** (URL, key, workers, etc.)
- Supports **EXTREME mode** (via `-extreme` flag)

> The GUI does **not** implement PoW itself. It is a wrapper for the official CLI miner.

---

## Usage

Click **Mine**. If **Auto-download latest miner** is enabled, the GUI will download the newest compatible CLI miner automatically.

### Fields / options

- **Faucet API base URL**: Useful if someone runs a compatible HCC faucet backend (or an HCC clone).
- **Miner executable (optional)**: Only needed if you want to use a custom binary instead of the latest release.
  - If left empty and auto-download is enabled, the GUI uses the downloaded binary.
  - If left empty and auto-download is disabled, the GUI will try to find a local binary next to the GUI.
- **Private key**: Required. Get it from the Web UI.
- **Workers**: Number of threads/cores to use. `0` = auto-detect CPU cores.
- **EXTREME mode**: Uses `/challenge_extreme` via the CLI miner. No cooldown, higher difficulty, separate server-side daily cap.
- **Profiles**: Save and load multiple configurations.

---

## Build from source

This GUI is written in Python (Tkinter). For distributing a standalone app/binary we recommend **PyInstaller**.

### Requirements

- Python 3.10+ (3.11 recommended)
- `pip`
- Tkinter
  - **Windows/macOS**: Tkinter is typically included with Python.
  - **Linux**: install your distro’s Tk package (e.g. `python3-tk`).

Install dependencies:

```bash
pip install -r requirements.txt
```

If you don’t have a `requirements.txt` yet, you need at least:

```txt
requests
```

---

## Build standalone binaries with PyInstaller

> Note: Python GUI apps are generally built **on the target OS** (or in CI runners). True cross-compiling is uncommon.

### macOS (Apple Silicon / arm64)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller

pyinstaller --noconsole --onefile --name hcc_gui_miner_mac_arm64_0.4.0 hcc_gui_miner.py
```

Output:

- `dist/hcc_gui_miner_mac_arm64_0.4.0`

### Windows (amd64)

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller

pyinstaller --noconsole --onefile --name hcc_gui_miner_win_amd64_0.4.0.exe hcc_gui_miner.py
```

Output:

- `dist\hcc_gui_miner_win_amd64_0.4.0.exe`

### Linux (amd64)

On Linux desktop systems:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller

pyinstaller --onefile --name hcc_gui_miner_linux_amd64_0.4.0 hcc_gui_miner.py
```

**Compatibility tip:** For wide compatibility across Linux distributions, build inside an older base image (e.g. Ubuntu 20.04) using Docker:

```bash
docker run --rm -v "$PWD:/src" -w /src ubuntu:20.04 bash -lc '
  apt-get update &&
  apt-get install -y python3 python3-venv python3-pip tk-dev &&
  python3 -m venv .venv &&
  . .venv/bin/activate &&
  pip install -r requirements.txt pyinstaller &&
  pyinstaller --onefile --name hcc_gui_miner_linux_amd64_0.4.0 hcc_gui_miner.py
'
```

---

## Releases / Auto-download

When **Auto-download latest miner** is enabled, the GUI downloads the newest CLI miner from:

- GitHub repo: `Hashcash-PoW-Faucet/HCC-CLI-Miner`

It selects the correct asset for your OS/architecture and caches it in your per-user app data folder.

---

## License

MIT

