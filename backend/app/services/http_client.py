from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from ..errors import ScanError

USER_AGENT = "RepoReady/1.0 (git repo integration health check)"
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class JsonResult:
    status: int
    data: Any
    headers: httpx.Headers
    url: str


@dataclass
class DownloadResult:
    path: Path
    bytes_written: int
    final_url: str


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _validate_https_host(url: str, allowed_hosts: tuple[str, ...] | None) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ScanError("UNSAFE_URL", "仅允许 HTTPS 请求", http_status=400)
    if parts.username or parts.password:
        raise ScanError("UNSAFE_URL", "链接中不允许包含用户信息", http_status=400)
    if parts.port not in (None, 443):
        raise ScanError("UNSAFE_URL", "链接中不允许使用非标准端口", http_status=400)
    host = (parts.hostname or "").lower()
    if not host:
        raise ScanError("UNSAFE_URL", "无法解析链接主机", http_status=400)
    if allowed_hosts is not None and host not in {h.lower() for h in allowed_hosts}:
        raise ScanError(
            "UNSAFE_URL",
            f"请求目标不在允许列表中：{host}",
            http_status=400,
        )
    return host


def _retry_after(headers: httpx.Headers) -> int | None:
    raw = headers.get("retry-after")
    if raw:
        try:
            return max(0, int(float(raw)))
        except ValueError:
            pass
    reset = headers.get("x-ratelimit-reset")
    if reset:
        try:
            return max(0, int(float(reset) - time.time()))
        except ValueError:
            pass
    return None


def _backoff(attempt: int) -> None:
    time.sleep(min(2.0, 0.35 * (2**attempt)) + random.uniform(0.0, 0.2))


class HttpClient:
    def __init__(self, timeout_seconds: float = 60.0, max_redirects: int = 5) -> None:
        self.max_redirects = max_redirects
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=10.0,
                read=timeout_seconds,
                write=30.0,
                pool=timeout_seconds,
            ),
            follow_redirects=False,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "identity",
            },
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
    ) -> JsonResult:
        current = url
        attempts = 0
        redirects = 0
        while True:
            _validate_https_host(current, allowed_hosts)
            try:
                response = self._client.get(current, headers=headers, params=params)
            except httpx.TimeoutException as exc:
                if attempts < 2:
                    attempts += 1
                    _backoff(attempts)
                    continue
                raise ScanError(
                    "NETWORK_TIMEOUT",
                    "请求仓库平台 API 超时，请稍后重试",
                    http_status=504,
                ) from exc
            except httpx.HTTPError as exc:
                if attempts < 2:
                    attempts += 1
                    _backoff(attempts)
                    continue
                raise ScanError(
                    "NETWORK_ERROR",
                    "无法连接仓库平台 API，请检查网络后重试",
                    http_status=502,
                ) from exc

            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location or redirects >= self.max_redirects:
                    raise ScanError(
                        "REDIRECT_BLOCKED",
                        "仓库平台返回了无法跟随的重定向",
                        http_status=502,
                    )
                current = urljoin(current, location)
                params = None  # Do not forward tokens to a redirect target.
                redirects += 1
                continue

            if response.status_code in RETRY_STATUSES and attempts < 2:
                attempts += 1
                _backoff(attempts)
                continue

            data: Any = None
            if response.content:
                try:
                    data = response.json()
                except (ValueError, json.JSONDecodeError):
                    data = None
            return JsonResult(
                status=response.status_code,
                data=data,
                headers=response.headers,
                url=_safe_url(str(response.url)),
            )

    def stream_to_file(
        self,
        url: str,
        dest: Path,
        *,
        max_bytes: int,
        headers: dict[str, str] | None = None,
        allowed_hosts: tuple[str, ...] | None = None,
    ) -> DownloadResult:
        current = url
        attempts = 0
        while True:
            redirects = 0
            failed_for_retry = False
            while True:
                _validate_https_host(current, allowed_hosts)
                try:
                    with self._client.stream("GET", current, headers=headers) as response:
                        if response.status_code in REDIRECT_STATUSES:
                            location = response.headers.get("location")
                            if not location or redirects >= self.max_redirects:
                                raise ScanError(
                                    "REDIRECT_BLOCKED",
                                    "归档下载重定向次数过多",
                                    http_status=502,
                                )
                            current = urljoin(current, location)
                            redirects += 1
                            continue

                        if response.status_code in RETRY_STATUSES and attempts < 2:
                            failed_for_retry = True
                        elif response.status_code != 200:
                            raise ScanError(
                                "DOWNLOAD_FAILED",
                                f"归档下载失败（HTTP {response.status_code}）",
                                http_status=502,
                                retry_after=_retry_after(response.headers),
                            )
                        else:
                            length_header = response.headers.get("content-length")
                            if length_header:
                                try:
                                    if int(length_header) > max_bytes:
                                        raise ScanError(
                                            "ARCHIVE_TOO_LARGE",
                                            "仓库归档体积超过限制（50MB），已停止下载",
                                            http_status=413,
                                        )
                                except ValueError:
                                    pass
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            written = 0
                            try:
                                with dest.open("wb") as handle:
                                    for chunk in response.iter_bytes(chunk_size=64 * 1024):
                                        if not chunk:
                                            continue
                                        written += len(chunk)
                                        if written > max_bytes:
                                            raise ScanError(
                                                "ARCHIVE_TOO_LARGE",
                                                "仓库归档体积超过限制（50MB），已停止下载",
                                                http_status=413,
                                            )
                                        handle.write(chunk)
                            except Exception:
                                try:
                                    dest.unlink(missing_ok=True)
                                except OSError:
                                    pass
                                raise
                            return DownloadResult(
                                path=dest,
                                bytes_written=written,
                                final_url=_safe_url(current),
                            )
                except httpx.TimeoutException as exc:
                    if attempts < 2:
                        failed_for_retry = True
                    else:
                        raise ScanError(
                            "DOWNLOAD_TIMEOUT",
                            "归档下载超时，请稍后重试",
                            http_status=504,
                        ) from exc
                except httpx.HTTPError as exc:
                    if attempts < 2:
                        failed_for_retry = True
                    else:
                        raise ScanError(
                            "DOWNLOAD_FAILED",
                            "归档下载网络错误，请稍后重试",
                            http_status=502,
                        ) from exc

                if failed_for_retry and attempts < 2:
                    attempts += 1
                    _backoff(attempts)
                    break
                if failed_for_retry:
                    raise ScanError(
                        "DOWNLOAD_FAILED",
                        "归档下载失败，请稍后重试",
                        http_status=502,
                    )
            if not failed_for_retry:
                break
