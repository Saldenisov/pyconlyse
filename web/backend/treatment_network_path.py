import os
import ntpath
import posixpath
import time
from pathlib import PurePosixPath
from typing import Dict, Iterable
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4


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


def smb_parent(path: str) -> str:
    server, share, remote_path = split_smb_path(path)
    parent = posixpath.dirname(posixpath.normpath("/" + remote_path)).strip("/")
    parts = [quote(part) for part in parent.split("/") if part]
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
    if not root_candidate:
        return True
    return candidate == root_candidate or candidate.startswith(root_candidate.rstrip("/") + "/")


def _iter_smb_local_maps():
    raw_maps = os.environ.get("PYCONLYSE_SMB_LOCAL_MAP", "")
    if not raw_maps and os.path.isdir("E:\\"):
        raw_maps = "smb://10.20.30.202/e/=E:\\"
    for raw_item in raw_maps.replace("\n", "|").split("|"):
        item = raw_item.strip()
        if not item or "=" not in item:
            continue
        smb_prefix, local_prefix = item.split("=", 1)
        smb_prefix = smb_prefix.strip()
        local_prefix = local_prefix.strip().strip("\"'")
        if not smb_prefix or not local_prefix:
            continue
        try:
            normalized = normalize_smb_path(smb_prefix)
        except ValueError:
            continue
        yield normalized.rstrip("/"), local_prefix


def smb_to_local_path(path: str):
    normalized = normalize_smb_path(path)
    for smb_prefix, local_prefix in _iter_smb_local_maps():
        if normalized == smb_prefix:
            tail = ""
        elif normalized.startswith(smb_prefix + "/"):
            tail = normalized[len(smb_prefix) + 1:]
        else:
            continue

        parts = [unquote(part) for part in tail.split("/") if part]
        if "\\" in local_prefix or ntpath.splitdrive(local_prefix)[0]:
            return ntpath.normpath(ntpath.join(local_prefix, *parts))
        return os.path.abspath(os.path.join(os.path.expanduser(local_prefix), *parts))
    return None


def is_mapped_smb_path(path: str) -> bool:
    try:
        return smb_to_local_path(path) is not None
    except ValueError:
        return False


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
    if domain and "\\" not in username and "@" not in username:
        username = f"{domain}\\{username}"
    try:
        connection_timeout = max(
            1.0,
            float(os.environ.get("PYCONLYSE_SMB_CONNECTION_TIMEOUT", "8")),
        )
    except ValueError:
        connection_timeout = 8.0
    kwargs = {
        "username": username,
        "password": password or "",
        "connection_timeout": connection_timeout,
    }
    _smbclient().register_session(server, **kwargs)


def _smb_value_error(path: str, exc: Exception) -> ValueError:
    return ValueError(f"Could not access SMB path '{normalize_smb_path(path)}': {exc}")


def _smb_retry_count() -> int:
    try:
        return max(1, int(os.environ.get("PYCONLYSE_SMB_RETRIES", "6")))
    except ValueError:
        return 6


def _smb_retry_delay() -> float:
    try:
        return max(0.0, float(os.environ.get("PYCONLYSE_SMB_RETRY_DELAY", "0.5")))
    except ValueError:
        return 0.5


def _smb_lock_retry_count() -> int:
    try:
        return max(1, int(os.environ.get("PYCONLYSE_SMB_LOCK_RETRIES", "15")))
    except ValueError:
        return 15


def _smb_lock_retry_delay() -> float:
    try:
        return max(0.0, float(os.environ.get("PYCONLYSE_SMB_LOCK_RETRY_DELAY", "2.0")))
    except ValueError:
        return 2.0


def _is_smb_lock_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "c0000043" in message
        or "being used by another process" in message
        or "sharing violation" in message
    )


def _is_smb_credit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "credits" in message
        and "request requires" in message
        and "available" in message
    )


def _reset_smb_connection_cache() -> None:
    try:
        reset_connection_cache = getattr(_smbclient(), "reset_connection_cache", None)
        if reset_connection_cache:
            reset_connection_cache()
    except Exception:
        pass


def _smb_locked_value_error(path: str, exc: Exception, action: str, attempts: int) -> ValueError:
    return ValueError(
        f"SMB {action} is locked by another process after {attempts} attempts: "
        f"{normalize_smb_path(path)}. Close the file in other software and retry. {exc}"
    )


def smb_isdir(path: str) -> bool:
    attempts = _smb_retry_count()
    delay = _smb_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            server, _share, _remote_path = split_smb_path(path)
            _register_session(server)
            return _smbclient().path.isdir(smb_to_unc(path))
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc) and attempt < attempts:
                _reset_smb_connection_cache()
                time.sleep(delay * attempt)
                continue
            raise _smb_value_error(path, exc) from exc
    return False


def smb_isfile(path: str) -> bool:
    attempts = _smb_retry_count()
    delay = _smb_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            server, _share, _remote_path = split_smb_path(path)
            _register_session(server)
            return _smbclient().path.isfile(smb_to_unc(path))
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc) and attempt < attempts:
                _reset_smb_connection_cache()
                time.sleep(delay * attempt)
                continue
            raise _smb_value_error(path, exc) from exc
    return False


def smb_listdir(folder: str) -> Iterable[Dict[str, object]]:
    attempts = _smb_retry_count()
    delay = _smb_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            server, _share, _remote_path = split_smb_path(folder)
            _register_session(server)
            entries = list(_smbclient().scandir(smb_to_unc(folder)))
            listing = []
            for entry in entries:
                name = entry.name
                is_file = entry.is_file()
                is_dir = entry.is_dir()
                try:
                    size_bytes = int(entry.stat().st_size) if is_file else 0
                except Exception:
                    size_bytes = 0
                listing.append({
                    "name": name,
                    "path": smb_join(folder, name),
                    "is_dir": is_dir,
                    "is_file": is_file,
                    "size_bytes": size_bytes,
                })
            return listing
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc) and attempt < attempts:
                _reset_smb_connection_cache()
                time.sleep(delay * attempt)
                continue
            raise _smb_value_error(folder, exc) from exc
    return []


def copy_smb_file_to_local(smb_path: str, local_path, progress_callback=None) -> int:
    attempts = _smb_lock_retry_count()
    delay = _smb_lock_retry_delay()
    for attempt in range(1, attempts + 1):
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
                        if progress_callback:
                            progress_callback(total)
            return total
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc):
                if attempt < attempts:
                    _reset_smb_connection_cache()
                    time.sleep(min(delay, 0.5) * attempt)
                    continue
                raise _smb_value_error(smb_path, exc) from exc
            if _is_smb_lock_error(exc):
                if attempt < attempts:
                    time.sleep(delay)
                    continue
                raise _smb_locked_value_error(smb_path, exc, "source file", attempts) from exc
            raise _smb_value_error(smb_path, exc) from exc


def copy_local_file_to_smb(local_path, smb_path: str, progress_callback=None) -> int:
    attempts = _smb_lock_retry_count()
    delay = _smb_lock_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            server, _share, _remote_path = split_smb_path(smb_path)
            _register_session(server)
            total = 0
            with open(local_path, "rb") as source:
                with _smbclient().open_file(smb_to_unc(smb_path), mode="wb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
                        total += len(chunk)
                        if progress_callback:
                            progress_callback(total)
            return total
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc):
                if attempt < attempts:
                    _reset_smb_connection_cache()
                    time.sleep(min(delay, 0.5) * attempt)
                    continue
                raise _smb_value_error(smb_path, exc) from exc
            if _is_smb_lock_error(exc):
                if attempt < attempts:
                    time.sleep(delay)
                    continue
                raise _smb_locked_value_error(smb_path, exc, "target file", attempts) from exc
            raise _smb_value_error(smb_path, exc) from exc


def copy_local_file_to_smb_atomic(local_path, smb_path: str, progress_callback=None) -> int:
    temp_path = smb_join(
        smb_parent(smb_path),
        f"~{uuid4().hex[:8]}.tmp",
    )
    try:
        bytes_written = copy_local_file_to_smb(
            local_path,
            temp_path,
            progress_callback=progress_callback,
        )
        server, _share, _remote_path = split_smb_path(smb_path)
        _register_session(server)
        attempts = _smb_lock_retry_count()
        delay = _smb_lock_retry_delay()
        for attempt in range(1, attempts + 1):
            try:
                _smbclient().replace(smb_to_unc(temp_path), smb_to_unc(smb_path))
                return bytes_written
            except Exception as exc:
                if _is_smb_credit_error(exc) and attempt < attempts:
                    _reset_smb_connection_cache()
                    time.sleep(min(delay, 0.5) * attempt)
                    continue
                if _is_smb_lock_error(exc) and attempt < attempts:
                    time.sleep(delay)
                    continue
                raise
    except Exception as exc:
        try:
            smb_remove(temp_path)
        except Exception:
            pass
        if _is_smb_lock_error(exc):
            raise ValueError(
                f"SMB target is locked by another process: {normalize_smb_path(smb_path)}. "
                "Close the file in other software and retry. Original file was not changed."
            ) from exc
        raise _smb_value_error(smb_path, exc) from exc


def smb_remove(path: str) -> None:
    attempts = _smb_lock_retry_count()
    delay = _smb_lock_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            server, _share, _remote_path = split_smb_path(path)
            _register_session(server)
            _smbclient().remove(smb_to_unc(path))
            return
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc):
                if attempt < attempts:
                    _reset_smb_connection_cache()
                    time.sleep(min(delay, 0.5) * attempt)
                    continue
                raise _smb_value_error(path, exc) from exc
            if _is_smb_lock_error(exc):
                if attempt < attempts:
                    time.sleep(delay)
                    continue
                raise _smb_locked_value_error(path, exc, "delete target", attempts) from exc
            raise _smb_value_error(path, exc) from exc


def smb_rename(source_path: str, target_path: str) -> None:
    """Rename a file within one SMB share without replacing an existing target."""
    source_server, source_share, _source_remote_path = split_smb_path(source_path)
    target_server, target_share, _target_remote_path = split_smb_path(target_path)
    if (
        source_server.lower() != target_server.lower()
        or source_share.lower() != target_share.lower()
    ):
        raise ValueError("SMB rename source and target must be on the same share")

    attempts = _smb_lock_retry_count()
    delay = _smb_lock_retry_delay()
    for attempt in range(1, attempts + 1):
        try:
            _register_session(source_server)
            _smbclient().rename(smb_to_unc(source_path), smb_to_unc(target_path))
            return
        except ValueError:
            raise
        except Exception as exc:
            if _is_smb_credit_error(exc):
                if attempt < attempts:
                    _reset_smb_connection_cache()
                    time.sleep(min(delay, 0.5) * attempt)
                    continue
                raise _smb_value_error(source_path, exc) from exc
            if _is_smb_lock_error(exc):
                if attempt < attempts:
                    time.sleep(delay)
                    continue
                raise _smb_locked_value_error(source_path, exc, "rename target", attempts) from exc
            raise _smb_value_error(source_path, exc) from exc
