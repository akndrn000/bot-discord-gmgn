"""Tes regresi konfigurasi deploy Railway.

Mengunci agar kesalahan start command berbentuk
``PYTHONPATH=src python -m gmgn_bot`` tidak terulang: Railway menjalankan
start command TANPA shell, sehingga ``PYTHONPATH=src`` dianggap nama
executable dan deploy gagal di tahap "Create container" dengan error
``The executable `pythonpath=src` could not be found``.

Tes ini tidak menyentuh logika bot.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Hanya file yang isinya DIEKSEKUSI sebagai perintah (bukan dokumentasi).
# README/.env.example boleh menyebut pola lama sebagai peringatan.
DEPLOY_FILES = ("Procfile", "Dockerfile", "railway.json", "railway.toml")


def test_no_pythonpath_assignment_in_deploy_files():
    """Tidak ada `PYTHONPATH=...` di file konfigurasi deploy."""
    offenders = [
        name
        for name in DEPLOY_FILES
        if (ROOT / name).exists() and "PYTHONPATH=" in (ROOT / name).read_text(encoding="utf-8")
    ]
    assert offenders == [], f"PYTHONPATH= ditemukan di: {offenders}"


def test_railway_json_start_command():
    """railway.json mengunci builder Dockerfile dan start command bersih."""
    data = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert data["build"]["builder"] == "DOCKERFILE"
    start = data["deploy"]["startCommand"]
    assert start == "python -m gmgn_bot"
    assert "=" not in start, "start command tidak boleh mengandung assignment env"


def test_dockerfile_self_contained():
    """Image bisa jalan tanpa PYTHONPATH: paket di-pip-install + CMD exec form."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.10" in text
    assert "COPY src/" in text
    assert "pip install ." in text.replace("--no-cache-dir ", "")
    assert 'CMD ["python", "-m", "gmgn_bot"]' in text
    assert "PYTHONPATH" not in text


def test_procfile_clean_or_absent():
    """Bila Procfile ada, isinya harus perintah bersih tanpa prefix env."""
    procfile = ROOT / "Procfile"
    if procfile.exists():
        assert procfile.read_text(encoding="utf-8").strip() == "worker: python -m gmgn_bot"
