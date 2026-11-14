"""Request/response schemas for the client integration API (/analyze, /status)."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class AnalyzeRequest(BaseModel):
    """
    Accepts JeevaCare's documented body ({radiologyId, imageUrl, patientId, metadata}) as well as the
    explicit form ({type, radiologyId|documentId, fileUrl, patientRef, ...}).
    """
    type: Optional[Literal["radiology", "document"]] = None
    radiologyId: Optional[str] = Field(default=None, min_length=1, max_length=255)
    documentId: Optional[str] = Field(default=None, min_length=1, max_length=255)
    fileUrl: Optional[HttpUrl] = None
    imageUrl: Optional[HttpUrl] = None
    patientRef: Optional[str] = Field(default=None, max_length=255)
    patientId: Optional[str] = Field(default=None, max_length=255)
    hospitalRef: Optional[str] = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalise(self):
        if (self.radiologyId is None) == (self.documentId is None):
            raise ValueError("send exactly one of radiologyId or documentId")
        inferred = "radiology" if self.radiologyId is not None else "document"
        if self.type not in (None, inferred):
            raise ValueError(f"type '{self.type}' does not match the id that was sent")
        self.type = inferred
        if (self.fileUrl is None) == (self.imageUrl is None):
            raise ValueError("send exactly one of fileUrl or imageUrl")
        return self

    @property
    def record_id(self) -> str:
        return self.radiologyId or self.documentId

    @property
    def file_url(self) -> str:
        return str(self.fileUrl or self.imageUrl)

    @property
    def patient_ref(self) -> Optional[str]:
        return self.patientRef or self.patientId


class AnalyzeResponse(BaseModel):
    jobId: str
    status: str
