"""Tests for the OAuth 3rd-Party sample-local helpers."""

import sys
from pathlib import Path

import pytest

OAUTH_SAMPLE_DIR = Path(__file__).resolve().parents[2] / 'samples' / 'oauth-3rd-party'
sys.path.insert(0, str(OAUTH_SAMPLE_DIR))

from oauth_helpers import SpotifyArtist, SpotifyCredentials, load_spotify_credentials, parse_spotify_artist  # noqa: E402


@pytest.mark.unit
def test_load_spotify_credentials_returns_trimmed_values():
    credentials = load_spotify_credentials(
        {
            'SPOTIFY_CLIENT_ID': ' client-id ',
            'SPOTIFY_CLIENT_SECRET': ' client-secret ',
        }
    )

    assert credentials == SpotifyCredentials('client-id', 'client-secret')


@pytest.mark.unit
@pytest.mark.parametrize(
    ('environment', 'missing_name'),
    [
        ({'SPOTIFY_CLIENT_SECRET': 'secret'}, 'SPOTIFY_CLIENT_ID'),
        ({'SPOTIFY_CLIENT_ID': 'client'}, 'SPOTIFY_CLIENT_SECRET'),
        ({'SPOTIFY_CLIENT_ID': ' ', 'SPOTIFY_CLIENT_SECRET': '\t'}, 'SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET'),
    ],
)
def test_load_spotify_credentials_rejects_missing_values(environment, missing_name):
    with pytest.raises(ValueError, match=missing_name):
        load_spotify_credentials(environment)


@pytest.mark.unit
def test_load_spotify_credentials_uses_process_environment(monkeypatch):
    monkeypatch.setenv('SPOTIFY_CLIENT_ID', 'client-id')
    monkeypatch.setenv('SPOTIFY_CLIENT_SECRET', 'client-secret')

    assert load_spotify_credentials() == SpotifyCredentials('client-id', 'client-secret')


@pytest.mark.unit
def test_parse_spotify_artist_returns_typed_result():
    response = '{"name": "Taylor Swift", "popularity": 99, "followers": {"total": 123456}}'

    assert parse_spotify_artist(response) == SpotifyArtist('Taylor Swift', 99, 123456)


@pytest.mark.unit
@pytest.mark.parametrize('response', [None, '', 'not JSON', '[]'])
def test_parse_spotify_artist_rejects_invalid_json_shape(response):
    with pytest.raises(ValueError, match='valid JSON|JSON object'):
        parse_spotify_artist(response)


@pytest.mark.unit
@pytest.mark.parametrize(
    ('response', 'field'),
    [
        ('{"popularity": 99, "followers": {"total": 1}}', 'name'),
        ('{"name": " ", "popularity": 99, "followers": {"total": 1}}', 'name'),
        ('{"name": "Artist", "popularity": "99", "followers": {"total": 1}}', 'popularity'),
        ('{"name": "Artist", "popularity": true, "followers": {"total": 1}}', 'popularity'),
        ('{"name": "Artist", "popularity": 99}', 'followers'),
        ('{"name": "Artist", "popularity": 99, "followers": []}', 'followers'),
        ('{"name": "Artist", "popularity": 99, "followers": {}}', 'followers.total'),
        ('{"name": "Artist", "popularity": 99, "followers": {"total": false}}', 'followers.total'),
    ],
)
def test_parse_spotify_artist_rejects_missing_or_malformed_fields(response, field):
    with pytest.raises(ValueError, match=field):
        parse_spotify_artist(response)
