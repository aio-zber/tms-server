"""
Alibaba Cloud OSS (Object Storage Service) integration.

Handles file uploads, thumbnail generation, and file validation.
"""
import os
import uuid
import io
import logging
from typing import Dict, Tuple, List, Optional
from pathlib import Path

import oss2
from PIL import Image
from fastapi import UploadFile, HTTPException, status
import magic

from app.config import settings

logger = logging.getLogger(__name__)


class OSSService:
    """Service for handling file uploads to Alibaba Cloud OSS."""

    def __init__(self):
        """Initialize OSS service with credentials from settings."""
        if not settings.oss_access_key_id or not settings.oss_access_key_secret:
            logger.warning("OSS credentials not configured. File upload will fail.")

        # Initialize OSS authentication
        self.auth = oss2.Auth(
            settings.oss_access_key_id,
            settings.oss_access_key_secret
        )

        # Initialize OSS bucket
        self.bucket = oss2.Bucket(
            self.auth,
            settings.oss_endpoint,
            settings.oss_bucket_name
        )

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent security issues.

        Removes path traversal characters, null bytes, and limits length.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace('/', '_').replace('\\', '_')

        # Remove null bytes
        filename = filename.replace('\x00', '')

        # Remove leading dots (hidden files)
        filename = filename.lstrip('.')

        # Limit length (max 255 chars for most filesystems)
        if len(filename) > 255:
            # Keep extension, truncate name
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                name, ext = name_parts
                max_name_len = 255 - len(ext) - 1
                filename = f"{name[:max_name_len]}.{ext}"
            else:
                filename = filename[:255]

        return filename

    def _generate_unique_filename(self, original_filename: str) -> str:
        """
        Generate unique filename with UUID prefix.

        Args:
            original_filename: Original filename

        Returns:
            Unique filename in format: {uuid}_{sanitized_original_name}
        """
        # Sanitize original filename
        safe_name = self._sanitize_filename(original_filename)

        # Extract extension
        path = Path(safe_name)
        name_stem = path.stem
        extension = path.suffix

        # Generate UUID
        unique_id = uuid.uuid4().hex[:12]  # Use first 12 chars of UUID

        # Construct unique filename
        return f"{unique_id}_{name_stem}{extension}"

    def validate_file(
        self,
        file: UploadFile,
        allowed_types: List[str],
        max_size: int
    ) -> None:
        """
        Validate file type and size.

        Args:
            file: Uploaded file
            allowed_types: List of allowed MIME types
            max_size: Maximum file size in bytes

        Raises:
            HTTPException: If file is invalid (wrong type or too large)
        """
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )

        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({file_size} bytes). Maximum: {max_size} bytes"
            )

        # Validate MIME type (server-side check using magic numbers)
        file_content = file.file.read(8192)  # Read first 8KB for magic number check
        file.file.seek(0)  # Reset

        try:
            mime = magic.Magic(mime=True)
            actual_mime_type = mime.from_buffer(file_content)
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}")
            # Fallback to content_type from client
            actual_mime_type = file.content_type

        # Check if MIME type is allowed
        if actual_mime_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type not supported: {actual_mime_type}. Allowed types: {', '.join(allowed_types)}"
            )

        logger.info(f"File validated: {file.filename} ({actual_mime_type}, {file_size} bytes)")

    async def upload_file(
        self,
        file: UploadFile,
        folder: str = "files"
    ) -> Dict[str, any]:
        """
        Upload file to OSS.

        Args:
            file: File to upload
            folder: OSS folder path (e.g., "messages/conv123")

        Returns:
            Dict with keys:
                - url: Public URL to access the file
                - file_size: File size in bytes
                - oss_key: OSS object key

        Raises:
            HTTPException: If upload fails
        """
        try:
            # Generate unique filename
            unique_filename = self._generate_unique_filename(file.filename)

            # Construct OSS key (path in bucket)
            oss_key = f"{folder}/{unique_filename}"

            # Read file content
            file_content = await file.read()
            file_size = len(file_content)

            # Upload to OSS (bucket ACL handles public access)
            result = self.bucket.put_object(
                oss_key,
                file_content,
                headers={
                    'Content-Type': file.content_type,
                    'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
                }
            )

            if result.status != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file to OSS: HTTP {result.status}"
                )

            # Construct public URL (use public endpoint, not internal)
            # Format: https://{bucket}.{public_endpoint}/{key}
            public_endpoint = settings.oss_endpoint.replace('-internal', '')
            public_url = f"https://{settings.oss_bucket_name}.{public_endpoint}/{oss_key}"

            logger.info(f"File uploaded successfully: {oss_key} ({file_size} bytes)")

            return {
                "url": public_url,
                "file_size": file_size,
                "oss_key": oss_key
            }

        except oss2.exceptions.OssError as e:
            logger.error(f"OSS upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"File storage service temporarily unavailable: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {str(e)}"
            )

    async def generate_image_thumbnail(
        self,
        image_bytes: bytes,
        folder: str = "thumbnails",
        size: Tuple[int, int] = (300, 300)
    ) -> Optional[Tuple[bytes, str]]:
        """
        Generate thumbnail for an image.

        Args:
            image_bytes: Original image bytes
            folder: OSS folder for thumbnails
            size: Thumbnail size (width, height)

        Returns:
            Tuple of (thumbnail_bytes, thumbnail_url) or None if generation fails
        """
        try:
            # Open image with Pillow
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary (PNG with transparency, etc.)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')

            # Generate thumbnail (maintains aspect ratio)
            image.thumbnail(size, Image.Resampling.LANCZOS)

            # Save thumbnail to bytes
            thumbnail_io = io.BytesIO()
            image.save(thumbnail_io, format='JPEG', quality=85, optimize=True)
            thumbnail_bytes = thumbnail_io.getvalue()

            # Generate unique filename for thumbnail
            thumbnail_filename = f"{uuid.uuid4().hex[:12]}_thumb.jpg"
            oss_key = f"{folder}/{thumbnail_filename}"

            # Upload thumbnail to OSS (bucket ACL handles public access)
            result = self.bucket.put_object(
                oss_key,
                thumbnail_bytes,
                headers={
                    'Content-Type': 'image/jpeg',
                    'Cache-Control': 'public, max-age=31536000',
                }
            )

            if result.status != 200:
                logger.warning(f"Failed to upload thumbnail to OSS: HTTP {result.status}")
                return None

            # Construct public URL (use public endpoint, not internal)
            public_endpoint = settings.oss_endpoint.replace('-internal', '')
            thumbnail_url = f"https://{settings.oss_bucket_name}.{public_endpoint}/{oss_key}"

            logger.info(f"Thumbnail generated: {oss_key} ({len(thumbnail_bytes)} bytes)")

            return (thumbnail_bytes, thumbnail_url)

        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")
            # Non-critical - return None to continue without thumbnail
            return None

    async def generate_video_thumbnail(
        self,
        video_url: str,
        folder: str = "thumbnails"
    ) -> Optional[str]:
        """
        Generate thumbnail for a video (placeholder - requires ffmpeg).

        NOTE: This is a placeholder implementation. Full implementation requires:
        - ffmpeg installed on server
        - Downloading video, extracting frame, uploading thumbnail

        Args:
            video_url: URL of uploaded video
            folder: OSS folder for thumbnails

        Returns:
            Thumbnail URL or None
        """
        # TODO: Implement video thumbnail generation with ffmpeg
        # For MVP, we can skip video thumbnails
        logger.info("Video thumbnail generation not implemented yet")
        return None

    def delete_file(self, oss_key: str) -> bool:
        """
        Delete file from OSS.

        Args:
            oss_key: OSS object key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.bucket.delete_object(oss_key)
            logger.info(f"File deleted: {oss_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {oss_key}: {e}")
            return False

    def get_file_url(self, oss_key: str) -> str:
        """
        Get public URL for an OSS object.

        Args:
            oss_key: OSS object key

        Returns:
            Public URL
        """
        public_endpoint = settings.oss_endpoint.replace('-internal', '')
        return f"https://{settings.oss_bucket_name}.{public_endpoint}/{oss_key}"

    def format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted string (e.g., "1.50 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
