import logging
from io import BytesIO

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _

from sanaap_api_challenge.documents.models import Access
from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.utils.validators import validate_uploaded_file
from sanaap_api_challenge.utils.minio_client import minio_client

from .api.utils import calculate_file_hash
from .api.utils import generate_unique_filename

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_document_upload(
    self,
    document_id,
    file_data,
    user_id,
    ip_address="",
    user_agent="",
):
    """
    Process document upload asynchronously.

    Args:
        document_id: Document instance ID
        file_data: Dictionary containing file information
        user_id: User ID who uploaded the file
        ip_address: IP address of the client
        user_agent: User agent string

    Returns:
        dict: Result information with success status and details
    """
    try:
        # Get document and user instances
        document = Document.objects.get(id=document_id)
        user = User.objects.get(id=user_id)

        # Update status to processing
        document.update_upload_status(
            "processing",
            progress={"step": "validating", "progress": 10},
        )

        # Recreate file object for validation
        file_content = file_data["content"]
        file_obj = InMemoryUploadedFile(
            file=BytesIO(file_content),
            field_name=None,
            name=file_data["name"],
            content_type=file_data["content_type"],
            size=len(file_content),
            charset=None,
        )

        # Validate file
        is_valid, errors = validate_uploaded_file(file_obj)
        if not is_valid:
            error_message = "; ".join(errors)
            document.update_upload_status("failed", error_message=error_message)

            # Log failed upload
            Access.objects.create(
                document=document,
                user=user,
                action="upload",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message=error_message,
            )

            return {
                "success": False,
                "error": error_message,
                "document_id": document_id,
            }

        # Update progress
        document.update_upload_status(
            "processing",
            progress={"step": "calculating_hash", "progress": 30},
        )

        # Calculate file hash
        file_hash = calculate_file_hash(file_content)

        # Check for duplicates
        existing = (
            Document.objects.filter(file_hash=file_hash).exclude(id=document_id).first()
        )
        if existing:
            error_message = _(
                "A document with identical content already exists: %(title)s",
            ) % {"title": existing.title}
            document.update_upload_status("failed", error_message=error_message)

            # Log failed upload
            Access.objects.create(
                document=document,
                user=user,
                action="upload",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message=error_message,
            )

            return {
                "success": False,
                "error": error_message,
                "document_id": document_id,
            }

        # Update progress
        document.update_upload_status(
            "processing",
            progress={"step": "uploading_to_storage", "progress": 50},
        )

        # Generate unique file path for MinIO storage
        from datetime import datetime

        now = datetime.now()
        unique_filename = generate_unique_filename(
            file_data["name"],
            user_id,
            prefix="doc",
        )
        file_path = f"documents/{now.year}/{now.month:02d}/{now.day:02d}/{user_id}/{unique_filename}"

        # Upload to MinIO
        file_obj_for_upload = BytesIO(file_content)
        success = minio_client.upload_file(
            object_name=file_path,
            file_data=file_obj_for_upload,
            file_size=len(file_content),
            content_type=file_data["content_type"] or "application/octet-stream",
        )

        if not success:
            error_message = _("Failed to upload file to storage")
            document.update_upload_status("failed", error_message=error_message)

            # Log failed upload
            Access.objects.create(
                document=document,
                user=user,
                action="upload",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message=error_message,
            )

            return {
                "success": False,
                "error": error_message,
                "document_id": document_id,
            }

        # Update progress
        document.update_upload_status(
            "processing",
            progress={"step": "finalizing", "progress": 90},
        )

        # Update document with final information
        document.file_path = file_path
        document.file_size = len(file_content)
        document.content_type = file_data["content_type"] or "application/octet-stream"
        document.file_hash = file_hash
        document.upload_status = "completed"
        document.upload_progress = {"step": "completed", "progress": 100}
        document.upload_error_message = ""
        document.save(
            update_fields=[
                "file_path",
                "file_size",
                "content_type",
                "file_hash",
                "upload_status",
                "upload_progress",
                "upload_error_message",
                "modified",
            ],
        )

        # Log successful upload
        Access.objects.create(
            document=document,
            user=user,
            action="upload",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        logger.info(f"Successfully processed upload for document {document_id}")

        return {
            "success": True,
            "document_id": document_id,
            "file_path": file_path,
            "file_size": len(file_content),
            "file_hash": file_hash,
        }

    except Document.DoesNotExist:
        error_message = f"Document with ID {document_id} not found"
        logger.error(error_message)
        return {"success": False, "error": error_message, "document_id": document_id}

    except User.DoesNotExist:
        error_message = f"User with ID {user_id} not found"
        logger.error(error_message)
        try:
            document = Document.objects.get(id=document_id)
            document.update_upload_status("failed", error_message=error_message)
        except Document.DoesNotExist:
            pass
        return {"success": False, "error": error_message, "document_id": document_id}

    except Exception as e:
        error_message = f"Unexpected error processing upload: {e!s}"
        logger.exception(error_message)

        try:
            document = Document.objects.get(id=document_id)
            document.update_upload_status("failed", error_message=error_message)

            # Clean up uploaded file if it exists
            if hasattr(document, "file_path") and document.file_path:
                minio_client.delete_file(document.file_path)

            # Log failed upload
            if user_id:
                user = User.objects.get(id=user_id)
                Access.objects.create(
                    document=document,
                    user=user,
                    action="upload",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message=error_message,
                )
        except Exception as cleanup_error:
            logger.exception(f"Failed to clean up after error: {cleanup_error}")

        return {"success": False, "error": error_message, "document_id": document_id}


@shared_task
def cleanup_failed_uploads():
    """
    Cleanup failed uploads that have been stuck in processing state.
    This task should be run periodically to clean up orphaned uploads.
    """
    from datetime import timedelta

    from django.utils import timezone

    # Find documents that have been processing for more than 1 hour
    cutoff_time = timezone.now() - timedelta(hours=1)
    stuck_documents = Document.objects.filter(
        upload_status__in=["pending", "processing"],
        modified__lt=cutoff_time,
    )

    cleaned_count = 0
    for document in stuck_documents:
        try:
            # Clean up file if it exists
            if document.file_path:
                minio_client.delete_file(document.file_path)

            # Mark as failed
            document.update_upload_status(
                "failed",
                error_message="Upload timed out and was cleaned up",
            )

            cleaned_count += 1
            logger.info(f"Cleaned up stuck upload for document {document.id}")

        except Exception as e:
            logger.error(f"Failed to clean up document {document.id}: {e}")

    logger.info(f"Cleaned up {cleaned_count} stuck uploads")
    return {"cleaned_count": cleaned_count}
