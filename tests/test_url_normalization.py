"""Tests for URL normalization and duplicate detection with UTM parameters."""

from app.crud import normalize_url, get_link_by_url, create_link
from app.schemas import LinkCreate


def test_normalize_url_removes_utm_params():
    """Test that UTM parameters are stripped from URLs."""
    # Test various UTM parameters
    url_with_utm = "https://example.com/page?utm_source=twitter&utm_medium=social&utm_campaign=spring"
    url_without_utm = "https://example.com/page"
    
    assert normalize_url(url_with_utm) == url_without_utm


def test_normalize_url_keeps_other_params():
    """Test that non-UTM parameters are preserved."""
    url = "https://example.com/page?id=123&category=tech&utm_source=email"
    
    # Parse result to compare without worrying about parameter order
    result = normalize_url(url)
    assert "id=123" in result
    assert "category=tech" in result
    assert "utm_source" not in result


def test_normalize_url_handles_all_utm_variants():
    """Test all common UTM parameters are removed."""
    utm_params = [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic'
    ]
    
    base_url = "https://example.com/page"
    for param in utm_params:
        url_with_param = f"{base_url}?{param}=test_value"
        assert normalize_url(url_with_param) == base_url


def test_normalize_url_no_query_params():
    """Test URLs without query parameters remain unchanged."""
    url = "https://example.com/page"
    assert normalize_url(url) == url


def test_normalize_url_with_fragment():
    """Test that fragments are preserved."""
    url = "https://example.com/page?utm_source=twitter#section1"
    expected = "https://example.com/page#section1"
    assert normalize_url(url) == expected


def test_normalize_url_malformed():
    """Test that malformed URLs don't crash the function."""
    malformed = "not-a-valid-url"
    # Should return original URL if normalization fails
    result = normalize_url(malformed)
    assert isinstance(result, str)


def test_duplicate_detection_with_utm_params(db_session):
    """Test that links with different UTM parameters are detected as duplicates."""
    # Create first link
    link1 = LinkCreate(
        url="https://example.com/article?utm_source=twitter",
        title="Test Article",
        notes="",
        collection=None,
        tags=[],
        in_inbox=True,
        is_done=False
    )
    created_link = create_link(db_session, link1)
    db_session.commit()
    
    # Try to find duplicate with different UTM parameter
    duplicate_url = "https://example.com/article?utm_source=facebook"
    found_link = get_link_by_url(db_session, duplicate_url)
    
    assert found_link is not None
    assert found_link.id == created_link.id
    assert "utm" in found_link.url.lower()  # Original URL preserved in database


def test_different_urls_not_duplicates(db_session):
    """Test that actually different URLs are not marked as duplicates."""
    # Create first link
    link1 = LinkCreate(
        url="https://example.com/article1",
        title="Article 1",
        notes="",
        collection=None,
        tags=[],
        in_inbox=True,
        is_done=False
    )
    create_link(db_session, link1)
    db_session.commit()
    
    # Check different URL is not found as duplicate
    different_url = "https://example.com/article2"
    found_link = get_link_by_url(db_session, different_url)
    
    assert found_link is None


def test_same_domain_different_path_not_duplicate(db_session):
    """Test that same domain with different paths are not duplicates."""
    # Create first link
    link1 = LinkCreate(
        url="https://example.com/path1?utm_source=twitter",
        title="Path 1",
        notes="",
        collection=None,
        tags=[],
        in_inbox=True,
        is_done=False
    )
    create_link(db_session, link1)
    db_session.commit()
    
    # Check different path is not found as duplicate
    different_path = "https://example.com/path2?utm_source=facebook"
    found_link = get_link_by_url(db_session, different_path)
    
    assert found_link is None


def test_original_url_preserved_in_database(db_session):
    """Test that the original URL with UTM params is stored in the database."""
    original_url = "https://example.com/page?utm_source=newsletter&utm_campaign=weekly"
    link = LinkCreate(
        url=original_url,
        title="Test",
        notes="",
        collection=None,
        tags=[],
        in_inbox=True,
        is_done=False
    )
    created = create_link(db_session, link)
    db_session.commit()
    
    # Original URL should be preserved
    assert created.url == original_url
    
    # But duplicate detection should still work
    similar_url = "https://example.com/page?utm_source=twitter"
    found = get_link_by_url(db_session, similar_url)
    assert found is not None
    assert found.id == created.id
