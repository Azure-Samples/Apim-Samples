"""Runtime helpers for the OAuth 3rd-Party sample notebook."""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpotifyCredentials:
    """Represent the Spotify application credentials used by APIM."""

    client_id: str
    client_secret: str


@dataclass(frozen=True)
class SpotifyArtist:
    """Represent the Spotify artist fields demonstrated by the sample."""

    name: str
    popularity: int
    followers_total: int


def load_spotify_credentials(environment: Mapping[str, str] | None = None) -> SpotifyCredentials:
    """Load and validate Spotify application credentials from an environment mapping."""
    values = os.environ if environment is None else environment
    client_id = values.get('SPOTIFY_CLIENT_ID', '').strip()
    client_secret = values.get('SPOTIFY_CLIENT_SECRET', '').strip()

    missing_names = [
        name
        for name, value in (
            ('SPOTIFY_CLIENT_ID', client_id),
            ('SPOTIFY_CLIENT_SECRET', client_secret),
        )
        if not value
    ]
    if missing_names:
        missing = ', '.join(missing_names)
        raise ValueError(f'Missing Spotify OAuth environment variable(s): {missing}. Set them in the root .env file.')

    return SpotifyCredentials(client_id, client_secret)


def parse_spotify_artist(response: str | None) -> SpotifyArtist:
    """Parse and validate the Spotify artist response returned through APIM."""
    try:
        payload = json.loads(response)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Spotify artist response is not valid JSON.') from exc

    if not isinstance(payload, dict):
        raise ValueError('Spotify artist response must be a JSON object.')

    name = _required_string(payload, 'name')
    popularity = _required_integer(payload, 'popularity')
    followers = payload.get('followers')
    if not isinstance(followers, dict):
        raise ValueError("Spotify artist response field 'followers' must be an object.")
    followers_total = _required_integer(followers, 'total', parent='followers')

    return SpotifyArtist(name, popularity, followers_total)


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Spotify artist response field '{field}' must be a non-empty string.")
    return value


def _required_integer(payload: dict[str, Any], field: str, *, parent: str | None = None) -> int:
    value = payload.get(field)
    field_path = f'{parent}.{field}' if parent else field
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Spotify artist response field '{field_path}' must be an integer.")
    return value
