from __future__ import annotations

from datetime import datetime

from slugify import slugify
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


link_tag_table = Table(
    "link_tags",
    Base.metadata,
    Column("link_id", ForeignKey("links.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    links: Mapped[list[Link]] = relationship("Link", back_populates="collection", lazy="selectin")


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50))  # Icon name/identifier
    color: Mapped[str | None] = mapped_column(String(20))  # Color for the icon

    links: Mapped[list[Link]] = relationship(
        "Link", secondary=link_tag_table, back_populates="tags", lazy="selectin"
    )


class Link(Base, TimestampMixin):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)  # Preview image URL from og:image

    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"))
    collection: Mapped[Collection | None] = relationship("Collection", back_populates="links")

    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=link_tag_table, back_populates="links", lazy="selectin"
    )


@event.listens_for(Collection, "before_insert")
def collection_before_insert(mapper, connection, target: Collection) -> None:  # noqa: D401
    """Ensure slug stays synced before inserting."""

    target.slug = slugify(target.name)


@event.listens_for(Collection, "before_update")
def collection_before_update(mapper, connection, target: Collection) -> None:  # noqa: D401
    """Ensure slug stays synced before updating."""

    target.slug = slugify(target.name)


@event.listens_for(Tag, "before_insert")
def tag_before_insert(mapper, connection, target: Tag) -> None:  # noqa: D401
    """Keep tag slug synced before insert."""

    target.slug = slugify(target.name)


@event.listens_for(Tag, "before_update")
def tag_before_update(mapper, connection, target: Tag) -> None:  # noqa: D401
    """Keep tag slug synced before update."""

    target.slug = slugify(target.name)
