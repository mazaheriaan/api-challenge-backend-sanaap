"""
MinIO client utility for file storage operations.

This module provides a wrapper around the MinIO Python client
for handling file upload, download, and management operations.
"""

import logging
from typing import Optional, BinaryIO, List
from urllib3.exceptions import ResponseError

from django.conf import settings
from minio import Minio
from minio.error import S3Error


logger = logging.getLogger(__name__)


class MinIOClient:
    """
    MinIO client wrapper for file storage operations.

    Provides methods for uploading, downloading, deleting files,
    and managing buckets in MinIO object storage.
    """

    def __init__(self):
        """Initialize MinIO client with settings from Django configuration."""
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_HTTPS,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Error creating bucket {self.bucket_name}: {e}")
            raise

    def upload_file(
        self,
        object_name: str,
        file_data: BinaryIO,
        file_size: int,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """
        Upload a file to MinIO.

        Args:
            object_name: Name of the object in MinIO
            file_data: File-like object containing the data to upload
            file_size: Size of the file in bytes
            content_type: MIME type of the file

        Returns:
            True if upload successful, False otherwise
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type,
            )
            logger.info(f"Successfully uploaded {object_name} to {self.bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Error uploading file {object_name}: {e}")
            return False

    def upload_file_from_path(
        self, object_name: str, file_path: str, content_type: Optional[str] = None
    ) -> bool:
        """
        Upload a file from local path to MinIO.

        Args:
            object_name: Name of the object in MinIO
            file_path: Local path to the file
            content_type: MIME type of the file (auto-detected if None)

        Returns:
            True if upload successful, False otherwise
        """
        try:
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type,
            )
            logger.info(f"Successfully uploaded {file_path} as {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error uploading file from path {file_path}: {e}")
            return False

    def download_file(self, object_name: str, file_path: str) -> bool:
        """
        Download a file from MinIO to local path.

        Args:
            object_name: Name of the object in MinIO
            file_path: Local path where the file will be saved

        Returns:
            True if download successful, False otherwise
        """
        try:
            self.client.fget_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
            )
            logger.info(f"Successfully downloaded {object_name} to {file_path}")
            return True
        except S3Error as e:
            logger.error(f"Error downloading file {object_name}: {e}")
            return False

    def get_file_data(self, object_name: str) -> Optional[bytes]:
        """
        Get file data as bytes from MinIO.

        Args:
            object_name: Name of the object in MinIO

        Returns:
            File data as bytes, or None if error occurred
        """
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Successfully retrieved data for {object_name}")
            return data
        except S3Error as e:
            logger.error(f"Error getting file data for {object_name}: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from MinIO.

        Args:
            object_name: Name of the object to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            logger.info(f"Successfully deleted {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting file {object_name}: {e}")
            return False

    def list_files(self, prefix: str = "") -> List[str]:
        """
        List files in the bucket.

        Args:
            prefix: Filter objects by prefix

        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
            )
            file_list = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(file_list)} files with prefix '{prefix}'")
            return file_list
        except S3Error as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            return []

    def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in MinIO.

        Args:
            object_name: Name of the object to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            return True
        except S3Error:
            return False

    def get_file_info(self, object_name: str) -> Optional[dict]:
        """
        Get file information (metadata) from MinIO.

        Args:
            object_name: Name of the object

        Returns:
            Dictionary with file info, or None if file doesn't exist
        """
        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata,
            }
        except S3Error as e:
            logger.error(f"Error getting file info for {object_name}: {e}")
            return None


# Global instance for easy import
minio_client = MinIOClient()
