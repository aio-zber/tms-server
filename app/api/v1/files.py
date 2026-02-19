"""
File Proxy API routes.
Provides a proxy endpoint for fetching encrypted files from OSS,
bypassing CORS restrictions on direct OSS access from the browser.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import httpx

from app.config import settings
from app.dependencies import get_current_user

router = APIRouter()


@router.get(
    "/proxy",
    summary="Proxy file download from OSS",
    description="Fetches a file from Alibaba OSS and streams it back with proper headers. "
                "Solves CORS issues when the browser needs to fetch encrypted files for decryption.",
)
async def proxy_file(
    url: str = Query(..., description="OSS file URL to proxy"),
    current_user: dict = Depends(get_current_user),
):
    """
    Proxy an OSS file URL through the backend to avoid CORS blocks.
    Only allows URLs from our configured OSS bucket.
    """
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

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Determine content type from OSS response
            content_type = response.headers.get("content-type", "application/octet-stream")

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Cache-Control": "private, max-age=3600",
                },
            )
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
