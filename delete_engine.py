import os
import shutil
from pathlib import Path

DELETE_MODE = os.environ.get("MONSTER_DELETE_MODE", "permanent").strip().lower()
VALID_MODES = {"permanent", "trash"}


class UnsafeDeleteError(RuntimeError):
    """Raised when a protected or ambiguous path is selected for deletion."""


def _norm(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        resolved = path.absolute()
    return os.path.normcase(os.path.normpath(str(resolved)))


def _is_same_or_child(candidate: str, protected: str) -> bool:
    if candidate == protected:
        return True
    try:
        return os.path.commonpath([candidate, protected]) == protected
    except (ValueError, OSError):
        return False


def _protected_exact_paths() -> list[Path]:
    # Protect the user profile root itself, but allow normal files inside it.
    paths = [Path.home()]
    public = os.environ.get("PUBLIC")
    if public:
        paths.append(Path(public))
    return paths


def _protected_tree_paths() -> list[Path]:
    # Everything below these OS/application roots is protected as well.
    paths: list[Path] = []
    for env_name in (
        "SystemRoot",
        "WINDIR",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramData",
    ):
        value = os.environ.get(env_name)
        if value:
            paths.append(Path(value))
    return paths


def validate_target(path: str | os.PathLike[str]) -> Path:
    if not path:
        raise UnsafeDeleteError("没有收到目标文件路径。请通过右键菜单启动程序。")

    target = Path(path)
    if not target.exists() and not target.is_symlink():
        raise FileNotFoundError(f"目标不存在：{target}")

    target_norm = _norm(target)

    # Block a bare filesystem root regardless of platform/drive.
    anchor = Path(target.anchor) if target.anchor else None
    if anchor and target_norm == _norm(anchor):
        raise UnsafeDeleteError(f"拒绝删除磁盘根目录：{target}")

    for protected in _protected_exact_paths():
        if target_norm == _norm(protected):
            raise UnsafeDeleteError(f"安全保护：拒绝删除关键目录本身：{target}")

    for protected in _protected_tree_paths():
        if _is_same_or_child(target_norm, _norm(protected)):
            raise UnsafeDeleteError(f"安全保护：拒绝删除系统/程序关键目录中的内容：{target}")

    return target


def delete_path(path: str | os.PathLike[str], mode: str | None = None) -> str:
    """Delete ``path`` and return a human-readable result message.

    ``permanent`` really removes the selected file/folder. ``trash`` sends it to
    the OS recycle bin. Permanent mode is intentionally the default for this
    project because the UI presents an explicit irreversible confirmation.
    """

    selected_mode = (mode or DELETE_MODE).strip().lower()
    if selected_mode not in VALID_MODES:
        raise ValueError(f"不支持的删除模式：{selected_mode}")

    target = validate_target(path)

    if selected_mode == "trash":
        from send2trash import send2trash

        send2trash(str(target))
        return f"已移入回收站：{target}"

    # For symlinks/junction-like links, only remove the link itself.
    if target.is_symlink():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return f"已永久删除：{target}"
