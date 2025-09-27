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


def get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
