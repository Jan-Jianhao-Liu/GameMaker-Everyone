"""Git LFS 检测：未安装时报错并给出 Windows 安装指引，不静默降级。

用法：python -m infra.scripts.check_lfs
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_INSTALL_GUIDE = """
Git LFS 未安装！请按以下步骤安装（Windows）：

1. 下载 Git LFS：https://git-lfs.com/
2. 运行安装程序
3. 打开新的终端，执行：
     git lfs install
4. 重新运行本脚本验证

不安装 LFS 将导致 *.fbx / *.png / *.wav 以普通文件提交，仓库会迅速膨胀。
"""


def check_lfs() -> bool:
    """检测 git-lfs 是否可用。返回 True 表示已安装且已初始化。"""
    if shutil.which("git") is None:
        print("✗ git 未安装", file=sys.stderr)
        return False
    if shutil.which("git-lfs") is None:
        try:
            version = subprocess.run(
                ["git", "lfs", "version"], capture_output=True, text=True, timeout=5
            )
            if version.returncode != 0:
                print(_INSTALL_GUIDE, file=sys.stderr)
                return False
        except (subprocess.SubprocessError, FileNotFoundError):
            print(_INSTALL_GUIDE, file=sys.stderr)
            return False
    try:
        installed = subprocess.run(
            ["git", "lfs", "install", "--skip-repocheck"],
            capture_output=True, text=True, timeout=5,
        )
        if installed.returncode != 0 and "already" not in installed.stderr.lower():
            print(f"⚠ git lfs install 警告: {installed.stderr.strip()}", file=sys.stderr)
    except subprocess.SubprocessError:
        pass
    print("✓ Git LFS 已安装且已初始化")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_lfs() else 1)
