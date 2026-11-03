"""
File Storage Service

Provides abstraction for local and S3-compatible object storage.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import uuid
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import StorageError

logger = get_logger(__name__)


class StorageService:
    """Service for file storage operations."""
    
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER
        self.local_path = Path(settings.STORAGE_LOCAL_PATH)
        
        if self.provider == "local":
            self._initialize_local_storage()
        elif self.provider == "s3":
            self._initialize_s3_storage()
        else:
            raise StorageError(
                f"Unsupported storage provider: {self.provider}",
                details={"provider": self.provider}
            )
    
    def _initialize_local_storage(self):
        """Initialize local file storage."""
        try:
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Local storage initialized: {self.local_path}")
        except Exception as e:
            raise StorageError(
                f"Failed to initialize local storage: {str(e)}",
                details={"path": str(self.local_path)}
            )
    
    def _initialize_s3_storage(self):
        """Initialize S3-compatible storage."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.STORAGE_ENDPOINT,
                aws_access_key_id=settings.STORAGE_ACCESS_KEY,
                aws_secret_access_key=settings.STORAGE_SECRET_KEY,
                region_name=settings.STORAGE_REGION,
            )
            
            # Verify bucket exists
            try:
                self.s3_client.head_bucket(Bucket=settings.STORAGE_BUCKET)
                logger.info(f"S3 storage initialized: {settings.STORAGE_BUCKET}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    # Create bucket if it doesn't exist
                    self.s3_client.create_bucket(Bucket=settings.STORAGE_BUCKET)
                    logger.info(f"Created S3 bucket: {settings.STORAGE_BUCKET}")
                else:
                    raise
        
        except ImportError:
            raise StorageError(
                "boto3 required for S3 storage",
                details={"install": "pip install boto3"}
            )
        except Exception as e:
            raise StorageError(
                f"Failed to initialize S3 storage: {str(e)}",
                details={"bucket": settings.STORAGE_BUCKET}
            )
    
    def generate_storage_key(
        self,
        analysis_id: str,
        filename: str,
        prefix: Optional[str] = None,
    ) -> str:
        """
        Generate a unique storage key for a file.
        
        Args:
            analysis_id: Analysis ID
            filename: Original filename
            prefix: Optional prefix (e.g., 'documents', 'images')
        
        Returns:
            Storage key
        """
        # Extract file extension
        path = Path(filename)
        extension = path.suffix.lower()
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        safe_name = f"{path.stem}_{unique_id}{extension}"
        
        # Build key
        if prefix:
            key = f"{prefix}/{analysis_id}/{safe_name}"
        else:
            key = f"{analysis_id}/{safe_name}"
        
        return key
    
    def save_file(
        self,
        source_path: Path,
        storage_key: str,
    ) -> Dict[str, Any]:
        """
        Save file to storage.
        
        Args:
            source_path: Path to source file
            storage_key: Storage key/path
        
        Returns:
            Storage metadata
        """
        try:
            if not source_path.exists():
                raise StorageError(f"Source file not found: {source_path}")
            
            file_size = source_path.stat().st_size
            
            if self.provider == "local":
                result = self._save_file_local(source_path, storage_key)
            elif self.provider == "s3":
                result = self._save_file_s3(source_path, storage_key)
            else:
                raise StorageError(f"Unsupported provider: {self.provider}")
            
            result.update({
                "storage_key": storage_key,
                "storage_provider": self.provider,
                "file_size": file_size,
            })
            
            logger.info(f"File saved: {storage_key} ({file_size} bytes)")
            return result
        
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"File save failed: {str(e)}", exc_info=True)
            raise StorageError(
                f"Failed to save file: {str(e)}",
                details={"storage_key": storage_key}
            )
    
    def _save_file_local(self, source_path: Path, storage_key: str) -> Dict[str, Any]:
        """Save file to local storage."""
        # Create full path
        dest_path = self.local_path / storage_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        shutil.copy2(source_path, dest_path)
        
        return {
            "local_path": str(dest_path),
        }
    
    def _save_file_s3(self, source_path: Path, storage_key: str) -> Dict[str, Any]:
        """Save file to S3 storage."""
        # Upload file
        self.s3_client.upload_file(
            str(source_path),
            settings.STORAGE_BUCKET,
            storage_key,
        )
        
        return {
            "bucket": settings.STORAGE_BUCKET,
            "region": settings.STORAGE_REGION,
        }
    
    def get_file(
        self,
        storage_key: str,
        dest_path: Optional[Path] = None,
    ) -> Path:
        """
        Retrieve file from storage.
        
        Args:
            storage_key: Storage key
            dest_path: Optional destination path (temp file if not provided)
        
        Returns:
            Path to retrieved file
        """
        try:
            if not dest_path:
                # Create temp file
                dest_path = Path(f"/tmp/{uuid.uuid4()}_{Path(storage_key).name}")
            
            if self.provider == "local":
                source_path = self.local_path / storage_key
                if not source_path.exists():
                    raise StorageError(f"File not found: {storage_key}")
                shutil.copy2(source_path, dest_path)
            
            elif self.provider == "s3":
                self.s3_client.download_file(
                    settings.STORAGE_BUCKET,
                    storage_key,
                    str(dest_path),
                )
            
            logger.info(f"File retrieved: {storage_key}")
            return dest_path
        
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"File retrieval failed: {str(e)}", exc_info=True)
            raise StorageError(
                f"Failed to retrieve file: {str(e)}",
                details={"storage_key": storage_key}
            )
    
    def delete_file(self, storage_key: str) -> bool:
        """
        Delete file from storage.
        
        Args:
            storage_key: Storage key
        
        Returns:
            True if deleted successfully
        """
        try:
            if self.provider == "local":
                file_path = self.local_path / storage_key
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"File deleted: {storage_key}")
                    return True
                else:
                    logger.warning(f"File not found for deletion: {storage_key}")
                    return False
            
            elif self.provider == "s3":
                self.s3_client.delete_object(
                    Bucket=settings.STORAGE_BUCKET,
                    Key=storage_key,
                )
                logger.info(f"File deleted: {storage_key}")
                return True
        
        except Exception as e:
            logger.error(f"File deletion failed: {str(e)}", exc_info=True)
            raise StorageError(
                f"Failed to delete file: {str(e)}",
                details={"storage_key": storage_key}
            )
    
    def generate_presigned_url(
        self,
        storage_key: str,
        expiration_seconds: int = 3600,
    ) -> Optional[str]:
        """
        Generate presigned URL for file access (S3 only).
        
        Args:
            storage_key: Storage key
            expiration_seconds: URL expiration time
        
        Returns:
            Presigned URL or None for local storage
        """
        if self.provider == "local":
            # Local storage doesn't support presigned URLs
            return None
        
        elif self.provider == "s3":
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.STORAGE_BUCKET,
                        'Key': storage_key,
                    },
                    ExpiresIn=expiration_seconds,
                )
                logger.info(f"Presigned URL generated: {storage_key}")
                return url
            except Exception as e:
                logger.error(f"Presigned URL generation failed: {str(e)}")
                raise StorageError(
                    f"Failed to generate presigned URL: {str(e)}",
                    details={"storage_key": storage_key}
                )
        
        return None
