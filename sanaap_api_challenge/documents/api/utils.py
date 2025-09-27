import hashlib
import mimetypes

from django.contrib.auth import get_user_model

User = get_user_model()


def get_file_content_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


def get_human_readable_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def get_file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_file_type(filename: str, allowed_types: list = None) -> bool:
    if not allowed_types:
        allowed_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/csv",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        ]

    content_type = get_file_content_type(filename)
    return content_type in allowed_types


def sanitize_filename(filename: str) -> str:
    import re

    # Remove path separators and other dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = name[:max_name_length] + ("." + ext if ext else "")

    return filename.strip()


def generate_unique_filename(
    original_filename: str,
    user_id: int,
    prefix: str = "doc",
) -> str:
    import uuid
    from datetime import datetime

    # Sanitize original filename
    safe_filename = sanitize_filename(original_filename)
    extension = get_file_extension(safe_filename)

    # Generate unique identifier
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4().hex[:8])

    # Create filename: prefix_userid_timestamp_uniqueid.ext
    filename_parts = [prefix, str(user_id), timestamp, unique_id]
    filename = "_".join(filename_parts)

    if extension:
        filename += f".{extension}"

    return filename


def parse_file_size_query(size_str: str) -> int | None:
    if not size_str:
        return None

    import re

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([KMGT]?B)$", size_str.upper().strip())
    if not match:
        return None

    number, unit = match.groups()
    number = float(number)

    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }

    return int(number * multipliers.get(unit, 1))


def get_mime_type_display_name(content_type: str) -> str:
    type_mapping = {
        "application/pdf": "PDF Document",
        "application/msword": "Word Document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word Document",
        "application/vnd.ms-excel": "Excel Spreadsheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel Spreadsheet",
        "text/plain": "Text File",
        "text/csv": "CSV File",
        "image/jpeg": "JPEG Image",
        "image/png": "PNG Image",
        "image/gif": "GIF Image",
        "image/webp": "WebP Image",
        "application/zip": "ZIP Archive",
        "application/x-rar-compressed": "RAR Archive",
    }

    return type_mapping.get(content_type, content_type.split("/")[-1].upper() + " File")


def check_user_document_quota(
    user: User,
    max_documents: int = 1000,
) -> tuple[bool, int]:
    from sanaap_api_challenge.documents.models import Document

    current_count = Document.objects.filter(owner=user, is_active=True).count()
    return current_count < max_documents, current_count


def check_user_storage_quota(
    user: User,
    max_storage_bytes: int = 10 * 1024**3,
) -> tuple[bool, int]:
    from django.db.models import Sum

    from sanaap_api_challenge.documents.models import Document

    current_usage = (
        Document.objects.filter(owner=user, is_active=True).aggregate(
            total_size=Sum("file_size"),
        )["total_size"]
        or 0
    )

    return current_usage < max_storage_bytes, current_usage
