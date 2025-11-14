from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: str | None = None
    color: str | None = None


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class LinkBase(BaseModel):
    url: HttpUrl
    title: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=10000)
    image_url: str | None = None


class LinkCreate(LinkBase):
    tags: list[str] = Field(default_factory=list, max_length=10)
    collection: str | None = Field(None, max_length=100)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate and sanitize tag names"""
        if not v:
            return []
        # Limit number of tags
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        # Validate each tag
        sanitized = []
        for tag in v:
            if not isinstance(tag, str):
                continue
            # Strip and limit length
            clean_tag = tag.strip()[:100]
            if clean_tag and len(clean_tag) >= 2:
                sanitized.append(clean_tag)
        return sanitized[:10]
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """Validate and sanitize title"""
        if v is None:
            return None
        # Strip whitespace and limit length
        clean = v.strip()
        if not clean:
            return None
        return clean[:500]
    
    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Validate and sanitize notes"""
        if v is None:
            return None
        # Strip whitespace and limit length
        clean = v.strip()
        if not clean:
            return None
        return clean[:10000]
    
    @field_validator('collection')
    @classmethod
    def validate_collection(cls, v: str | None) -> str | None:
        """Validate and sanitize collection name"""
        if v is None:
            return None
        # Strip whitespace and limit length
        clean = v.strip()
        if not clean or len(clean) < 2:
            return None
        return clean[:100]


class LinkUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    collection: str | None = None
    image_url: str | None = None


class LinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str | None
    notes: str | None
    image_url: str | None
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead]
    collection: CollectionRead | None

class PaginatedLinks(BaseModel):
    items: list[LinkRead]
    total: int
    page: int
    page_size: int
