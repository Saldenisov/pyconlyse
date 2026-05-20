import os
import posixpath
from pathlib import PurePosixPath
from typing import Dict, Iterable
from urllib.parse import quote, unquote, urlparse


def is_smb_path(path: str) -> bool:
    raw = str(path or "").strip()
    return raw.startswith("smb://") or raw.startswith("\\\\") or raw.startswith("//")


def normalize_smb_path(path: str) -> str:
    raw = str(path or "").strip()
    if raw.startswith("smb://"):
        parsed = urlparse(raw)
        server = parsed.netloc
        parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    else:
        parts = [part for part in raw.replace("\\", "/").strip("/").split("/") if part]
        if not parts:
            raise ValueError("SMB path is empty")
        server = parts.pop(0)

    if not server or not parts:
        raise ValueError("SMB path must include server and share")

    share = parts[0]
    tail = "/".join(quote(part) for part in parts[1:])
    base = f"smb://{server}/{quote(share)}"
    return f"{base}/{tail}" if tail else base


def split_smb_path(path: str):
    normalized = normalize_smb_path(path)
    parsed = urlparse(normalized)
    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if not parsed.netloc or not parts:
        raise ValueError("SMB path must include server and share")
    return parsed.netloc, parts[0], "/".join(parts[1:])


def smb_name(path: str) -> str:
    _server, share, remote_path = split_smb_path(path)
    if remote_path:
        return PurePosixPath(remote_path).name
    return share


def smb_suffix(path: str) -> str:
    return PurePosixPath(smb_name(path)).suffix.lower()


def smb_join(folder: str, name: str) -> str:
    server, share, remote_path = split_smb_path(folder)
    joined = posixpath.normpath(posixpath.join("/", remote_path, name)).strip("/")
    parts = [quote(part) for part in joined.split("/") if part]
    tail = "/".join(parts)
    return f"smb://{server}/{quote(share)}" + (f"/{tail}" if tail else "")


def smb_to_unc(path: str) -> str:
    server, share, remote_path = split_smb_path(path)
    unc = f"\\\\{server}\\{share}"
    if remote_path:
        unc += "\\" + remote_path.replace("/", "\\")
    return unc


def smb_is_within(path: str, root: str) -> bool:
    server, share, remote_path = split_smb_path(path)
    root_server, root_share, root_remote_path = split_smb_path(root)
    if server.lower() != root_server.lower() or share.lower() != root_share.lower():
        return False
    candidate = posixpath.normpath("/" + remote_path).strip("/").lower()
    root_candidate = posixpath.normpath("/" + root_remote_path).strip("/").lower()
    return candidate == root_candidate or candidate.startswith(root_candidate.rstrip("/") + "/")


def _smbclient():
    try:
        import smbclient
    except ImportError as exc:
        raise ValueError(
            "SMB support requires package 'smbprotocol'. Install it in pyconlyse39."
        ) from exc
    return smbclient


def _register_session(server: str) -> None:
    username = os.environ.get("PYCONLYSE_SMB_USERNAME")
    password = os.environ.get("PYCONLYSE_SMB_PASSWORD")
    domain = os.environ.get("PYCONLYSE_SMB_DOMAIN")
    if not username:
        return
    kwargs = {"username": username, "password": password or ""}
    if domain:
        kwargs["domain"] = domain
    _smbclient().register_session(server, **kwargs)


def _smb_value_error(path: str, exc: Exception) -> ValueError:
    return ValueError(f"Could not access SMB path '{normalize_smb_path(path)}': {exc}")


def smb_isdir(path: str) -> bool:
    try:
        server, _share, _remote_path = split_smb_path(path)
        _register_session(server)
        return _smbclient().path.isdir(smb_to_unc(path))
    except ValueError:
        raise
    except Exception as exc:
        raise _smb_value_error(path, exc) from exc


def smb_isfile(path: str) -> bool:
    try:
        server, _share, _remote_path = split_smb_path(path)
        _register_session(server)
        return _smbclient().path.isfile(smb_to_unc(path))
    except ValueError:
        raise
    except Exception as exc:
        raise _smb_value_error(path, exc) from exc


def smb_listdir(folder: str) -> Iterable[Dict[str, object]]:
    try:
        server, _share, _remote_path = split_smb_path(folder)
        _register_session(server)
        entries = list(_smbclient().scandir(smb_to_unc(folder)))
    except ValueError:
        raise
    except Exception as exc:
        raise _smb_value_error(folder, exc) from exc

    for entry in entries:
        name = entry.name
        yield {
            "name": name,
            "path": smb_join(folder, name),
            "is_dir": entry.is_dir(),
            "is_file": entry.is_file(),
        }


def copy_smb_file_to_local(smb_path: str, local_path) -> int:
    try:
        server, _share, _remote_path = split_smb_path(smb_path)
        _register_session(server)
        total = 0
        with _smbclient().open_file(smb_to_unc(smb_path), mode="rb") as source:
            with open(local_path, "wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    total += len(chunk)
        return total
    except ValueError:
        raise
    except Exception as exc:
        raise _smb_value_error(smb_path, exc) from exc
