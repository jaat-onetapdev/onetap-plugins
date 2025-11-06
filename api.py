# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess, tempfile, shutil, json, os

# ------------- CONFIGURACIÓN BÁSICA (EDITABLE) -------------
BASE_DIR = Path.home() / "onetapdev"   
PLUGINS_DIR = BASE_DIR / "plugins"
GIT_BIN = "git"                         

# Crea carpetas necesarias
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="onetapdev", version="0.0.1")

# Registro en memoria: plugin_id -> metadata mínima
REGISTRY: Dict[str, Dict[str, Any]] = {}


# ----------------- UTILIDADES -----------------
def load_manifest(plugin_dir: Path) -> Dict[str, Any]:
    """
    Carga manifest.yaml o manifest.json del plugin.
    Si usas solo JSON, basta con manifest.json y evitas instalar PyYAML.
    """
    yml = plugin_dir / "manifest.yaml"
    jsn = plugin_dir / "manifest.json"

    if jsn.exists():
        with jsn.open("r", encoding="utf-8") as f:
            return json.load(f)

    if yml.exists():
        try:
            import yaml  # requiere: pip install pyyaml
        except ImportError as e:
            raise HTTPException(500, "Falta PyYAML: pip install pyyaml") from e
        with yml.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    raise HTTPException(400, f"No se encontró manifest.yaml ni manifest.json en {plugin_dir}")

def scan_plugins_registry() -> None:
    """
    Recorre PLUGINS_DIR y reconstruye REGISTRY con lo instalado.
    """
    REGISTRY.clear()
    for entry in PLUGINS_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            manifest = load_manifest(entry)
            pid = manifest.get("id") or entry.name
            REGISTRY[pid] = {
                "plugin_id": pid,
                "name": manifest.get("name", pid),
                "version": manifest.get("version", "0.0.0"),
                "path": str(entry.resolve()),
            }
        except Exception as e:
            # No frenamos toda la carga si un plugin está roto
            print(f"[WARN] Falló registro de {entry.name}: {e}")

# ----------------- MODELOS -----------------
class InstallFromGitRequest(BaseModel):
    git_url: str
    ref: Optional[str] = None        # rama / tag / commit
    subdir: Optional[str] = None     # si el plugin está en subcarpeta


# ----------------- ENDPOINTS -----------------
@app.on_event("startup")
def _startup():
    scan_plugins_registry()

@app.get("/plugins/installed")
def list_installed():
    """
    Devuelve la lista de plugins instalados.
    Formato mínimo y estable para tu frontend.
    """
    items = list(REGISTRY.values())
    return {"items": items, "total": len(items)}

@app.post("/plugins/install-from-git")
def install_from_git(req: InstallFromGitRequest):
    """
    Instala un plugin clonando un repo Git y copiándolo a /plugins/{plugin_id}
    - Lee manifest (yaml o json) para obtener id/name/version
    - Si ya existía, lo reemplaza (comportamiento simple para MVP)
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="labox_git_"))
    try:
        # 1) Clonar
        clone_cmd = [GIT_BIN, "clone", req.git_url, str(tmpdir)]
        subprocess.run(clone_cmd, check=True, capture_output=True, text=True)

        # 2) Checkout ref (si se indicó)
        if req.ref:
            subprocess.run([GIT_BIN, "-C", str(tmpdir), "fetch", "--all"], check=False)
            subprocess.run([GIT_BIN, "-C", str(tmpdir), "checkout", req.ref], check=True, capture_output=True, text=True)

        # 3) Determinar carpeta del plugin
        plugin_root = tmpdir / req.subdir if req.subdir else tmpdir
        if not plugin_root.exists():
            raise HTTPException(400, f"subdir no existe dentro del repo: {req.subdir}")

        # 4) Leer manifest
        manifest = load_manifest(plugin_root)
        plugin_id = manifest.get("id") or plugin_root.name

        # 5) Destino final
        dest = PLUGINS_DIR / plugin_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(plugin_root, dest)

        # 6) Actualizar registro en memoria
        scan_plugins_registry()

        meta = REGISTRY[plugin_id]
        return {
            "plugin_id": meta["plugin_id"],
            "name": meta["name"],
            "version": meta["version"],
            "path": meta["path"],
            "status": "installed"
        }

    except subprocess.CalledProcessError as e:
        # Error de git (clone/checkout)
        raise HTTPException(400, f"Git error: {e.stderr or e.stdout}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
