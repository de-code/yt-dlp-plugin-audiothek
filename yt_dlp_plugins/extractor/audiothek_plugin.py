# pylint: disable=abstract-method

# import re
from datetime import datetime
import json
import re
from typing import Iterable, List, Optional, Sequence
from urllib.parse import quote_plus

from yt_dlp.extractor.common import (
    InfoExtractor,
    urljoin,
    base_url as get_base_url
)
from yt_dlp.utils import orderedSet
from yt_dlp.utils._utils import ExtractorError


GRAPHQL_ENDPOINT_URL = 'https://api.ardaudiothek.de/graphql'

GRAPHQL_QUERY = r'query ProgramSetEpisodesQuery($id:ID!,$offset:Int!,$count:Int!){result:programSet(id:$id){items(offset:$offset first:$count filter:{isPublished:{equalTo:true},itemType:{notEqualTo:EVENT_LIVESTREAM}}){pageInfo{hasNextPage endCursor}nodes{id coreId title isPublished tracking publishDate summary duration path image{url url1X1 description attribution}programSet{id coreId title path publicationService{title genre path organizationName}}audios{url mimeType downloadUrl allowDownload}}}}}'  # noqa  pylint: disable=line-too-long


def _get_info_dict_for_ld_data_dict(ld_data_dict: dict) -> dict:
    timestamp = datetime.fromisoformat(ld_data_dict['datePublished'])
    encoding_format = ld_data_dict['encodingFormat']
    if encoding_format != 'audio/mp3':
        raise AssertionError(f'Expected audio/mp3 but found: {repr(encoding_format)}')
    return {
        'ext': 'mp3',
        'id': ld_data_dict['identifier'],
        'series': ld_data_dict['partOfSeries']['name'],
        'title': ld_data_dict['name'],
        'description': ld_data_dict['description'],
        'upload_date': timestamp.strftime(r'%Y%m%d'),
        'timestamp': int(timestamp.timestamp()),
        'duration': ld_data_dict['timeRequired'],
        'language': ld_data_dict['inLanguage'],
        'thumbnail': ld_data_dict['image'],
        'formats': [{
            'url': ld_data_dict['associatedMedia']['contentUrl'],
            'ext': 'mp3',
            'vcodec': 'none',
            'acodec': 'mp3'
        }]
    }


def _get_nodes_from_nextjs_dict(nextjs_dict: dict) -> Sequence[dict]:
    return nextjs_dict['props']['pageProps']['initialData']['data']['result']['items']['nodes']


def _get_total_count_from_nextjs_dict(nextjs_dict: dict) -> int:
    return nextjs_dict['props']['pageProps']['initialData']['data']['result']['numberOfElements']


def _get_paths_from_nextjs_dict(nextjs_dict: dict) -> Sequence[str]:
    return [node['path'] for node in _get_nodes_from_nextjs_dict(nextjs_dict)]


def _get_nodes_from_graphql_response(graphql_response: dict) -> Sequence[dict]:
    return graphql_response['data']['result']['items']['nodes']


def _get_paths_from_graphql_response(graphql_response: dict) -> Sequence[str]:
    return [node['path'] for node in _get_nodes_from_graphql_response(graphql_response)]


def _iter_entry_dict_for_nextjs_dict(nextjs_dict: dict) -> Iterable[dict]:
    return [
        {
            'path': item_dict['path'],
            'title': item_dict['title']
        }
        for item_dict in _get_nodes_from_nextjs_dict(nextjs_dict)
    ]


class ArdAudioThekAudioIE(InfoExtractor):
    _VALID_URL: str = (
        r'https?://www\.ardaudiothek\.de/episode/urn:ard:episode:(?P<id>[^/]+)/'  # type: ignore
    )

    def _search_ld_data_dict(self, webpage: str, video_id: str, *, fatal=True, **kw) -> dict:
        return self._search_json(
            start_pattern=r'<script[^>]+type=[\'"]application/ld\+json[\'"][^>]*>',
            string=webpage,
            name='application/ld+json data',
            video_id=video_id,
            end_pattern='</script>',
            fatal=fatal,
            **kw,
        )

    def _real_extract(self, url: str):
        url_match = self._match_valid_url(url)
        display_id = url_match.group('id')
        webpage = self._download_webpage(url, display_id)
        ld_data_dict = self._search_ld_data_dict(webpage=webpage, video_id=display_id)
        self.write_debug(f'[debug] ld_data_dict: {repr(ld_data_dict)}')
        info_dict = _get_info_dict_for_ld_data_dict(ld_data_dict)
        for key in ['series', 'title', 'description', 'upload_date']:
            self.to_screen(f'[info] {key}: {repr(info_dict[key])}')
        return info_dict


class OldArdAudioThekAudioIE(ArdAudioThekAudioIE):
    _VALID_URL: str = (
        r'https?://www\.ardaudiothek\.de/episode/(?P<playlist_display_id>[^/]+)(?:/[^?]*)?/(?P<id>\d+)/'  # type: ignore
    )


class ArdAudioThekPlaylistIE(InfoExtractor):
    # https://www.ardaudiothek.de/sendung/maushoerspiel-lang/36244846/
    _VALID_URL: str = (
        r'https?://www\.ardaudiothek\.de/sendung/(?P<playlist_display_id>[^/]+)/(?P<playlist_id>\d+)/?$'  # type: ignore
    )

    def _fetch_graphql_response_via_url(
        self,
        graphql_url: str,
        video_id: str,
        variables: Optional[dict] = None
    ) -> dict:
        if variables:
            graphql_url += '&variables=' + quote_plus(json.dumps(
                variables,
                separators=(',', ':')
            ))
        self.to_screen(f'[info] fetching graphql response with variables: {variables}')
        self.to_screen(f'[debug] graphql url: {graphql_url}')
        response_str = self._download_webpage(
            graphql_url,
            video_id=video_id,
            headers={
                'Accept': '*/*',
                'Accept-Language': 'en-GB,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://www.ardaudiothek.de/',
                'Origin': 'https://www.ardaudiothek.de',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            }
        )
        try:
            return json.loads(response_str)
        except ValueError as err:
            self.to_screen(f'[debug] JSON: {repr(response_str)}')
            raise ExtractorError(
                'Failed to parse JSON',
                video_id=video_id,
                cause=err
            ) from err

    def _fetch_graphql_response(
        self,
        graphql_endpoint_url: str,
        query: str,
        video_id: str,
        variables: dict
    ) -> dict:
        self.to_screen(f'[info] fetching from graphql url: {graphql_endpoint_url}')
        self.to_screen(f'[info] variables: {variables}')
        request_json = {
            'query': query,
            'variables': variables
        }
        request_json_str = json.dumps(
            request_json,
            separators=(',', ':')
        )
        response_str = self._download_webpage(
            graphql_endpoint_url,
            video_id=video_id,
            data=request_json_str.encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Referer': 'https://www.ardaudiothek.de/',
                'Origin': 'https://www.ardaudiothek.de'
            }
        )
        try:
            return json.loads(response_str)
        except ValueError as err:
            self.to_screen(f'[debug] JSON: {repr(response_str)}')
            raise ExtractorError(
                'Failed to parse JSON',
                video_id=video_id,
                cause=err
            ) from err

    def _iter_entry_dict_from_paths(
        self,
        paths: Iterable[str],
        playlist_display_id: str,
        base_url: str
    ) -> Iterable[dict]:
        paths = orderedSet(paths)
        self.write_debug(f'[debug] paths: {paths}')
        for path in paths:
            url = urljoin(base_url, path)
            path_match = re.match(ArdAudioThekAudioIE._VALID_URL, url)  # pylint: disable=protected-access
            if not path_match:
                self.write_debug(f'[info] ignoring non-matching path: {repr(path)} ({repr(url)})')
                continue
            group_dict = path_match.groupdict()
            if 'playlist_display_id' not in group_dict:
                self.write_debug(f'[debug] no playlist display id in group dict: {group_dict}')
            elif path_match.group('playlist_display_id') != playlist_display_id:
                self.to_screen(f'[info] ignoring not matching playlist display id: {repr(path)}')
            yield self.url_result(
                ie=ArdAudioThekAudioIE.ie_key(),
                url=url
            )

    def _get_entries_via_finding_links(
        self,
        webpage: str,
        playlist_display_id: str,
        base_url: str
    ):
        paths = re.findall(
            r'<a\s[^>]*\s+href="([^"]+)">',
            webpage
        )
        yield from self._iter_entry_dict_from_paths(
            paths=paths,
            playlist_display_id=playlist_display_id,
            base_url=base_url
        )

    def _get_entries_via_nextjs_initial_data_and_and_graph_ql(
        self,
        webpage: str,
        playlist_id: str,
        playlist_display_id: str,
        base_url: str
    ):
        nextjs_data = self._search_nextjs_data(webpage=webpage, video_id=playlist_display_id)
        self.write_debug(f'[debug] nextjs_data: {nextjs_data}')
        total_items = _get_total_count_from_nextjs_dict(nextjs_data)
        self.to_screen(f'[info] total_items: {total_items}')
        paths: List[str] = []
        paths.extend(_get_paths_from_nextjs_dict(nextjs_data))
        page_size = len(paths)
        offset = page_size
        while len(paths) < total_items:
            graphql_response = self._fetch_graphql_response(
                GRAPHQL_ENDPOINT_URL,
                query=GRAPHQL_QUERY,
                variables={'id': playlist_id, 'offset': offset, 'count': page_size},
                video_id=playlist_display_id
            )
            this_page_paths = _get_paths_from_graphql_response(graphql_response)
            if not this_page_paths:
                self.report_warning('[warn] empty response, assuming end')
                break
            paths.extend(this_page_paths)
            offset += page_size
        yield from self._iter_entry_dict_from_paths(
            paths=paths,
            playlist_display_id=playlist_display_id,
            base_url=base_url
        )

    def _real_extract(self, url):
        url_match = self._match_valid_url(url)
        playlist_display_id = url_match.group('playlist_display_id')
        self.to_screen(f'[info] playlist_display_id: {playlist_display_id}')
        playlist_id = url_match.group('playlist_id')
        self.to_screen(f'[info] playlist_id: {playlist_id}')
        webpage = self._download_webpage(url, playlist_id)

        playlist_title = self._html_search_regex(
            r'<h1[^>]*>([^<]+)</h1>',
            string=webpage,
            name='playlist-title'
        ).strip()
        self.to_screen(f'[info] playlist_title: {playlist_title}')

        entries = list(self._get_entries_via_nextjs_initial_data_and_and_graph_ql(
            webpage=webpage,
            playlist_id=playlist_id,
            playlist_display_id=playlist_display_id,
            base_url=get_base_url(url)
        ))
        self.to_screen(f'[info] number of entries: {len(entries)}')
        self.write_debug(f'[debug] entries: {entries}')

        return self.playlist_result(
            entries,
            playlist_id=playlist_id,
            playlist_title=playlist_title
        )
