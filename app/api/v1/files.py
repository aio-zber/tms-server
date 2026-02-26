"""
File Proxy API routes.
Provides a proxy endpoint for fetching encrypted files from OSS,
bypassing CORS restrictions on direct OSS access from the browser.
"""
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import httpx

from app.config import settings
from app.core.database import get_db
from app.core.security import extract_token_from_header, SecurityException
from app.core.jwt_validator import decode_nextauth_jwt, JWTValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter()


async def _authenticate_proxy(
    token: Optional[str],
    authorization: Optional[str],
    db: AsyncSession,
) -> None:
    """
    Authenticate a proxy request via Authorization header OR ?token= query param.
    The token query param is needed for <img src> / <video src> usage since browsers
    cannot send custom headers for media elements.
    """
    auth_header = authorization
    if not auth_header and token:
        auth_header = f"Bearer {token}"
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        raw_token = extract_token_from_header(auth_header)
        decode_nextauth_jwt(raw_token)  # validates signature + expiry
    except (SecurityException, JWTValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/proxy",
    summary="Proxy file download from OSS",
    description=(
        "Fetches a file from Alibaba OSS and streams it back with proper headers. "
        "Solves CORS issues when the browser needs to fetch encrypted files for decryption. "
        "Accepts auth via Authorization header OR ?token= query param (for <img>/<video> src usage). "
        "Passes Range headers through to OSS for efficient partial fetching by the browser's fetch() API."
    ),
)
async def proxy_file(
    url: str = Query(..., description="OSS file URL to proxy"),
    token: Optional[str] = Query(None, description="Bearer token — for <img>/<video> src where headers can't be set"),
    authorization: Optional[str] = Header(None),
    range: Optional[str] = Header(None, alias="range"),
    db: AsyncSession = Depends(get_db),
):
    """
    Proxy an OSS file URL through the backend to avoid CORS blocks.
    Only allows URLs from our configured OSS bucket.

    Passes the browser's Range header through to OSS so large files can be
    fetched in chunks (Alibaba OSS supports byte-range requests). This is the
    key to fast decryption: fetch() with { headers: { Range: 'bytes=0-' } }
    gets a 206 response with Content-Length set, allowing progress tracking.

    Uses no-store cache policy to prevent ERR_CACHE_WRITE_FAILURE on large files.
    """
    await _authenticate_proxy(token, authorization, db)

    # Validate the URL belongs to our OSS bucket
    bucket_name = settings.oss_bucket_name
    oss_endpoint = settings.oss_endpoint.replace('-internal', '')

    allowed_hosts = [
        f"{bucket_name}.{oss_endpoint}",
        f"{bucket_name}.oss-",  # Partial match for regional endpoints
    ]

    url_is_allowed = any(host in url for host in allowed_hosts)
    if not url_is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="URL is not from the allowed storage bucket"
        )

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)

    # Forward Range header to OSS if present — enables partial content responses (HTTP 206)
    request_headers: dict[str, str] = {}
    if range:
        request_headers["Range"] = range

    try:
        client = httpx.AsyncClient(timeout=timeout)
        oss_response = await client.send(
            client.build_request("GET", url, headers=request_headers),
            stream=True,
        )
        oss_response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch file from storage: {e.response.status_code}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to storage: {str(e)}"
        )

    content_type = oss_response.headers.get("content-type", "application/octet-stream")

    # Build response headers to pass back to browser
    response_headers: dict[str, str] = {
        # no-store prevents ERR_CACHE_WRITE_FAILURE on large encrypted files.
        # Encrypted blobs must never be served stale — decryption requires the exact bytes.
        "Cache-Control": "no-store",
        # Tell nginx not to buffer this response — required for streaming to work
        # through a reverse proxy without buffering the entire body first.
        "X-Accel-Buffering": "no",
        # Allow browsers to use Range requests (needed for fetch() progress tracking)
        "Accept-Ranges": "bytes",
    }

    # Pass through Content-Length and Content-Range from OSS so the browser can
    # track download progress and handle partial content (206) correctly.
    for header in ("content-length", "content-range"):
        value = oss_response.headers.get(header)
        if value:
            response_headers[header.title()] = value

    async def _stream_oss() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in oss_response.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await oss_response.aclose()
            await client.aclose()

    return StreamingResponse(
        _stream_oss(),
        status_code=oss_response.status_code,
        media_type=content_type,
        headers=response_headers,
    )
