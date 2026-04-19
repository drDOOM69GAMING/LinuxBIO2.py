#!/usr/bin/env -S python3 -W ignore
import os, sys, subprocess, shutil, zipfile, webbrowser, requests, threading
from queue import Queue
from PyQt5 import QtWidgets, QtGui, QtCore

def xdg_desktop():
    try:
        out = subprocess.check_output(["xdg-user-dir","DESKTOP"],timeout=3).decode().strip()
        if out and os.path.isdir(out): return out
    except: pass
    p = os.path.join(os.path.expanduser("~"),"Desktop"); os.makedirs(p,exist_ok=True); return p

def xdg_download():
    try:
        out = subprocess.check_output(["xdg-user-dir","DOWNLOAD"],timeout=3).decode().strip()
        if out and os.path.isdir(out): return out
    except: pass
    p = os.path.join(os.path.expanduser("~"),"Downloads"); os.makedirs(p,exist_ok=True); return p

def cache_dir():
    d = os.path.join(os.path.expanduser("~"),".cache","re_aio_modder"); os.makedirs(d,exist_ok=True); return d

GAME_CONFIGS = {
    "re2":{
        "title":"Resident Evil 2","folder":"biohazard-2-apan-source-next",
        "iso_url":"iso-url-goes-here",
        "iso_name":"biohazard-2-apan-source-next.iso",
        "mod_url":"https://github.com/TheOtherGuy66-source/Resident_Evil_Python_Builder_kit/releases/download/amd/Bio2_mod.zip",
        "mod_name":"Bio2_mod.zip","target_subdir":"data",
        "bg_image":"https://www.reshdp.com/img/re2header_uw.jpg",
        "final_name":"RE2SHDP - RE Seamless HD Project (biohazard-2-apan-source-next)","has_amd_option":False,
        "exe_name":"bio2.exe",
    },
}

ALL_MODS=[
    ("Bio2_mod.zip","https://github.com/TheOtherGuy66-source/Resident_Evil_Python_Builder_kit/releases/download/amd/Bio2_mod.zip"),
]

HELP_TEXT=(
    "Resident Evil 2 Linux Modder - Help\n"
    "--------------------------------------\n\n"
    "BUTTONS:\n\n"
    "  A/D (Auto Download)\n"
    "    Downloads the RE2 ISO + Bio2_mod.zip, extracts the ISO\n"
    "    to your Desktop, applies the mod, creates a savedata\n"
    "    folder, deletes the archives, and writes a\n"
    "    run_proton.sh launch script.\n\n"
    "  Auto - Apply Mod Only\n"
    "    Applies Bio2_mod.zip to an existing game folder on\n"
    "    your Desktop. Use this if you already extracted the\n"
    "    ISO manually.\n\n"
    "LAUNCHING THE GAME:\n"
    "  A run_proton.sh script is created in the final game folder.\n"
    "  Run it with:  bash run_proton.sh\n"
    "  It auto-detects the newest Proton-GE in ~/.steam/root/\n"
    "  compatibilitytools.d/ and uses the correct Steam env vars.\n"
    "  If Proton-GE is not found it falls back to Wine.\n"
    "  Install Proton-GE via ProtonUp-Qt for best compatibility.\n\n"
    "FIRST TIME CONFIGURATION:\n"
    "  1. Open the game folder on your Desktop.\n"
    "  2. Open config.ini in Kate (or any text editor).\n"
    "  3. Find the line  BootConfig = 0  and change the 0 to 1,\n"
    "     then save and close the file.\n"
    "  4. Run bio2.exe - the Configuration menu will now appear.\n"
    "  5. Click BEST to auto-apply the recommended settings.\n"
    "  6. Untick Texture Filtering.\n"
    "  7. Click OK - the game will launch correctly.\n\n"
    "CONTROLLER SETUP (in-game):\n"
    "  - Press SELECT in-game to open the controller config.\n"
    "  - Set your aim to the front right trigger (R2 / RT).\n\n"
    "REQUIRED GAME FOLDER NAME (exact, on Desktop):\n"
    "  biohazard-2-apan-source-next\n\n"
    "NOTES:\n"
    "  - 7z must be installed: sudo apt install p7zip-full\n"
    "  - Use the Japanese PC (Source Next) version only.\n"
    "  - Download progress is shown live in the log console.\n"
)

class ImageWorker(QtCore.QThread):
    done=QtCore.pyqtSignal(str)
    def __init__(self,url,path,parent=None):
        super().__init__(parent); self.url=url; self.path=path
    def run(self):
        try:
            r=requests.get(self.url,timeout=15); r.raise_for_status()
            open(self.path,"wb").write(r.content); self.done.emit(self.path)
        except: self.done.emit("")

class ModWorker(QtCore.QThread):
    log=QtCore.pyqtSignal(str,bool)
    done=QtCore.pyqtSignal(bool)
    progress=QtCore.pyqtSignal(int,int)   # value, maximum (max=0 means indeterminate)
    def __init__(self,game_key,mode,parent=None):
        super().__init__(parent); self.game_key=game_key; self.mode=mode; self._cancelled=False
    def cancel(self): self._cancelled=True
    def run(self):
        try:
            if self.mode=="auto_download": self._full()
            else: self._mod_only()
            if self._cancelled: self.log.emit("Cancelled.",True); self.done.emit(False)
            else: self.done.emit(True)
        except Exception as e:
            if self._cancelled: self.log.emit("Cancelled.",True)
            else: self.log.emit("CRITICAL ERROR: "+str(e),True)
            self.done.emit(False)

    def _l(self,m,e=False): self.log.emit(m,e)

    def _cleanup_files(self,paths):
        for f in paths:
            try:
                if f and os.path.exists(f):
                    os.remove(f); self._l("Deleted incomplete file: "+os.path.basename(f),True)
            except Exception: pass

    def _dl(self,label,url,dest):
        self._l("Downloading "+label+" ...")
        # Check if server supports range requests
        head=requests.head(url,timeout=30,allow_redirects=True)
        total=int(head.headers.get("content-length",0))
        accepts_ranges=head.headers.get("accept-ranges","none").lower()=="bytes"

        if not total or not accepts_ranges:
            self._l("  Server does not support parallel download, using single thread ...")
            self._dl_single(label,url,dest,total)
            return

        NUM_THREADS=8
        chunk_size=total//NUM_THREADS
        segments=[]
        for i in range(NUM_THREADS):
            start=i*chunk_size
            end=(start+chunk_size-1) if i<NUM_THREADS-1 else (total-1)
            segments.append((i,start,end))

        seg_files=[dest+".part%d"%i for i,_,_ in segments]
        seg_done=[0]*NUM_THREADS
        lock=threading.Lock()
        errors=[]

        self.progress.emit(0,total)
        self._l("  Starting %d parallel segments ..."%NUM_THREADS)

        def download_segment(i,start,end):
            try:
                headers={"Range":"bytes=%d-%d"%(start,end)}
                with requests.get(url,headers=headers,stream=True,timeout=300) as r:
                    r.raise_for_status()
                    with open(seg_files[i],"wb") as fh:
                        for chunk in r.iter_content(chunk_size=512*1024):
                            if self._cancelled: return   # file handle closed cleanly here
                            if chunk:
                                fh.write(chunk)
                                with lock:
                                    seg_done[i]+=len(chunk)
                                    self.progress.emit(sum(seg_done),total)
            except Exception as e:
                if not self._cancelled:
                    with lock: errors.append("Segment %d: %s"%(i,str(e)))

        threads=[threading.Thread(target=download_segment,args=(i,s,e),daemon=True) for i,s,e in segments]
        for t in threads: t.start()

        # Wait for all threads, polling for cancel every 0.5s
        while any(t.is_alive() for t in threads):
            threading.Event().wait(0.5)
            if self._cancelled:
                # Wait for all threads to exit their current chunk cleanly
                for t in threads: t.join(timeout=5)
                # Now all file handles are closed - safe to delete
                self._cleanup_files(seg_files+[dest])
                raise InterruptedError("Cancelled")
            with lock:
                total_done=sum(seg_done)
                pct=int(total_done*100/total) if total else 0
            self._l("  %s: %d%%  (%.1f MB / %.1f MB)"%(label,pct,total_done/(1<<20),total/(1<<20)))

        for t in threads: t.join()

        if errors:
            self._cleanup_files(seg_files+[dest])
            raise RuntimeError("Parallel download failed:\n"+"\n".join(errors))

        # Reassemble segments in order
        self._l("  Reassembling segments ...")
        self.progress.emit(0,0)
        try:
            with open(dest,"wb") as out:
                for f in seg_files:
                    with open(f,"rb") as inp: shutil.copyfileobj(inp,out)
                    os.remove(f)
        except Exception:
            self._cleanup_files(seg_files+[dest])
            raise

        self.progress.emit(total,total)
        self._l("Download complete: "+label)

    def _dl_single(self,label,url,dest,total=0):
        try:
            with requests.get(url,stream=True,timeout=300) as r:
                r.raise_for_status()
                if not total: total=int(r.headers.get("content-length",0))
                done=0; last=-1
                if total: self.progress.emit(0,total)
                else: self.progress.emit(0,0)
                with open(dest,"wb") as fh:
                    for chunk in r.iter_content(chunk_size=1<<20):
                        if self._cancelled: raise InterruptedError("Cancelled")
                        if chunk:
                            fh.write(chunk); done+=len(chunk)
                            if total:
                                self.progress.emit(done,total)
                                pct=int(done*100/total)
                                if pct>=last+5:
                                    last=pct; self._l("  %s: %d%%  (%.1f MB / %.1f MB)"%(label,pct,done/(1<<20),total/(1<<20)))
                            else:
                                mb=done/(1<<20); prev=(done-len(chunk))/(1<<20)
                                if int(mb)>int(prev): self._l("  %s: %.0f MB ..."%(label,mb))
        except InterruptedError:
            # File handle is closed here since we're outside the `with open` block
            self._cleanup_files([dest])
            raise
        self.progress.emit(0,0)
        self._l("Download complete: "+label)

    def _7z(self,iso,dest):
        self._l("Extracting ISO -> "+os.path.basename(dest)+" ..."); os.makedirs(dest,exist_ok=True)
        p=subprocess.run(["7z","x",iso,"-o"+dest,"-y"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode!=0: raise RuntimeError("7z: "+p.stderr.decode(errors="replace").strip())
        self._l("ISO extraction complete.")

    def _zip(self,label,zpath,tdir):
        self._l("Applying "+label+" ...")
        with zipfile.ZipFile(zpath,"r") as z:
            all_entries=z.namelist()
            files=[n for n in all_entries if not n.endswith('/')]
            top_entries=sorted(set(n.split('/')[0] for n in all_entries))
            self._l("  Zip top-level: "+", ".join(top_entries[:10]))
            common=os.path.commonpath(all_entries) if len(all_entries)>1 else ""
            if common and common!='.' and all(n==common or n.startswith(common+'/') for n in all_entries):
                strip=common+'/'
            else:
                strip=""
            for member in files:
                rel=member[len(strip):] if strip and member.startswith(strip) else member
                if not rel: continue
                dst=os.path.join(tdir,rel); os.makedirs(os.path.dirname(dst),exist_ok=True)
                with z.open(member) as src, open(dst,"wb") as out: shutil.copyfileobj(src,out)
        self._l(label+" applied successfully.")

    def _find(self,name):
        for folder in [xdg_desktop(),xdg_download()]:
            for root,_,files in os.walk(folder):
                if name in files:
                    p=os.path.join(root,name); self._l("Found "+name+": "+p); return p
        return None

    def _clean(self,paths):
        self._l("Cleaning up archives ...")
        for p in paths:
            if p and os.path.exists(p): os.remove(p); self._l("  Removed: "+os.path.basename(p))
        self._l("Cleanup complete.")

    def _find_proton_ge(self):
        steam_roots=[
            os.path.expanduser("~/.steam/root"),
            os.path.expanduser("~/.local/share/Steam"),
        ]
        candidates=[]
        for sr in steam_roots:
            compat=os.path.join(sr,"compatibilitytools.d")
            if not os.path.isdir(compat): continue
            for entry in os.listdir(compat):
                if "proton" in entry.lower() and ("ge" in entry.lower() or "GE" in entry):
                    proton_bin=os.path.join(compat,entry,"proton")
                    if os.path.isfile(proton_bin):
                        candidates.append((entry,proton_bin,sr))
        if not candidates: return None,None
        candidates.sort(key=lambda x:x[0],reverse=True)
        name,proton_bin,steam_root=candidates[0]
        self._l("Found Proton-GE: "+name)
        return proton_bin,steam_root

    def _write_launch_script(self,game_dir,cfg):
        proton_bin,steam_root=self._find_proton_ge()
        exe_path=os.path.join(game_dir,cfg["exe_name"])
        compat_data=os.path.join(game_dir,"proton_pfx")
        os.makedirs(compat_data,exist_ok=True)

        if proton_bin:
            runner_lines=(
                '#!/usr/bin/env bash\n'
                '# Auto-generated by RE2 Linux Modder\n'
                'set -e\n'
                'PROTON="{proton}"\n'
                'STEAM_ROOT="{steam_root}"\n'
                'COMPAT_DATA="{compat_data}"\n'
                'EXE="{exe}"\n\n'
                'export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"\n'
                'export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"\n'
                '# --- RE2 SHDP Linux fix ---\n'
                '# bio2.exe is 32-bit. Without LAA it is capped at 2GB virtual memory.\n'
                '# The SHDP hires textures push it past that ceiling causing black screens\n'
                '# on doors, item pickup stutter and sluggish exit. LAA lifts the cap to 4GB+.\n'
                'export WINE_LARGE_ADDRESS_AWARE=1\n'
                '# Force native mod DLLs - dinput8 loads HD textures, ddraw is the\n'
                '# Classic Rebirth hook. Both must be native or textures load slowly.\n'
                'export WINEDLLOVERRIDES="d3d9,d3dcompiler_47,ddraw,dinput8,dsound,libwebp,xaudio2_9=n,b"\n'
                '# Thread sync - reduces stutter on item pickup, doors and game exit\n'
                'export WINEESYNC=1\n'
                'export WINEFSYNC=1\n'
                '# Async shader compilation - prevents compile hitches mid-game\n'
                'export DXVK_ASYNC=1\n'
                '# Cap framerate - reduces GPU thrashing during texture loads\n'
                'export DXVK_FRAME_RATE=60\n'
                'export PROTON_LOG=1\n\n'
                'echo "Launching RE2 SHDP with Proton-GE: $PROTON"\n'
                'cd "$(dirname "$EXE")"\n'
                '"$PROTON" run "$EXE" "$@"\n'
            ).format(
                proton=proton_bin,
                steam_root=steam_root,
                compat_data=compat_data,
                exe=exe_path,
            )
            note="Proton-GE launch script written (LAA + full SHDP fix applied)."
        else:
            runner_lines=(
                '#!/usr/bin/env bash\n'
                '# Auto-generated by RE2 Linux Modder\n'
                '# WARNING: Proton-GE not found - falling back to Wine.\n'
                '# Install Proton-GE via ProtonUp-Qt then re-run the modder.\n'
                'EXE="{exe}"\n\n'
                '# --- RE2 SHDP Linux fix ---\n'
                'export WINE_LARGE_ADDRESS_AWARE=1\n'
                'export WINEDLLOVERRIDES="d3d9,d3dcompiler_47,ddraw,dinput8,dsound,libwebp,xaudio2_9=n,b"\n'
                'export WINEESYNC=1\n'
                'export WINEFSYNC=1\n'
                'export DXVK_ASYNC=1\n'
                'export DXVK_FRAME_RATE=60\n\n'
                'echo "Proton-GE not found - using Wine fallback."\n'
                'cd "$(dirname "$EXE")"\n'
                'wine "$EXE" "$@"\n'
            ).format(exe=exe_path)
            note="Proton-GE not found - Wine fallback script written (LAA + SHDP fix). Install Proton-GE via ProtonUp-Qt for best results."

        script_path=os.path.join(game_dir,"run_proton.sh")
        with open(script_path,"w") as fh: fh.write(runner_lines)
        os.chmod(script_path,0o755)
        self._l(note)
        self._l("Launch script: "+script_path)

    def _patch_config_ini(self,game_dir):
        cfg_path=os.path.join(game_dir,"config.ini")
        if not os.path.exists(cfg_path):
            self._l("config.ini not found, skipping BootConfig patch.",True); return
        with open(cfg_path,"r",encoding="utf-8",errors="replace") as f: content=f.read()
        import re as _re
        patched=_re.sub(r'(BootConfig\s*=\s*)0',r'\g<1>1',content)
        if patched==content:
            self._l("BootConfig already set to 1 or not found - no change needed."); return
        with open(cfg_path,"w",encoding="utf-8") as f: f.write(patched)
        self._l("Patched config.ini: BootConfig = 0  ->  BootConfig = 1")

    def _full(self):
        cfg=GAME_CONFIGS[self.game_key]; dl=xdg_download(); desk=xdg_desktop()
        iso=os.path.join(dl,cfg["iso_name"]); mod=os.path.join(dl,cfg["mod_name"])
        staging=os.path.join(dl,cfg["folder"]+"__staging")
        fdir=os.path.join(desk,cfg["final_name"])

        try:
            if os.path.exists(iso): self._l("ISO already present, skipping download.")
            else: self._dl(cfg["iso_name"],cfg["iso_url"],iso)

            if self._cancelled: raise InterruptedError("Cancelled")

            if os.path.exists(mod): self._l("Mod zip already present, skipping download.")
            else: self._dl(cfg["mod_name"],cfg["mod_url"],mod)

            if self._cancelled: raise InterruptedError("Cancelled")

        except InterruptedError:
            # Clean up any partial downloads still sitting in Downloads folder
            self._cleanup_files([iso, mod])
            raise

        staging=os.path.join(dl,cfg["folder"]+"__staging")
        self._l("Extracting ISO ...")
        if os.path.exists(staging): shutil.rmtree(staging)
        self._7z(iso,staging)
        top=os.listdir(staging); self._l("ISO top-level: "+", ".join(sorted(top)))

        tsub_src=os.path.join(staging,cfg["target_subdir"])
        if not os.path.isdir(tsub_src):
            raise FileNotFoundError("'%s' not found at ISO root. Top-level: %s"%(cfg["target_subdir"],", ".join(top)))
        self._l("Found: "+tsub_src)

        self._zip(cfg["mod_name"],mod,tsub_src)

        self._l("Moving to Desktop as: "+cfg["final_name"])
        if os.path.exists(fdir): shutil.rmtree(fdir)
        shutil.move(tsub_src,fdir)

        self._l("Removing staging remainder ...")
        shutil.rmtree(staging)

        os.makedirs(os.path.join(fdir,"savedata"),exist_ok=True)
        self._l("Created savedata folder.")

        self._clean([iso,mod])

        self._write_launch_script(fdir,cfg)
        self._patch_config_ini(fdir)
        self._l("="*50); self._l("ALL DONE! -> "+cfg["final_name"])
        self._l("Run: bash run_proton.sh  (inside the game folder)"); self._l("Good luck, S.T.A.R.S.!"); self._l("="*50)

    def _mod_only(self):
        cfg=GAME_CONFIGS[self.game_key]; desk=xdg_desktop()
        gdir=os.path.join(desk,cfg["folder"]); fdir=os.path.join(desk,cfg["final_name"])
        if not os.path.isdir(gdir):
            self._l("Game folder not found: "+cfg["folder"],True)
            self._l("Use A/D to download and extract, or extract manually.",True)
            raise FileNotFoundError(gdir)
        tsub=os.path.join(gdir,cfg["target_subdir"])
        if not os.path.isdir(tsub):
            self._l("'%s' not found inside %s"%(cfg["target_subdir"],cfg["folder"]),True)
            raise FileNotFoundError(tsub)
        mzip=self._find(cfg["mod_name"])
        if not mzip: self._l(cfg["mod_name"]+" not found.",True); raise FileNotFoundError(cfg["mod_name"])
        self._zip(cfg["mod_name"],mzip,tsub)
        self._l("Renaming to: "+cfg["final_name"])
        if os.path.exists(fdir): shutil.rmtree(fdir)
        shutil.move(tsub,fdir)
        self._l("Removing leftover game folder ...")
        shutil.rmtree(gdir)
        os.makedirs(os.path.join(fdir,"savedata"),exist_ok=True)
        self._l("Created savedata folder.")
        self._clean([mzip])
        self._write_launch_script(fdir,cfg)
        self._patch_config_ini(fdir)
        self._l("="*50); self._l("ALL DONE! -> "+cfg["final_name"])
        self._l("Run: bash run_proton.sh  (inside the game folder)"); self._l("Good luck, S.T.A.R.S.!"); self._l("="*50)


class REModderApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.current_key="re2"; self.mod_worker=None; self.img_worker=None
        self._build_ui()
        self._select_game("re2")

    def _build_ui(self):
        self.setWindowTitle("Resident Evil 2 Linux Modder"); self.setMinimumSize(1000,840)
        self.setStyleSheet(
            "QWidget{background:#2E2E2E;color:#EEE;font-family:sans-serif;}"
            "QPushButton{background:#3A3A3A;border:1px solid #555;padding:8px 14px;border-radius:4px;color:#EEE;}"
            "QPushButton:hover{background:#4A4A4A;}"
            "QPushButton:disabled{color:#555;background:#2A2A2A;border-color:#3A3A3A;}"
            "QComboBox{background:#3A3A3A;border:1px solid #555;padding:4px 8px;color:#EEE;}"
            "QTextEdit{background:#1A1A1A;color:#00DD00;font-family:monospace;font-size:12px;}"
            "QProgressBar{border:1px solid #555;border-radius:4px;text-align:center;}"
            "QProgressBar::chunk{background:#4CAF50;}"
            "QMenuBar{background:#2E2E2E;color:#EEE;}"
            "QMenuBar::item:selected{background:#4A4A4A;}"
            "QMenu{background:#3A3A3A;color:#EEE;}"
            "QMenu::item:selected{background:#555;}"
        )
        root=QtWidgets.QVBoxLayout(self); root.setSpacing(6); root.setContentsMargins(10,4,10,8)
        mb=QtWidgets.QMenuBar(self); ha=QtWidgets.QAction("Help",self); ha.triggered.connect(self._show_help)
        mb.addAction(ha); root.setMenuBar(mb)
        title_label=QtWidgets.QLabel("Resident Evil 2  —  SHDP Modder")
        title_label.setStyleSheet("font-size:16px;font-weight:bold;color:#7EC8FF;padding:6px 0;")
        title_label.setAlignment(QtCore.Qt.AlignCenter); root.addWidget(title_label)
        self.bg_label=QtWidgets.QLabel("Loading header image ...")
        self.bg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.bg_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        self.bg_label.setMinimumHeight(320)
        self.bg_label.setStyleSheet("background:#1A1A1A;border:1px solid #444;"); root.addWidget(self.bg_label,stretch=1)
        mr=QtWidgets.QHBoxLayout(); mr.addWidget(QtWidgets.QLabel("Select Mod to Download:"))
        self.mod_combo=QtWidgets.QComboBox()
        for n,u in ALL_MODS: self.mod_combo.addItem(n,u)
        mr.addWidget(self.mod_combo,1); db=QtWidgets.QPushButton("Open Download in Browser")
        db.clicked.connect(self._open_browser); mr.addWidget(db); root.addLayout(mr)
        self.log_area=QtWidgets.QTextEdit(); self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(240); root.addWidget(self.log_area)
        self.progress=QtWidgets.QProgressBar(); self.progress.setRange(0,0)
        self.progress.setVisible(False); self.progress.setFixedHeight(28)
        self.progress.setFormat("%p%"); root.addWidget(self.progress)
        ar=QtWidgets.QHBoxLayout(); ar.setSpacing(10)
        self.ad_btn=QtWidgets.QPushButton("A/D  --  Auto Download")
        self.ad_btn.setToolTip("Downloads ISO + mod, extracts, applies, cleans up. Fully hands-free.")
        self.ad_btn.setStyleSheet("background:#1a3a5c;color:#7EC8FF;font-weight:bold;padding:12px 20px;")
        self.ad_btn.clicked.connect(lambda:self._start("auto_download")); ar.addWidget(self.ad_btn)
        self.auto_btn=QtWidgets.QPushButton("Auto  --  Apply Mod Only")
        self.auto_btn.setToolTip("Applies mod zip to existing game folder (no ISO download).")
        self.auto_btn.clicked.connect(lambda:self._start("auto_mod")); ar.addWidget(self.auto_btn)
        self.cancel_btn=QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel the current operation.")
        self.cancel_btn.setStyleSheet("background:#5c1a1a;color:#FF8888;font-weight:bold;padding:12px 20px;")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel); ar.addWidget(self.cancel_btn)
        root.addLayout(ar)
        cred=QtWidgets.QLabel(
            '<font color="#CCC">Credits: </font><font color="#E55">TeamX</font><font color="#CCC"> [Textures]  </font>'
            '<font color="#E55">RESHDP</font><font color="#CCC"> [Textures]  </font>'
            '<font color="#E55">Gemini</font><font color="#CCC"> [Classic Rebirth]</font>'
        ); cred.setAlignment(QtCore.Qt.AlignCenter); root.addWidget(cred)

    def _select_game(self,key):
        self.current_key=key; cfg=GAME_CONFIGS[key]
        self._log("-- "+cfg["title"]+" selected --")
        self._log("Desktop folder: "+cfg["folder"])
        self._log("ISO:            "+cfg["iso_name"])
        self._log("Mod zip:        "+cfg["mod_name"])
        bg=os.path.join(cache_dir(),key+"_bg.jpg")
        if os.path.exists(bg): self._set_bg(bg)
        else:
            self.bg_label.setText("Loading image ...")
            self.img_worker=ImageWorker(cfg["bg_image"],bg,self)
            self.img_worker.done.connect(self._set_bg); self.img_worker.start()

    @QtCore.pyqtSlot(str)
    def _set_bg(self,path):
        if path and os.path.exists(path):
            w=self.bg_label.width() or 980; h=self.bg_label.height() or 320
            self.bg_label.setPixmap(QtGui.QPixmap(path).scaled(w,h,QtCore.Qt.KeepAspectRatioByExpanding,QtCore.Qt.SmoothTransformation))
        else: self.bg_label.setText("(banner unavailable)")

    def _cancel(self):
        if self.mod_worker and self.mod_worker.isRunning():
            self._log("Cancelling ...",True); self.mod_worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _update_progress(self,value,maximum):
        if maximum==0:
            self.progress.setRange(0,0); self.progress.setFormat("Working ...")
        else:
            self.progress.setRange(0,maximum); self.progress.setValue(value)
            self.progress.setFormat("%p%")

    def _start(self,mode):
        if self.mod_worker and self.mod_worker.isRunning(): self._log("Already running.",True); return
        btn=self.ad_btn if mode=="auto_download" else self.auto_btn
        btn.setStyleSheet("background:#226622;color:white;font-weight:bold;padding:12px 20px;")
        self.mod_worker=ModWorker(self.current_key,mode,self)
        self.mod_worker.log.connect(self._log)
        self.mod_worker.progress.connect(self._update_progress)
        self.mod_worker.done.connect(lambda ok:self._done(ok,btn)); self.mod_worker.start()
        for b in (self.ad_btn,self.auto_btn): b.setEnabled(False)
        self.cancel_btn.setVisible(True); self.cancel_btn.setEnabled(True)
        self.progress.setRange(0,0); self.progress.setFormat("Working ...")
        self.progress.setVisible(True)

    def _done(self,ok,btn):
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False); self.cancel_btn.setEnabled(True)
        for b in (self.ad_btn,self.auto_btn): b.setEnabled(True)
        if ok: btn.setStyleSheet("background:#2D6A2D;color:white;font-weight:bold;padding:12px 20px;"); btn.setText("Done!  OK")
        else: btn.setStyleSheet("background:#6A2D2D;color:white;font-weight:bold;padding:12px 20px;"); btn.setText("Failed -- see log")

    def _open_browser(self):
        webbrowser.open(self.mod_combo.currentData()); self._log("Opened: "+self.mod_combo.currentText())

    def _show_help(self):
        d=QtWidgets.QDialog(self); d.setWindowTitle("Help"); d.setMinimumSize(520,400)
        d.setStyleSheet("QDialog{background:#2E2E2E;} QTextEdit{background:#1A1A1A;color:#EEE;font-family:monospace;font-size:12px;border:1px solid #555;} QPushButton{background:#3A3A3A;border:1px solid #555;padding:6px 18px;border-radius:4px;color:#EEE;} QPushButton:hover{background:#4A4A4A;}")
        lay=QtWidgets.QVBoxLayout(d)
        t=QtWidgets.QTextEdit(); t.setReadOnly(True); t.setPlainText(HELP_TEXT)
        t.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn); lay.addWidget(t)
        btn=QtWidgets.QPushButton("Close"); btn.clicked.connect(d.accept); lay.addWidget(btn,alignment=QtCore.Qt.AlignRight)
        d.exec_()

    @QtCore.pyqtSlot(str,bool)
    def _log(self,msg,error=False):
        col="#FF6666" if error else "#55FF55"
        self.log_area.append("<span style='color:%s;'>&gt; %s</span>"%(col,msg))
        sb=self.log_area.verticalScrollBar(); sb.setValue(sb.maximum())


if __name__=="__main__":
    # Minimize the terminal to taskbar so only the GUI is visible
    try:
        import ctypes
        hwnd=ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd: ctypes.windll.user32.ShowWindow(hwnd,6)
    except Exception: pass
    try:
        subprocess.run(["xdotool","getactivewindow","windowminimize"],
                       capture_output=True,timeout=2)
    except Exception: pass
    app=QtWidgets.QApplication(sys.argv); app.setApplicationName("RE2 Linux Modder")
    win=REModderApp(); win.show(); sys.exit(app.exec_())
