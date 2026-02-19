import tkinter as tk
import tkinter.font as tkFont
import subprocess
import threading
import queue
import json
import re
import os
import requests
from tkinter import filedialog
import platform
import stat
import hashlib
import struct
import shutil

config_file = 'dist/hcc_miner_config.json'

# Global reference to the mining process
mining_process = None

# Global flag to indicate intentional termination
stop_requested = False

default_config = {
    "Profile": {
        "Default": {
            "api_url": "https://hashcash-pow-faucet.dynv6.net/api",
            "miner_path": "",
            "private_key": "",
            "threads": "0",
            "auto_download": True,
            "extreme": False
        }
    }
}


def strip_ansi_codes(text):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


def save_config(profile_name):
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        config = {"Profile": {}}

    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    config["Profile"][profile_name] = {
        'api_url': api_url_entry.get(),
        'miner_path': miner_path_entry.get(),
        'private_key': private_key_entry.get(),
        'threads': threads_entry.get(),
        'auto_download': bool(auto_download_var.get()),
        'extreme': bool(extreme_mode_var.get())
    }

    with open(config_file, 'w') as file:
        json.dump(config, file, indent=4)


def save_config_with_name():
    profile_name = profile_name_entry.get()
    if profile_name:
        save_config(profile_name)
        update_profile_options()
        selected_profile_name.set(profile_name)
    else:
        print("Profile name cannot be empty")


def load_config(profile_name):
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        config = default_config
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as file:
            json.dump(config, file, indent=4)

    profile = config["Profile"].get(profile_name, default_config["Profile"]["Default"])

    api_url_entry.delete(0, tk.END)
    api_url_entry.insert(0, profile.get('api_url', ''))

    miner_path_entry.delete(0, tk.END)
    miner_path_entry.insert(0, profile.get('miner_path', ''))
    if not miner_path_entry.get().strip():
        dmp = default_miner_path()
        if dmp:
            miner_path_entry.insert(0, dmp)

    private_key_entry.delete(0, tk.END)
    private_key_entry.insert(0, profile.get('private_key', ''))

    threads_entry.delete(0, tk.END)
    threads_entry.insert(0, profile.get('threads', '0'))

    auto_download_var.set(bool(profile.get('auto_download', True)))
    extreme_mode_var.set(bool(profile.get('extreme', False)))


def load_profile_names():
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        config = default_config

    if "Profile" in config:
        return list(config["Profile"].keys())
    else:
        return ["Default"]

def execute_command(cmd, output_queue):
    global mining_process, stop_requested
    try:
        startupinfo = None
        if os.name == 'nt':  # If running on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        mining_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                          startupinfo=startupinfo)

        # Continuously read output
        for line in mining_process.stdout:
            if line:
                output_queue.put(line)

        return_code = mining_process.wait()
        if return_code and not stop_requested:
            output_queue.put(f"Process exited with return code {return_code}")

    except subprocess.CalledProcessError as e:
        output_queue.put(f"Exception: {str(e)}")
    finally:
        stop_requested = False
        update_mining_status("Status: Not Mining")


def update_output_textbox(output_queue):
    try:
        line = output_queue.get_nowait()
        clean_line = strip_ansi_codes(line)
        output_textbox.insert(tk.END, clean_line)
        output_textbox.see(tk.END)
    except queue.Empty:
        pass
    finally:
        root.after(100, update_output_textbox, output_queue)


def update_mining_status(message):
    if isinstance(message, bool):
        message = "Status: Mining" if message else "Status: Not Mining"
    fg_color = "red" if "Error:" in message or "Exception:" in message or "Process exited" in message else "green"
    status_label.config(text=message, fg=fg_color)


def default_miner_path():
    """Default miner path for manual mode. If a local miner is in the same folder, prefer it; else empty."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Prefer a simple local name if user placed it next to the GUI.
        candidates = ['hhc_miner.exe', 'hhc_miner', 'faucet_miner.exe', 'faucet_miner']
        for name in candidates:
            candidate = os.path.join(script_dir, name)
            if os.path.exists(candidate):
                return candidate
    except Exception:
        pass
    # Empty means: rely on auto-download or PATH.
    return ''


def resolve_miner_exe():
    """Resolve miner path from UI. If empty, use default. If relative, try script dir first, then PATH."""
    p = miner_path_entry.get().strip()
    if not p:
        p = default_miner_path() or 'hhc_miner.exe' if os.name == 'nt' else 'hhc_miner'

    # If relative, try script directory.
    if not os.path.isabs(p):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.join(script_dir, p)
            if os.path.exists(candidate):
                return candidate
        except Exception:
            pass

        # Try PATH
        which = shutil.which(p)
        if which:
            return which

    return p


def browse_miner_path():
    initial = miner_path_entry.get().strip() or default_miner_path()
    # If initial is a file, use its directory
    init_dir = None
    try:
        if os.path.isabs(initial):
            init_dir = os.path.dirname(initial)
    except Exception:
        init_dir = None

    path = filedialog.askopenfilename(
        title='Select miner binary',
        initialdir=init_dir,
        filetypes=[('Executable', '*.exe'), ('All files', '*.*')] if os.name == 'nt' else [('All files', '*')]
    )
    if path:
        miner_path_entry.delete(0, tk.END)
        miner_path_entry.insert(0, path)


def toggle_show_key():
    if show_key_var.get():
        private_key_entry.config(show='')
    else:
        private_key_entry.config(show='*')


GITHUB_OWNER = "Hashcash-PoW-Faucet"
GITHUB_REPO = "HCC-CLI-Miner"


def app_data_dir():
    """Cross-platform per-user data dir."""
    # Windows
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(base, 'HashcashMiner')
    # macOS
    if platform.system().lower() == 'darwin':
        return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'HashcashMiner')
    # Linux/Unix
    xdg = os.environ.get('XDG_DATA_HOME')
    if xdg:
        return os.path.join(xdg, 'hashcashminer')
    return os.path.join(os.path.expanduser('~'), '.local', 'share', 'hashcashminer')


def detect_os_arch():
    """Map current OS/arch to the release asset naming scheme."""
    sys = platform.system().lower()
    mach = platform.machine().lower()

    # OS mapping
    if sys.startswith('win'):
        os_id = 'win'
        ext = '.exe'
    elif sys == 'darwin':
        os_id = 'mac'
        ext = ''
    else:
        os_id = 'linux'
        ext = ''

    # Arch mapping
    # Prefer pointer size to detect 32-bit python on x86
    ptr_bits = struct.calcsize('P') * 8

    if mach in ('x86_64', 'amd64'):
        arch = 'amd64' if ptr_bits == 64 else '386'
    elif mach in ('i386', 'i686', 'x86'):
        arch = '386'
    elif mach in ('arm64', 'aarch64'):
        arch = 'arm64'
    elif mach.startswith('armv6') or mach == 'armv6l':
        arch = 'armv6'
    elif mach.startswith('armv7') or mach == 'armv7l':
        arch = 'armv7'
    else:
        raise RuntimeError(f"Unsupported architecture: {platform.machine()}")

    return os_id, arch, ext


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def github_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def find_asset(release_json, asset_name):
    for a in release_json.get('assets', []):
        if a.get('name') == asset_name:
            return a
    return None


def ensure_latest_miner(log_fn):
    """Download the latest miner binary for this OS/arch into app data dir and return its path."""
    rel = github_latest_release()
    tag = rel.get('tag_name', '')
    version = tag[1:] if tag.startswith('v') else tag

    os_id, arch, ext = detect_os_arch()
    asset_name = f"hhc_miner_{os_id}_{arch}_{version}{ext}"

    asset = find_asset(rel, asset_name)
    if not asset:
        raise RuntimeError(f"No matching asset in latest release: {asset_name}")

    download_url = asset.get('browser_download_url')
    if not download_url:
        raise RuntimeError('Missing download URL for asset')

    base = app_data_dir()
    bin_dir = os.path.join(base, 'bin', tag)
    os.makedirs(bin_dir, exist_ok=True)
    local_path = os.path.join(bin_dir, asset_name)

    if os.path.exists(local_path):
        try:
            local_size = os.path.getsize(local_path)
        except Exception:
            local_size = None

        expected_size = asset.get('size')

        # If the cached file size doesn't match the GitHub asset size, re-download.
        if expected_size is not None and local_size is not None and int(local_size) != int(expected_size):
            log_fn(f"[!] Cached miner size mismatch (local={local_size} bytes, expected={expected_size} bytes). Re-downloading...\n")
        else:
            # Log SHA256 for troubleshooting (compare with release notes)
            try:
                h = sha256_file(local_path)
                log_fn(f"[*] Cached miner SHA256: {h}\n")
            except Exception:
                pass
            log_fn(f"[*] Using cached miner: {local_path}\n")
            return local_path

    log_fn(f"[*] Downloading latest miner: {asset_name}\n")
    r = requests.get(download_url, timeout=60)
    r.raise_for_status()

    tmp = local_path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(r.content)
    os.replace(tmp, local_path)

    # Make executable on unix
    if ext == '':
        st = os.stat(local_path)
        os.chmod(local_path, st.st_mode | stat.S_IEXEC)

    try:
        h = sha256_file(local_path)
        log_fn(f"[*] Downloaded miner SHA256: {h}\n")
    except Exception:
        pass

    log_fn(f"[+] Miner ready: {local_path}\n")
    return local_path


def start_mining():
    global mining_process

    # Disable the "Mine" button to prevent re-clicking
    mine_button.config(state=tk.DISABLED)

    if mining_process is None or mining_process.poll() is not None:
        # Clear the output textbox only if mining is not already in progress
        output_textbox.delete("1.0", tk.END)

    api_url = api_url_entry.get().strip()
    private_key = private_key_entry.get().strip()
    threads = threads_entry.get().strip() or "0"

    if not private_key:
        output_textbox.insert(tk.END, "ERROR: Please enter your private key.\n")
        update_mining_status("Error: Missing private key")
        mine_button.config(state=tk.NORMAL)
        return

    # Auto-download latest miner if enabled and no explicit path was set
    if auto_download_var.get() and not miner_path_entry.get().strip():
        try:
            def _log(msg):
                output_textbox.insert(tk.END, msg)
                output_textbox.see(tk.END)
            path = ensure_latest_miner(_log)
            miner_path_entry.delete(0, tk.END)
            miner_path_entry.insert(0, path)
        except Exception as e:
            output_textbox.insert(tk.END, f"[!] Auto-download failed: {e}\n")
            output_textbox.see(tk.END)

    miner_exe = resolve_miner_exe()
    # If it's an absolute path and doesn't exist, show a friendly error.
    if os.path.isabs(miner_exe) and not os.path.exists(miner_exe):
        output_textbox.insert(tk.END, f"ERROR: Miner executable not found: {miner_exe}\n")
        update_mining_status("Error: Missing miner executable")
        mine_button.config(state=tk.NORMAL)
        return

    # IMPORTANT (Go flag parsing): pass bool/int flags using = syntax.
    # Do NOT pass bool flags as `-progress true` because the `true` becomes a positional arg
    # and Go's flag parser may stop parsing further flags (e.g. `-extreme`).
    command = [
        miner_exe,
        "-url", api_url,
        "-key", private_key,
        "-workers", threads,
        "-progress=true",
        "-progress-interval=2",
    ]
    if extreme_mode_var.get():
        command.append("-extreme")

    # Debug: Log mode + command into the GUI output (so we can verify flags are passed)
#    mode = "EXTREME" if extreme_mode_var.get() else "normal"
#    output_textbox.insert(tk.END, f"[*] GUI mode checkbox: {mode}\n")
#    output_textbox.insert(tk.END, f"[*] Executing: {' '.join(command)}\n")
#    output_textbox.see(tk.END)

    print("Executing:", " ".join(command))

    # Start the command in a new thread
    output_queue = queue.Queue()
    threading.Thread(target=execute_command, args=(command, output_queue), daemon=True).start()
    update_output_textbox(output_queue)
    update_mining_status("Status: Mining")


def best_effort_cancel_pow():
    try:
        api_url = api_url_entry.get().strip().rstrip('/')
        private_key = private_key_entry.get().strip()
        if not api_url or not private_key:
            return
        r = requests.post(f"{api_url}/cancel_pow", headers={"Authorization": f"Bearer {private_key}"}, timeout=3)
        # ignore response body; best-effort only
        _ = r.status_code
    except Exception:
        pass


def stop_mining():
    global mining_process, stop_requested
    stop_requested = True  # Set the flag when stopping
    if mining_process:
        best_effort_cancel_pow()
        mining_process.terminate()
        mining_process.wait(5)
        mining_process = None
        output_textbox.insert(tk.END, "Mining stopped.\n")
    update_mining_status("Status: Not Mining")
    mine_button.config(state=tk.NORMAL)


def on_closing():
    global mining_process
    if mining_process:
        # Terminate the process using its PID
        try:
            mining_process.terminate()
            mining_process.wait(5)  # Wait for 5 seconds to allow process to terminate
        except Exception as e:
            print("Error terminating process:", e)
    root.destroy()  # Close the GUI


def update_profile_options():
    profile_names = load_profile_names()

    profile_option_menu['menu'].delete(0, 'end')

    for profile_name in profile_names:
        profile_option_menu['menu'].add_command(label=profile_name,
                                                command=lambda value=profile_name: selected_profile_name.set(value))

    if profile_names:
        selected_profile_name.set(profile_names[0])
    else:
        selected_profile_name.set("Default")


# Create the main window
root = tk.Tk()
root.title("Hashcash Credits GUI miner")
# Give the window a reasonable minimum size so the log is usable
root.minsize(900, 600)
# Make the main entry column expand, but also allow full-width widgets spanning all columns
root.grid_columnconfigure(0, weight=0)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=0)

# Customizing font
custom_font = tkFont.Font(family="Helvetica", size=10, weight="bold")

# Create and place labels, entry widgets, and the output textbox
tk.Label(root, text="Faucet API base URL:").grid(row=0, column=0, sticky='w')
api_url_entry = tk.Entry(root, width=50)
api_url_entry.grid(row=0, column=1, sticky='we')

# Miner executable path (auto-detects script folder by default)
tk.Label(root, text="Miner executable (optional):").grid(row=1, column=0, sticky='w')
miner_path_entry = tk.Entry(root, width=50)
miner_path_entry.grid(row=1, column=1, sticky='we')
if not miner_path_entry.get().strip():
    dmp = default_miner_path()
    if dmp:
        miner_path_entry.insert(0, dmp)
browse_button = tk.Button(root, text="Browse...", command=browse_miner_path, width=12)
browse_button.grid(row=1, column=2, padx=6)

# Private key + show toggle
tk.Label(root, text="Private key (from the web faucet):").grid(row=2, column=0, sticky='w')
private_key_entry = tk.Entry(root, width=50, show="*")
private_key_entry.grid(row=2, column=1, sticky='we')
show_key_var = tk.BooleanVar(value=False)
show_key_cb = tk.Checkbutton(root, text="Show key", variable=show_key_var, command=toggle_show_key)
show_key_cb.grid(row=2, column=2, padx=6)

# Workers
tk.Label(root, text="Workers (0 = auto-detect CPU cores):").grid(row=3, column=0, sticky='w')
threads_entry = tk.Entry(root, width=5)
threads_entry.grid(row=3, column=1, sticky='w')

# Auto-download checkbox
auto_download_var = tk.BooleanVar(value=True)
auto_download_cb = tk.Checkbutton(root, text="Auto-download latest miner (GitHub Releases)", variable=auto_download_var)
auto_download_cb.grid(row=4, column=0, columnspan=2, sticky='w')

# Extreme mode checkbox
extreme_mode_var = tk.BooleanVar(value=False)
extreme_mode_cb = tk.Checkbutton(root, text="EXTREME mode (higher difficulty but no cooldown and higher daily cap)", variable=extreme_mode_var)
extreme_mode_cb.grid(row=5, column=0, columnspan=2, sticky='w')

tk.Label(root, text="Profile name:").grid(row=11)
profile_name_entry = tk.Entry(root, width=20)
profile_name_entry.grid(row=12, column=0)

save_as_button = tk.Button(root, text="Save profile", command=save_config_with_name, width=20)
save_as_button.grid(row=14, column=0)

selected_profile_name = tk.StringVar(root)

profile_names = load_profile_names()

if profile_names:
    selected_profile_name.set(profile_names[0])
else:
    selected_profile_name.set("Default")

tk.Label(root, text="Select existing profile:").grid(row=11, column=1)

profile_option_menu = tk.OptionMenu(root, selected_profile_name, *profile_names)
profile_option_menu.grid(row=12, column=1)


def profile_selected(*args):
    load_config(selected_profile_name.get())


selected_profile_name.trace("w", profile_selected)


output_textbox = tk.Text(root, bg='black', fg='white')
# Full width (all columns) and expandable
output_textbox.grid(row=10, column=0, columnspan=3, sticky='nsew', padx=6, pady=6)

# Allow the log box row to expand when resizing the window
root.grid_rowconfigure(10, weight=1)

# Create and place the "mine" button with custom color and font
mine_button = tk.Button(root, text="Mine", command=start_mining, bg="green", font=custom_font, height=2)
mine_button.grid(row=9, column=0, columnspan=2, sticky='we', padx=6, pady=6)

# Create and place the "Stop" button with custom color and font
stop_button = tk.Button(root, text="Stop", command=stop_mining, bg="red", font=custom_font, height=2)
stop_button.grid(row=9, column=2, columnspan=1, sticky='we', padx=6, pady=6)

# Status label
status_label = tk.Label(root, text="Status: Not Mining", font=custom_font)
status_label.grid(row=15, column=0, columnspan=3)

# Load the configuration at startup
load_config(selected_profile_name.get())

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start the GUI event loop
root.mainloop()
