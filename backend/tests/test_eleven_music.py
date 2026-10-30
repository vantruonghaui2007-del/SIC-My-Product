import httpx
import pytest

from mixverse.creator.providers import MusicProviderError
from mixverse.creator.providers.eleven_music import ElevenMusicProvider


def test_key_id_rejection_explains_real_api_key_without_exposing_id(tmp_path):
    attempts = []
    def handle(request):
        attempts.append(request)
        return httpx.Response(400, json={'detail': {
            'status': 'api_key_id_used_as_api_key',
            'message': 'API key ID used as API key: private-test-id. Keys start with sk_.',
        }})
    target = tmp_path / 'result.mp3'
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = ElevenMusicProvider('private-test-id', client=client)
        with pytest.raises(MusicProviderError) as caught:
            provider.generate('text_song', '', 30, target, 'Xin chào Việt Nam', 'pop')
    assert caught.value.code == 'MUSIC_PROVIDER_AUTH'
    assert 'API key ID' in str(caught.value) and 'sk_' in str(caught.value)
    assert 'private-test-id' not in str(caught.value)
    assert len(attempts) == 1
    assert not target.exists()
