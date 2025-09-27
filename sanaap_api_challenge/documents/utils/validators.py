import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy


def get_file_category(filename: str) -> str:
    _, ext = os.path.splitext(filename.lower())

    document_exts = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".rtf",
        ".txt",
        ".csv",
    }
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"}
    audio_exts = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}
    video_exts = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"}
    archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
    code_exts = {".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml"}

    if ext in document_exts:
        return "document"
    if ext in image_exts:
        return "image"
    if ext in audio_exts:
        return "audio"
    if ext in video_exts:
        return "video"
    if ext in archive_exts:
        return "archive"
    if ext in code_exts:
        return "code"
    return "default"


def validate_file_extension(uploaded_file: UploadedFile) -> None:
    if not uploaded_file.name:
        raise ValidationError(gettext_lazy("File must have a name"))

    allowed_extensions = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])
    if not allowed_extensions:
        return  # No restrictions if not configured

    _, ext = os.path.splitext(uploaded_file.name.lower())

    if ext not in allowed_extensions:
        message = gettext_lazy(
            "File type '%(extension)s' is not allowed. Allowed types: %(allowed)s",
        ) % {"extension": ext, "allowed": ", ".join(allowed_extensions)}
        raise ValidationError(message)


def validate_file_size(uploaded_file: UploadedFile) -> None:
    if not uploaded_file.name:
        raise ValidationError(gettext_lazy("File must have a name"))

    max_file_sizes = getattr(settings, "MAX_FILE_SIZES", {})
    if not max_file_sizes:
        return  # No restrictions if not configured

    file_category = get_file_category(uploaded_file.name)
    max_size = max_file_sizes.get(file_category, max_file_sizes.get("default", 0))

    if max_size > 0 and uploaded_file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        actual_size_mb = uploaded_file.size / (1024 * 1024)

        message = gettext_lazy(
            "File size (%(actual_size).1f MB) exceeds maximum allowed size "
            "for %(category)s files (%(max_size).1f MB)",
        ) % {
            "actual_size": actual_size_mb,
            "max_size": max_size_mb,
            "category": file_category,
        }
        raise ValidationError(message)


def validate_file_content(uploaded_file: UploadedFile) -> None:
    if not uploaded_file.name:
        raise ValidationError(gettext_lazy("File must have a name"))

    # Check for suspicious file names
    suspicious_patterns = [
        "..",  # Directory traversal
        "/",  # Path separator
        "\\",  # Windows path separator
        "\x00",  # Null byte
    ]

    for pattern in suspicious_patterns:
        if pattern in uploaded_file.name:
            message = gettext_lazy(
                "File name contains suspicious characters: %(filename)s",
            ) % {"filename": uploaded_file.name}
            raise ValidationError(message)

    dangerous_extensions = {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scr",
        ".vbs",
        ".js",
        ".jar",
        ".app",
        ".deb",
        ".pkg",
        ".dmg",
        ".php",
        ".asp",
        ".jsp",
    }

    _, ext = os.path.splitext(uploaded_file.name.lower())
    if ext in dangerous_extensions:
        message = gettext_lazy(
            "Executable file types are not allowed: %(extension)s",
        ) % {"extension": ext}
        raise ValidationError(message)

    # Basic magic number validation for common file types
    try:
        uploaded_file.seek(0)
        file_header = uploaded_file.read(10)  # Read first 10 bytes
        uploaded_file.seek(0)  # Reset file pointer

        # PDF files should start with %PDF
        if uploaded_file.name.lower().endswith(".pdf"):
            if not file_header.startswith(b"%PDF"):
                raise ValidationError(
                    gettext_lazy("PDF file appears to be corrupted or fake"),
                )

        # ZIP files should start with PK
        elif uploaded_file.name.lower().endswith(".zip"):
            if not file_header.startswith(b"PK"):
                raise ValidationError(
                    gettext_lazy("ZIP file appears to be corrupted or fake"),
                )

    except Exception:
        # If we can't read the file, let other validators handle it
        pass


def validate_uploaded_file(uploaded_file: UploadedFile) -> tuple[bool, list[str]]:
    errors = []

    try:
        validate_file_extension(uploaded_file)
    except ValidationError as e:
        errors.append(str(e))

    try:
        validate_file_size(uploaded_file)
    except ValidationError as e:
        errors.append(str(e))

    try:
        validate_file_content(uploaded_file)
    except ValidationError as e:
        errors.append(str(e))

    return len(errors) == 0, errors


def get_upload_limits_info() -> dict:
    max_file_sizes = getattr(settings, "MAX_FILE_SIZES", {})
    allowed_extensions = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])

    size_limits_mb = {}
    for category, size_bytes in max_file_sizes.items():
        size_limits_mb[category] = round(size_bytes / (1024 * 1024), 1)

    return {
        "max_file_sizes_mb": size_limits_mb,
        "allowed_extensions": allowed_extensions,
        "max_memory_size_mb": getattr(settings, "FILE_UPLOAD_MAX_MEMORY_SIZE", 0)
        / (1024 * 1024),
        "max_fields": getattr(settings, "DATA_UPLOAD_MAX_NUMBER_FIELDS", 1000),
    }


def create_file_validator(
    max_size_bytes: int | None = None,
    allowed_extensions: list[str] | None = None,
    require_content_validation: bool = True,
):
    def validator(uploaded_file: UploadedFile) -> None:
        # Size validation
        if max_size_bytes and uploaded_file.size > max_size_bytes:
            max_size_mb = max_size_bytes / (1024 * 1024)
            actual_size_mb = uploaded_file.size / (1024 * 1024)
            message = gettext_lazy(
                "File size (%(actual_size).1f MB) exceeds maximum allowed "
                "size (%(max_size).1f MB)",
            ) % {"actual_size": actual_size_mb, "max_size": max_size_mb}
            raise ValidationError(message)

        # Extension validation
        if allowed_extensions and uploaded_file.name:
            _, ext = os.path.splitext(uploaded_file.name.lower())
            if ext not in allowed_extensions:
                message = gettext_lazy(
                    "File type '%(extension)s' is not allowed. "
                    "Allowed types: %(allowed)s",
                ) % {"extension": ext, "allowed": ", ".join(allowed_extensions)}
                raise ValidationError(message)

        # Content validation
        if require_content_validation:
            validate_file_content(uploaded_file)

    return validator
