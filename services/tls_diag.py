"""
One-time TLS diagnostic probe, run at startup, for the
"[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate" error seen when
services/zeabur.py calls gateway.zeabur.com from inside a deployed container.

httpx (used everywhere else in this codebase) verifies against certifi's
bundled CA list, not the OS trust store — so a bare "missing ca-certificates
package" is not the likely cause here. A self-signed leaf cert usually means
something between the container and gateway.zeabur.com is intercepting the
TLS connection. This probe logs exactly what got presented so that evidence
(fingerprint, subject/issuer, resolved IP) is available in the deploy logs
for a Zeabur support ticket, without needing shell access to the container.

Non-fatal: any failure here is logged and swallowed, never blocks startup.
"""

import hashlib
import logging
import socket
import ssl

log = logging.getLogger(__name__)


def _sha256_fingerprint(der_bytes: bytes) -> str:
    return hashlib.sha256(der_bytes).hexdigest()


def diagnose_tls(host: str, port: int = 443) -> None:
    log.info(f"[tls_diag] Probing {host}:{port} — OpenSSL {ssl.OPENSSL_VERSION}")

    try:
        import certifi
        log.info(f"[tls_diag] certifi bundle: {certifi.where()}")
    except ImportError:
        log.info("[tls_diag] certifi not installed (unexpected — httpx depends on it)")

    try:
        ips = sorted({ai[4][0] for ai in socket.getaddrinfo(host, port)})
        log.info(f"[tls_diag] DNS resolved {host} -> {ips}")
    except Exception as exc:
        log.warning(f"[tls_diag] DNS resolution failed: {exc}")
        return

    # Unverified handshake — succeeds even against a self-signed/interception
    # cert, so we can inspect exactly what's being presented.
    try:
        ctx = ssl._create_unverified_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
                log.info(
                    f"[tls_diag] Unverified handshake OK — TLS {ssock.version()}, "
                    f"cipher {ssock.cipher()[0]}, peer cert SHA-256 fingerprint "
                    f"{_sha256_fingerprint(der)}"
                )
    except Exception as exc:
        log.warning(f"[tls_diag] Unverified handshake itself failed (not just verification): {exc}")
        return

    # Verified handshake — mirrors what httpx does by default, to capture
    # the exact error MonitoringMiku hits in normal operation.
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                log.info("[tls_diag] Verified handshake OK — chain trusted, no interception detected")
    except ssl.SSLCertVerificationError as exc:
        log.warning(f"[tls_diag] Verified handshake failed as expected: {exc}")
    except Exception as exc:
        log.warning(f"[tls_diag] Verified handshake failed with unexpected error: {exc}")
