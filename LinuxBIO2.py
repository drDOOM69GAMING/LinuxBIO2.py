#!/usr/bin/env -S python3 -W ignore
import os, sys, subprocess, shutil, zipfile, webbrowser, requests, threading
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
    "  Reset Proton Prefix\n"
    "    Deletes and rebuilds the proton_pfx folder inside the\n"
    "    game directory AND rewrites run_proton.sh.\n"
    "    Use this if the game stopped launching, the black bars\n"
    "    disappeared, or you see odd errors on startup.\n\n"
    "LAUNCHING THE GAME:\n"
    "  A run_proton.sh script is created in the final game folder.\n"
    "  Run it with:  bash run_proton.sh\n"
    "  It auto-detects the newest Proton-GE in ~/.steam/root/\n"
    "  compatibilitytools.d/ and uses the correct Steam env vars.\n"
    "  If Proton-GE is not found it falls back to Wine.\n"
    "  Install Proton-GE via ProtonUp-Qt for best compatibility.\n\n"
    "ABOUT THE BLACK SIDE BARS:\n"
    "  The black side bars are INTENTIONAL. Classic REbirth\n"
    "  enforces the correct 4:3 aspect ratio by design.\n"
    "  If the bars are missing, the Classic REbirth ddraw hook\n"
    "  is not loading. Use 'Reset Proton Prefix' to fix this.\n\n"
    "ABOUT XALIA / 'Invalid window handle' IN THE LOG:\n"
    "  These messages are completely harmless. Xalia is a\n"
    "  gamepad accessibility tool built into Proton-GE. It runs\n"
    "  alongside every game and its handle errors are normal.\n"
    "  They have no effect on gameplay.\n\n"
    "FIRST TIME CONFIGURATION:\n"
    "  The modder auto-sets BootConfig = 1 in config.ini.\n"
    "  Run bash run_proton.sh - the config window will appear.\n"
    "  Click BEST, untick Texture Filtering, then click OK.\n\n"
    "CONTROLLER SETUP (in-game):\n"
    "  Press SELECT in-game to open the controller config.\n"
    "  Set aim to the front right trigger (R2 / RT).\n\n"
    "SLOW TEXTURE LOADING (doors / item pickups):\n"
    "  On the first playthrough DXVK compiles shaders on the fly.\n"
    "  This causes one-time hitches on first door/item encounters.\n"
    "  After each transition is triggered once, the shader is\n"
    "  cached and subsequent loads are smooth. This is normal.\n\n"
    "REQUIRED GAME FOLDER NAME (exact, on Desktop):\n"
    "  biohazard-2-apan-source-next\n\n"
    "NOTES:\n"
    "  - 7z must be installed: sudo apt install p7zip-full\n"
    "  - Use the Japanese PC (Source Next) version only.\n"
    "  - Download progress is shown live in the log console.\n"
)

# -----------------------------------------------------------------------
# DLL OVERRIDE RATIONALE  (community-confirmed working set)
#
# Sources:
#   github.com/ValveSoftware/Proton/issues/8238
#   forum.winehq.org/viewtopic.php?t=39604
#   moddb.com/downloads/aio-qol-mod-pack-for-resident-evil-2-1998-sourcenext-gog
#
# d3d9, d3dcompiler_47  -> DXVK handles D3D9. Required for SHDP HD
#                          textures; WineD3D cannot load them properly.
# ddraw                 -> Classic REbirth v1.0.9 uses DirectDraw as its
#                          core renderer. Its own ddraw.dll sits in the
#                          game folder and Proton must use THAT one.
#                          Including ddraw=n,b here tells Wine to prefer
#                          native DLLs, so the game-folder copy wins over
#                          any system stub. This is what keeps Classic
#                          REbirth's 4:3 aspect ratio hook active (bars).
# dinput8               -> The HD texture loader (bio2hd.asi) is injected
#                          via dinput8. Must be native or textures won't load.
# dsound, libwebp       -> TeamX HD mod audio/media support.
# xaudio2_9             -> Classic REbirth audio subsystem.
#
# IMPORTANT: Do NOT add PROTON_USE_WINED3D=0. That is not a real Proton
# environment variable and corrupts the prefix on rebuild, causing the
# 'Invalid window handle' cascade seen in the terminal output.
# -----------------------------------------------------------------------
DLL_OVERRIDES = "d3d9,d3dcompiler_47,ddraw,dinput8,dsound,libwebp,xaudio2_9=n,b"


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
    progress=QtCore.pyqtSignal(int,int)
    def __init__(self,game_key,mode,parent=None):
        super().__init__(parent); self.game_key=game_key; self.mode=mode; self._cancelled=False
    def cancel(self): self._cancelled=True
    def run(self):
        try:
            if self.mode=="auto_download": self._full()
            elif self.mode=="auto_mod": self._mod_only()
            elif self.mode=="reset_prefix": self._reset_prefix()
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
        head=requests.head(url,timeout=30,allow_redirects=True)
        total=int(head.headers.get("content-length",0))
        accepts_ranges=head.headers.get("accept-ranges","none").lower()=="bytes"
        if not total or not accepts_ranges:
            self._l("  Server does not support parallel download, using single thread ...")
            self._dl_single(label,url,dest,total); return

        NUM_THREADS=8
        chunk_size=total//NUM_THREADS
        segments=[(i,i*chunk_size,(i*chunk_size+chunk_size-1) if i<NUM_THREADS-1 else total-1)
                  for i in range(NUM_THREADS)]
        seg_files=[dest+".part%d"%i for i,_,_ in segments]
        seg_done=[0]*NUM_THREADS; lock=threading.Lock(); errors=[]
        self.progress.emit(0,total)
        self._l("  Starting %d parallel segments ..."%NUM_THREADS)

        def download_segment(i,start,end):
            try:
                with requests.get(url,headers={"Range":"bytes=%d-%d"%(start,end)},
                                  stream=True,timeout=300) as r:
                    r.raise_for_status()
                    with open(seg_files[i],"wb") as fh:
                        for chunk in r.iter_content(chunk_size=512*1024):
                            if self._cancelled: return
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
        while any(t.is_alive() for t in threads):
            threading.Event().wait(0.5)
            if self._cancelled:
                for t in threads: t.join(timeout=5)
                self._cleanup_files(seg_files+[dest]); raise InterruptedError("Cancelled")
            with lock:
                total_done=sum(seg_done)
                pct=int(total_done*100/total) if total else 0
            self._l("  %s: %d%%  (%.1f MB / %.1f MB)"%(label,pct,total_done/(1<<20),total/(1<<20)))
        for t in threads: t.join()
        if errors:
            self._cleanup_files(seg_files+[dest])
            raise RuntimeError("Parallel download failed:\n"+"\n".join(errors))
        self._l("  Reassembling segments ..."); self.progress.emit(0,0)
        try:
            with open(dest,"wb") as out:
                for f in seg_files:
                    with open(f,"rb") as inp: shutil.copyfileobj(inp,out)
                    os.remove(f)
        except Exception:
            self._cleanup_files(seg_files+[dest]); raise
        self.progress.emit(total,total); self._l("Download complete: "+label)

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
            self._cleanup_files([dest]); raise
        self.progress.emit(0,0); self._l("Download complete: "+label)

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
            strip=(common+'/') if common and common!='.' and all(
                n==common or n.startswith(common+'/') for n in all_entries) else ""
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
        steam_roots=[os.path.expanduser("~/.steam/root"),
                     os.path.expanduser("~/.local/share/Steam")]
        candidates=[]
        for sr in steam_roots:
            compat=os.path.join(sr,"compatibilitytools.d")
            if not os.path.isdir(compat): continue
            for entry in os.listdir(compat):
                if "proton" in entry.lower() and ("ge" in entry.lower() or "GE" in entry):
                    proton_bin=os.path.join(compat,entry,"proton")
                    if os.path.isfile(proton_bin): candidates.append((entry,proton_bin,sr))
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

        env_block=(
            '# --- RE2 SHDP + Classic REbirth Linux environment ---\n'
            '#\n'
            '# Large Address Aware: bio2.exe is 32-bit and hits a 2 GB virtual\n'
            '# memory ceiling without this. SHDP textures can push past that\n'
            '# limit causing black door screens and item-pickup stutter.\n'
            'export WINE_LARGE_ADDRESS_AWARE=1\n'
            '#\n'
            '# Community-confirmed DLL overrides for RE2 1998 SourceNext +\n'
            '# Classic REbirth + Seamless HD Project on Linux / Proton-GE.\n'
            '# See DLL_OVERRIDES comment block in the modder script for full\n'
            '# rationale on why each DLL is listed.\n'
            'export WINEDLLOVERRIDES="{dlls}"\n'
            '#\n'
            '# Thread sync: reduces stutter on item pickup, doors and exit.\n'
            'export WINEESYNC=1\n'
            'export WINEFSYNC=1\n'
            '#\n'
            '# DXVK async shader compilation prevents mid-game compile hitches.\n'
            '# First-run hitches on new doors/items are normal (shader caching).\n'
            'export DXVK_ASYNC=1\n'
            '# 60 fps cap reduces GPU thrashing during texture loads.\n'
            'export DXVK_FRAME_RATE=60\n'
        ).format(dlls=DLL_OVERRIDES)

        if proton_bin:
            script=(
                '#!/usr/bin/env bash\n'
                '# Auto-generated by RE2 Linux Modder\n'
                '# Use "Reset Proton Prefix" in the modder to regenerate this file.\n'
                'set -e\n'
                'PROTON="{proton}"\n'
                'STEAM_ROOT="{steam_root}"\n'
                'COMPAT_DATA="{compat_data}"\n'
                'EXE="{exe}"\n\n'
                'export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"\n'
                'export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"\n'
                '{env_block}'
                'export PROTON_LOG=1\n\n'
                'echo ""\n'
                'echo "  RE2 SHDP -> Proton-GE: $(basename $(dirname $PROTON))"\n'
                'echo "  Black side bars are correct (Classic REbirth 4:3 by design)"\n'
                'echo "  Xalia / handle errors in log are harmless (Proton-GE built-in)"\n'
                'echo "  First-run door/item hitches are normal (DXVK shader caching)"\n'
                'echo ""\n'
                'cd "$(dirname "$EXE")"\n'
                '"$PROTON" run "$EXE" "$@"\n'
            ).format(
                proton=proton_bin, steam_root=steam_root,
                compat_data=compat_data, exe=exe_path, env_block=env_block,
            )
            note="Proton-GE launch script written."
        else:
            script=(
                '#!/usr/bin/env bash\n'
                '# Auto-generated by RE2 Linux Modder\n'
                '# WARNING: Proton-GE not found - falling back to Wine.\n'
                '# Install Proton-GE via ProtonUp-Qt for best results.\n'
                'EXE="{exe}"\n\n'
                '{env_block}'
                '\n'
                'echo ""\n'
                'echo "  RE2 SHDP -> Wine fallback (Proton-GE not found)"\n'
                'echo "  Install Proton-GE via ProtonUp-Qt for best results."\n'
                'echo "  Black side bars are correct (Classic REbirth 4:3 by design)"\n'
                'echo ""\n'
                'cd "$(dirname "$EXE")"\n'
                'wine "$EXE" "$@"\n'
            ).format(exe=exe_path, env_block=env_block)
            note="Proton-GE not found - Wine fallback script written. Install Proton-GE via ProtonUp-Qt."

        script_path=os.path.join(game_dir,"run_proton.sh")
        with open(script_path,"w") as fh: fh.write(script)
        os.chmod(script_path,0o755)
        self._l(note); self._l("Launch script: "+script_path)

    def _patch_config_ini(self,game_dir):
        cfg_path=os.path.join(game_dir,"config.ini")
        if not os.path.exists(cfg_path):
            self._l("config.ini not found, skipping BootConfig patch.",True); return
        with open(cfg_path,"r",encoding="utf-8",errors="replace") as f: content=f.read()
        import re as _re
        patched=_re.sub(r'(BootConfig\s*=\s*)0',r'\g<1>1',content)
        if patched==content:
            self._l("BootConfig already 1 or not found - no change."); return
        with open(cfg_path,"w",encoding="utf-8") as f: f.write(patched)
        self._l("Patched config.ini: BootConfig = 0 -> BootConfig = 1")

    def _reset_prefix(self):
        cfg=GAME_CONFIGS[self.game_key]; desk=xdg_desktop()
        game_dir=os.path.join(desk,cfg["final_name"])
        if not os.path.isdir(game_dir):
            self._l("Game folder not found: "+cfg["final_name"],True)
            self._l("Run A/D first to set up the game.",True)
            raise FileNotFoundError(game_dir)
        pfx=os.path.join(game_dir,"proton_pfx")
        if os.path.exists(pfx):
            self._l("Removing corrupt Proton prefix: "+pfx)
            shutil.rmtree(pfx); self._l("Old prefix removed.")
        else:
            self._l("No existing prefix found.")
        os.makedirs(pfx,exist_ok=True)
        self._l("Fresh prefix directory created.")
        self._write_launch_script(game_dir,cfg)
        self._l("="*50)
        self._l("Prefix reset complete. Run: bash run_proton.sh")
        self._l("Proton will rebuild the prefix automatically on first launch.")
        self._l("="*50)

    def _full(self):
        cfg=GAME_CONFIGS[self.game_key]; dl=xdg_download(); desk=xdg_desktop()
        iso=os.path.join(dl,cfg["iso_name"]); mod=os.path.join(dl,cfg["mod_name"])
        fdir=os.path.join(desk,cfg["final_name"])
        try:
            if os.path.exists(iso): self._l("ISO already present, skipping download.")
            else: self._dl(cfg["iso_name"],cfg["iso_url"],iso)
            if self._cancelled: raise InterruptedError("Cancelled")
            if os.path.exists(mod): self._l("Mod zip already present, skipping download.")
            else: self._dl(cfg["mod_name"],cfg["mod_url"],mod)
            if self._cancelled: raise InterruptedError("Cancelled")
        except InterruptedError:
            self._cleanup_files([iso,mod]); raise

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
        self._l("Removing staging remainder ..."); shutil.rmtree(staging)
        os.makedirs(os.path.join(fdir,"savedata"),exist_ok=True)
        self._l("Created savedata folder.")
        self._clean([iso,mod])
        self._write_launch_script(fdir,cfg)
        self._patch_config_ini(fdir)
        self._l("="*50)
        self._l("ALL DONE! -> "+cfg["final_name"])
        self._l("Run: bash run_proton.sh  (inside the game folder)")
        self._l("Black side bars = correct. Classic REbirth enforces 4:3.")
        self._l("Good luck, S.T.A.R.S.!")
        self._l("="*50)

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
        self._l("Removing leftover game folder ..."); shutil.rmtree(gdir)
        os.makedirs(os.path.join(fdir,"savedata"),exist_ok=True)
        self._l("Created savedata folder.")
        self._clean([mzip])
        self._write_launch_script(fdir,cfg)
        self._patch_config_ini(fdir)
        self._l("="*50)
        self._l("ALL DONE! -> "+cfg["final_name"])
        self._l("Run: bash run_proton.sh  (inside the game folder)")
        self._l("Black side bars = correct. Classic REbirth enforces 4:3.")
        self._l("Good luck, S.T.A.R.S.!")
        self._l("="*50)


class REModderApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.current_key="re2"; self.mod_worker=None; self.img_worker=None
        self._build_ui(); self._select_game("re2")

    def _build_ui(self):
        self.setWindowTitle("Resident Evil 2 Linux Modder"); self.setMinimumSize(1000,860)
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
        mb=QtWidgets.QMenuBar(self); ha=QtWidgets.QAction("Help",self)
        ha.triggered.connect(self._show_help); mb.addAction(ha); root.setMenuBar(mb)

        title=QtWidgets.QLabel("Resident Evil 2  —  SHDP Modder")
        title.setStyleSheet("font-size:16px;font-weight:bold;color:#7EC8FF;padding:6px 0;")
        title.setAlignment(QtCore.Qt.AlignCenter); root.addWidget(title)

        self.bg_label=QtWidgets.QLabel("Loading header image ...")
        self.bg_label.setAlignment(QtCore.Qt.AlignCenter)
        self.bg_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        self.bg_label.setMinimumHeight(300)
        self.bg_label.setStyleSheet("background:#1A1A1A;border:1px solid #444;")
        root.addWidget(self.bg_label,stretch=1)

        mr=QtWidgets.QHBoxLayout(); mr.addWidget(QtWidgets.QLabel("Select Mod to Download:"))
        self.mod_combo=QtWidgets.QComboBox()
        for n,u in ALL_MODS: self.mod_combo.addItem(n,u)
        mr.addWidget(self.mod_combo,1)
        db=QtWidgets.QPushButton("Open Download in Browser")
        db.clicked.connect(self._open_browser); mr.addWidget(db); root.addLayout(mr)

        self.log_area=QtWidgets.QTextEdit(); self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(210); root.addWidget(self.log_area)

        self.progress=QtWidgets.QProgressBar(); self.progress.setRange(0,0)
        self.progress.setVisible(False); self.progress.setFixedHeight(28)
        self.progress.setFormat("%p%"); root.addWidget(self.progress)

        # Primary row
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

        # Utility row
        br=QtWidgets.QHBoxLayout(); br.setSpacing(10)
        self.reset_btn=QtWidgets.QPushButton("Reset Proton Prefix")
        self.reset_btn.setToolTip(
            "Deletes proton_pfx/ and rewrites run_proton.sh.\n"
            "Use if the game won't launch or black bars disappeared."
        )
        self.reset_btn.setStyleSheet("background:#3a2a1a;color:#FFBB66;padding:8px 14px;border-radius:4px;border:1px solid #666;")
        self.reset_btn.clicked.connect(lambda:self._start("reset_prefix")); br.addWidget(self.reset_btn)
        root.addLayout(br)

        cred=QtWidgets.QLabel(
            '<font color="#CCC">Credits: </font><font color="#E55">TeamX</font><font color="#CCC"> [Textures]  </font>'
            '<font color="#E55">RESHDP</font><font color="#CCC"> [Textures]  </font>'
            '<font color="#E55">Gemini</font><font color="#CCC"> [Classic Rebirth]</font>'
        ); cred.setAlignment(QtCore.Qt.AlignCenter); root.addWidget(cred)

    def _all_action_buttons(self):
        return (self.ad_btn, self.auto_btn, self.reset_btn)

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
            w=self.bg_label.width() or 980; h=self.bg_label.height() or 300
            self.bg_label.setPixmap(QtGui.QPixmap(path).scaled(
                w,h,QtCore.Qt.KeepAspectRatioByExpanding,QtCore.Qt.SmoothTransformation))
        else: self.bg_label.setText("(banner unavailable)")

    def _cancel(self):
        if self.mod_worker and self.mod_worker.isRunning():
            self._log("Cancelling ...",True); self.mod_worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _update_progress(self,value,maximum):
        if maximum==0: self.progress.setRange(0,0); self.progress.setFormat("Working ...")
        else:
            self.progress.setRange(0,maximum); self.progress.setValue(value)
            self.progress.setFormat("%p%")

    def _start(self,mode):
        if self.mod_worker and self.mod_worker.isRunning():
            self._log("Already running.",True); return
        btn_map={"auto_download":self.ad_btn,"auto_mod":self.auto_btn,"reset_prefix":self.reset_btn}
        btn=btn_map[mode]
        self.mod_worker=ModWorker(self.current_key,mode,self)
        self.mod_worker.log.connect(self._log)
        self.mod_worker.progress.connect(self._update_progress)
        self.mod_worker.done.connect(lambda ok:self._done(ok,btn,mode))
        self.mod_worker.start()
        for b in self._all_action_buttons(): b.setEnabled(False)
        self.cancel_btn.setVisible(True); self.cancel_btn.setEnabled(True)
        self.progress.setRange(0,0); self.progress.setFormat("Working ...")
        self.progress.setVisible(True)

    def _done(self,ok,btn,mode):
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False); self.cancel_btn.setEnabled(True)
        for b in self._all_action_buttons(): b.setEnabled(True)
        if ok:
            btn.setStyleSheet("background:#2D6A2D;color:white;font-weight:bold;padding:12px 20px;")
            btn.setText("Done!  OK")
        else:
            btn.setStyleSheet("background:#6A2D2D;color:white;font-weight:bold;padding:12px 20px;")
            btn.setText("Failed -- see log")

    def _open_browser(self):
        webbrowser.open(self.mod_combo.currentData())
        self._log("Opened: "+self.mod_combo.currentText())

    def _show_help(self):
        d=QtWidgets.QDialog(self); d.setWindowTitle("Help"); d.setMinimumSize(560,500)
        d.setStyleSheet(
            "QDialog{background:#2E2E2E;}"
            "QTextEdit{background:#1A1A1A;color:#EEE;font-family:monospace;font-size:12px;border:1px solid #555;}"
            "QPushButton{background:#3A3A3A;border:1px solid #555;padding:6px 18px;border-radius:4px;color:#EEE;}"
            "QPushButton:hover{background:#4A4A4A;}"
        )
        lay=QtWidgets.QVBoxLayout(d)
        t=QtWidgets.QTextEdit(); t.setReadOnly(True); t.setPlainText(HELP_TEXT)
        t.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn); lay.addWidget(t)
        btn=QtWidgets.QPushButton("Close"); btn.clicked.connect(d.accept)
        lay.addWidget(btn,alignment=QtCore.Qt.AlignRight); d.exec_()

    @QtCore.pyqtSlot(str,bool)
    def _log(self,msg,error=False):
        col="#FF6666" if error else "#55FF55"
        self.log_area.append("<span style='color:%s;'>&gt; %s</span>"%(col,msg))
        sb=self.log_area.verticalScrollBar(); sb.setValue(sb.maximum())


if __name__=="__main__":
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
