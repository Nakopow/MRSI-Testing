"""
Tests for the pipeline module.

These tests verify the pipeline routes and state management functionality.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.pipeline import (
    _load_state,
    _save_state,
    _update_step_status,
    _check_articles_exist,
    _check_digest_exists,
    pipeline_bp
)


@pytest.fixture
def app():
    """Create a Flask app with the pipeline blueprint."""
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file path."""
    return str(tmp_path / ".test_pipeline_state.json")


class TestPipelineState:
    """Test pipeline state management."""

    def test_load_state_returns_default_when_no_file(self, tmp_path, monkeypatch):
        """Verify default state is returned when no state file exists."""
        # Change to temp directory to avoid using real state file
        monkeypatch.chdir(tmp_path)
        state = _load_state()
        
        assert "scraping" in state
        assert "summarizing" in state
        assert "insights" in state
        assert "tlp" in state
        assert state["scraping"]["status"] == "idle"
        assert state["summarizing"]["status"] == "idle"

    def test_save_and_load_state(self, tmp_path, monkeypatch):
        """Verify state can be saved and loaded."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        
        test_state = {
            "scraping": {"status": "running", "last_run": None, "last_duration": None},
            "summarizing": {"status": "idle", "last_run": None, "last_duration": None},
        }
        _save_state(test_state)
        loaded_state = _load_state()
        
        assert loaded_state == test_state

    def test_update_step_status(self, tmp_path, monkeypatch):
        """Verify step status can be updated."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        
        # Initialize state
        _save_state(_load_state())
        
        # Update status
        _update_step_status("scraping", "running")
        state = _load_state()
        assert state["scraping"]["status"] == "running"
        
        # Update back to idle with duration
        _update_step_status("scraping", "idle", duration=5.5)
        state = _load_state()
        assert state["scraping"]["status"] == "idle"
        assert state["scraping"]["last_duration"] == 5.5
        assert state["scraping"]["last_run"] is not None


class TestArtifactChecks:
    """Test artifact existence checks."""

    def test_check_articles_exist_when_all_exist(self, tmp_path, monkeypatch):
        """Verify check returns True when all article files exist."""
        monkeypatch.chdir(tmp_path)
        
        # Create all article files
        for topic in ["ai", "cybersecurity", "web3"]:
            (tmp_path / f"{topic}_articles.txt").write_text("Test content")
        
        assert _check_articles_exist() is True

    def test_check_articles_exist_when_missing(self, tmp_path, monkeypatch):
        """Verify check returns False when article files are missing."""
        monkeypatch.chdir(tmp_path)
        
        # Don't create any files
        assert _check_articles_exist() is False

    def test_check_articles_exist_when_partial(self, tmp_path, monkeypatch):
        """Verify check returns False when only some article files exist."""
        monkeypatch.chdir(tmp_path)
        
        # Create only one article file
        (tmp_path / "ai_articles.txt").write_text("Test content")
        
        assert _check_articles_exist() is False

    def test_check_digest_exists_when_exists(self, tmp_path, monkeypatch):
        """Verify check returns True when digest file exists."""
        monkeypatch.chdir(tmp_path)
        
        (tmp_path / "output.txt").write_text("Daily digest content")
        
        assert _check_digest_exists() is True

    def test_check_digest_exists_when_missing(self, tmp_path, monkeypatch):
        """Verify check returns False when digest file is missing."""
        monkeypatch.chdir(tmp_path)
        
        assert _check_digest_exists() is False


class TestPipelineRoutes:
    """Test pipeline API routes."""

    def test_status_route(self, client, tmp_path, monkeypatch):
        """Test the status endpoint returns pipeline state."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        
        # Initialize state
        _save_state(_load_state())
        
        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        
        data = response.get_json()
        assert "scraping" in data
        assert "summarizing" in data
        assert "insights" in data
        assert "tlp" in data
        assert "artifacts" in data

    def test_scrape_route_method_not_allowed(self, client, tmp_path, monkeypatch):
        """Test that GET method is not allowed for scrape route."""
        monkeypatch.chdir(tmp_path)
        
        response = client.get("/api/pipeline/scrape")
        assert response.status_code == 405

    def test_scrape_route_starts_scraping(self, client, tmp_path, monkeypatch):
        """Test that POST to scrape route starts scraping task."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        with patch("routes.pipeline.run_scraping") as mock_scrape:
            response = client.post("/api/pipeline/scrape")
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["status"] == "started"
            assert data["step"] == "scraping"

    def test_summarize_route_missing_articles(self, client, tmp_path, monkeypatch):
        """Test that summarize route returns error when articles are missing."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        response = client.post("/api/pipeline/summarize")
        assert response.status_code == 400
        
        data = response.get_json()
        assert "error" in data
        assert data["required_step"] == "scraping"

    def test_insights_route_missing_digest(self, client, tmp_path, monkeypatch):
        """Test that insights route returns error when digest is missing."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        response = client.post("/api/pipeline/insights")
        assert response.status_code == 400
        
        data = response.get_json()
        assert "error" in data
        assert data["required_step"] == "summarizing"

    def test_tlp_route_missing_digest(self, client, tmp_path, monkeypatch):
        """Test that TLP route returns error when digest is missing."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        response = client.post("/api/pipeline/tlp")
        assert response.status_code == 400
        
        data = response.get_json()
        assert "error" in data
        assert data["required_step"] == "summarizing"

    def test_tlp_route_with_platform_filter(self, client, tmp_path, monkeypatch):
        """Test that TLP route accepts platform filter."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        # Create digest file
        (tmp_path / "output.txt").write_text("Digest content")
        
        with patch("routes.pipeline.run_tl_pipeline") as mock_tlp:
            response = client.post(
                "/api/pipeline/tlp",
                json={"platforms": ["linkedin", "twitter"], "topic": "ai"}
            )
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["status"] == "started"
            assert data["step"] == "tlp"

    def test_run_all_route(self, client, tmp_path, monkeypatch):
        """Test that run-all route starts full pipeline."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        response = client.post("/api/pipeline/run-all")
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["status"] == "started"
        assert data["step"] == "full-pipeline"

    def test_legacy_run_route(self, client, tmp_path, monkeypatch):
        """Test that legacy /run route still works."""
        monkeypatch.chdir(tmp_path)
        state_file = str(tmp_path / ".test_state.json")
        monkeypatch.setattr("routes.pipeline.STATE_FILE", state_file)
        _save_state(_load_state())
        
        response = client.post("/api/pipeline/run")
        assert response.status_code == 200
        
        data = response.get_json()
        assert data["status"] == "started"


class TestArticleParsing:
    """Test article parsing logic used in summarization."""

    def test_parse_articles_from_file_format(self):
        """Test parsing articles from the formatted text file format."""
        content = '''"Article Title 1"
Jan 01, 2025
This is the article body content.
It spans multiple lines.
http://example.com/article1

===

"Article Title 2"
Jan 02, 2025
Another article body.
http://example.com/article2
'''
        # Parse articles using the same logic as in routes/pipeline.py
        articles = []
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('"') and line.endswith('"'):
                title = line.strip('"')
                published = ""
                if i + 1 < len(lines):
                    published = lines[i + 1].strip()
                    i += 1
                body_lines = []
                i += 1
                while i < len(lines):
                    body_line = lines[i].strip()
                    if body_line.startswith("http") or body_line.startswith("=" * 10):
                        break
                    if body_line:
                        body_lines.append(body_line)
                    i += 1
                if title and body_lines:
                    articles.append({
                        "title": title,
                        "published": published,
                        "body": " ".join(body_lines)
                    })
            i += 1
        
        assert len(articles) == 2
        assert articles[0]["title"] == "Article Title 1"
        assert articles[0]["published"] == "Jan 01, 2025"
        assert "article body content" in articles[0]["body"]
        assert articles[1]["title"] == "Article Title 2"