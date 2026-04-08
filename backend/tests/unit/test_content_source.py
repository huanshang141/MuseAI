from app.application.content_source import ContentMetadata, ContentSource


def test_content_source_creation():
    """Test creating a ContentSource instance."""
    metadata = ContentMetadata(
        name="Test Exhibit",
        category="Ceramics",
        hall="Hall A",
        floor=1,
    )
    source = ContentSource(
        source_id="test-123",
        source_type="exhibit",
        content="This is test content for the exhibit.",
        metadata=metadata,
    )
    assert source.source_id == "test-123"
    assert source.source_type == "exhibit"
    assert source.metadata.name == "Test Exhibit"

def test_content_metadata_optional_fields():
    """Test ContentMetadata with optional fields."""
    metadata = ContentMetadata()
    assert metadata.name is None
    assert metadata.category is None
    assert metadata.filename is None

def test_content_source_for_document():
    """Test creating ContentSource for a document."""
    metadata = ContentMetadata(filename="test.pdf")
    source = ContentSource(
        source_id="doc-456",
        source_type="document",
        content="Document content here.",
        metadata=metadata,
    )
    assert source.source_type == "document"
    assert source.metadata.filename == "test.pdf"


def test_content_metadata_to_dict_excludes_none():
    """Test that to_dict excludes None values."""
    metadata = ContentMetadata(
        name="Test",
        category="Ceramics",
    )
    result = metadata.to_dict()
    assert "name" in result
    assert "category" in result
    assert "filename" not in result  # None should be excluded
    assert "floor" not in result  # None should be excluded


def test_content_metadata_to_dict_includes_extra():
    """Test that extra fields are included in to_dict."""
    metadata = ContentMetadata(
        name="Test",
        extra={"custom_field": "value", "another": 123},
    )
    result = metadata.to_dict()
    assert result["custom_field"] == "value"
    assert result["another"] == 123


def test_content_source_invalid_source_type():
    """Test that invalid source_type raises ValueError."""
    import pytest

    metadata = ContentMetadata()
    with pytest.raises(ValueError, match="source_type must be one of"):
        ContentSource(
            source_id="test",
            source_type="invalid_type",
            content="test",
            metadata=metadata,
        )


def test_content_source_to_dict():
    """Test ContentSource to_dict method."""
    metadata = ContentMetadata(name="Test", category="Art")
    source = ContentSource(
        source_id="test-123",
        source_type="exhibit",
        content="Test content",
        metadata=metadata,
    )
    result = source.to_dict()
    assert result["source_id"] == "test-123"
    assert result["source_type"] == "exhibit"
    assert result["metadata"]["name"] == "Test"
