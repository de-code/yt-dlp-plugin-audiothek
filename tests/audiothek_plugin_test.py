import json
from pathlib import Path
import pytest

from yt_dlp_plugins.extractor.audiothek_plugin import (
    _get_info_dict_for_ld_data_dict,
    _iter_entry_dict_for_nextjs_dict
)


# Examples:
#   https://www.ardaudiothek.de/episode/maushoerspiel-lang/die-amazonas-detektive-verschwoerung-im-dschungel/die-maus/14107801/
#   https://wdrmedien-a.akamaihd.net/medp/podcast/weltweit/fsk0/324/3240584/3240584_60895358.mp3?download=true

EXAMPLE_LD_DATA_DICT = {
    '@context': 'https://schema.org/',
    '@type': 'PodcastEpisode',
    'encodingFormat': 'audio/mp3',
    'inLanguage': 'de-DE',
    'isAccessibleForFree': 'true',
    'partOfSeries': {
        '@type': 'PodcastSeries',
        'name': 'MausHörspiel lang',
        'url': 'https://www.ardaudiothek.de/sendung/maushoerspiel-lang/36244846/',
        'about': 'Die Maus präsentiert euch Kinderhörspiele, um richtig in anderen Welten zu versinken. Ihr hört Kinderbuch-Klassiker, Zeitreisen, Märchen und heldenhafte Abenteuer - jede Folge ist mindestens 30 Minuten lang. Eine Altersempfehlung steht auch immer dabei.',
    },
    'identifier': '14107801',
    'name': 'Die Amazonas-Detektive - Verschwörung im Dschungel',
    'url': 'https://www.ardaudiothek.de/episode/maushoerspiel-lang/die-amazonas-detektive-verschwoerung-im-dschungel/die-maus/14107801/',
    'description': '•Kinderhörspiel, ab 8 Jahren• Manaus, Brasilien. Straßenjunge Pablo erhält einen Hilferuf: Sein Freund, ein Umweltaktivist, scheint entführt worden zu sein. Die Suche führt Pablo in den brasilianischen Urwald und ein abenteuerlicher Wettlauf gegen die Zeit beginnt.\r\n\r\nVon Antonia Michaelis\r\nHR/WDR 2022\r\nwww.wdrmaus.de',
    'image': 'https://api.ardmediathek.de/image-service/images/urn:ard:image:82e9c6e947a6e1ad?w=1280&ch=eb358f3a1a0d12db',
    'datePublished': '2025-01-25T19:04:00+01:00',
    'timeRequired': 3175,
    'associatedMedia': {
        '@type': 'MediaObject',
        'contentUrl': 'https://wdrmedien-a.akamaihd.net/medp/podcast/weltweit/fsk0/324/3240584/3240584_60895358.mp3',
    },
    'expires': '2028-01-25',
    'productionCompany': 'Die Maus',
}


@pytest.fixture(name='playlist_nextjs_json')
def _playlist_nextjs_json():
    return json.loads(Path('./test-data/playlist-nextjs.json').read_text())


class TestGetInfoDictForLdDataDict:
    def test_should_parse_ld_data_json_to_info(self):
        info_dict = _get_info_dict_for_ld_data_dict({
            **EXAMPLE_LD_DATA_DICT,
             'datePublished': '2025-01-25T19:04:00+01:00'
        })
        assert info_dict == {
            'id': EXAMPLE_LD_DATA_DICT['identifier'],
            'ext': 'mp3',
            'series': EXAMPLE_LD_DATA_DICT['partOfSeries']['name'],
            'title': EXAMPLE_LD_DATA_DICT['name'],
            'description': EXAMPLE_LD_DATA_DICT['description'],
            'upload_date': '20250125',
            'timestamp': 1737828240,
            'duration': EXAMPLE_LD_DATA_DICT['timeRequired'],
            'language': EXAMPLE_LD_DATA_DICT['inLanguage'],
            'thumbnail': EXAMPLE_LD_DATA_DICT['image'],
            'formats': [{
                'url': EXAMPLE_LD_DATA_DICT['associatedMedia']['contentUrl'],
                'ext': 'mp3',
                'vcodec': 'none',
                'acodec': 'mp3'
            }]
        }


class TestIterEntryDictForNextjsDict:
    def test_should_extract_episodes(self, playlist_nextjs_json: dict):
        entries = list(_iter_entry_dict_for_nextjs_dict(playlist_nextjs_json))
        assert entries
