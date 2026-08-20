"""离线包导出：uv export wheelhouse + ollama 模型 blob + docker save 镜像 tar。

导出后断网可用：uv pip install --no-index --find-links wheelhouse/ ...
                ollama create -f Modelfile（blob 已在 ~/.ollama/models）
                docker load < image.tar

用法：python -m infra.scripts.export_offline [输出目录]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUT = _ROOT / "dist" / "offline"
_MODELS = ["qwen3.5:4b", "qwen3.5:2b"]
_DOCKER_IMAGES = ["gitea/gitea:1.22"]


def export_wheelhouse(out_dir: Path) -> bool:
    """uv export → wheelhouse。"""
    wh = out_dir / "wheelhouse"
    wh.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["uv", "export", "--no-hashes", "--format", "requirements-txt"],
            cwd=str(_ROOT), check=True,
            stdout=open(wh / "requirements.txt", "w", encoding="utf-8"),
        )
        subprocess.run(
            ["uv", "pip", "download", "-r", str(wh / "requirements.txt"),
             "-o", str(wh)],
            cwd=str(_ROOT), check=True,
        )
    except subprocess.SubprocessError as e:
        print(f"✗ wheelhouse 导出失败: {e}", file=sys.stderr)
        return False
    print(f"✓ wheelhouse → {wh}")
    return True


def export_ollama_models(out_dir: Path) -> bool:
    """ollama 模型已在 ~/.ollama/models，记录清单供断网重建。"""
    manifest = out_dir / "ollama-models.txt"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(_MODELS) + "\n", encoding="utf-8")
    print(f"✓ ollama 模型清单 → {manifest}（模型 blob 已在 ~/.ollama/models）")
    return True


def export_docker_images(out_dir: Path) -> bool:
    """docker save 镜像 tar。"""
    if shutil.which("docker") is None:
        print("⚠ docker 未安装，跳过镜像导出", file=sys.stderr)
        return True
    img_dir = out_dir / "docker"
    img_dir.mkdir(parents=True, exist_ok=True)
    all_ok = True
    for image in _DOCKER_IMAGES:
        tar_name = image.replace("/", "_").replace(":", "_") + ".tar"
        tar_path = img_dir / tar_name
        try:
            subprocess.run(
                ["docker", "save", "-o", str(tar_path), image],
                check=True, capture_output=True,
            )
            print(f"✓ {image} → {tar_path}")
        except subprocess.SubprocessError as e:
            print(f"✗ {image} 导出失败: {e}", file=sys.stderr)
            all_ok = False
    return all_ok


def export_all(out_dir: Path) -> bool:
    """导出全套离线包。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"导出离线包到 {out_dir}")
    ok1 = export_wheelhouse(out_dir)
    ok2 = export_ollama_models(out_dir)
    ok3 = export_docker_images(out_dir)
    if ok1 and ok2 and ok3:
        print(f"\n✓ 离线包导出完成：{out_dir}")
        print("断网重建步骤：")
        print(f"  1. uv pip install --no-index --find-links {out_dir/'wheelhouse'}")
        print("  2. ollama pull（模型 blob 已在 ~/.ollama/models）")
        print(f"  3. docker load < {out_dir/'docker'}/<image>.tar")
        return True
    return False


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_OUT
    sys.exit(0 if export_all(out) else 1)
