from django.conf import settings
from django.core.files.uploadhandler import TemporaryFileUploadHandler


class SecureFileUploadHandler(TemporaryFileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.max_size = getattr(
            settings,
            "DATA_UPLOAD_MAX_MEMORY_SIZE",
            1024 * 1024 * 1024,
        )  # 1GB default
        self.current_size = 0

    def receive_data_chunk(self, raw_data, start):
        self.current_size += len(raw_data)

        # Enforce hard limit to prevent DoS
        if self.current_size > self.max_size:
            # Stop the upload immediately
            raise Exception(
                f"Upload too large. Maximum size is {self.max_size // (1024 * 1024)} MB",
            )

        return super().receive_data_chunk(raw_data, start)

    def file_complete(self, file_size):
        if file_size > self.max_size:
            raise Exception(
                f"File too large. Maximum size is {self.max_size // (1024 * 1024)} MB",
            )

        return super().file_complete(file_size)


class MemoryEfficientUploadHandler(TemporaryFileUploadHandler):
    """
    Upload handler that always uses temporary files, never memory.

    This prevents large files from consuming server memory.
    """

    def new_file(self, *args, **kwargs):
        """
        Always create a temporary file, regardless of size.
        """
        super().new_file(*args, **kwargs)
        # Force temporary file creation even for small files
        if hasattr(self, "file") and hasattr(self.file, "multiple_chunks"):
            # Override the multiple_chunks method to always return True
            # This forces Django to use temporary files instead of memory
            original_multiple_chunks = self.file.multiple_chunks
            self.file.multiple_chunks = lambda chunk_size=None: True
