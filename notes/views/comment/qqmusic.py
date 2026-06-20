"""Comment qqmusic views."""
from .common import *  # noqa: F401, F403


def _extract_first_url(raw_value):
    match = re.search(r'https?://[^\s<>"\']+', str(raw_value or ''), re.I)
    return match.group(0) if match else ''

def _compact_qqmusic_text(raw_value):
    return re.sub(r'\s+', '', str(raw_value or ''))

def _is_allowed_qqmusic_url(raw_url):
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and parsed.hostname in QQ_MUSIC_HOSTS

def _extract_qqmusic_ids(raw_value):
    text = str(raw_value or '')
    compact_text = _compact_qqmusic_text(text)

    direct_songmid = re.fullmatch(r'[A-Za-z0-9]{8,32}', text.strip())
    if direct_songmid and not text.strip().isdigit():
        return {'player_id': direct_songmid.group(0), 'id_type': 'songmid'}

    songid = re.search(r'(?:songid|songId|id)=(\d+)', text, re.I)
    if songid:
        return {'player_id': songid.group(1), 'id_type': 'songid'}
    songid = re.search(r'(?:songid|songId|id)=(\d+)', compact_text, re.I)
    if songid:
        return {'player_id': songid.group(1), 'id_type': 'songid'}

    songmid = re.search(r'(?:songmid|songMid|mid)=([A-Za-z0-9]+)', text, re.I)
    if songmid:
        return {'player_id': songmid.group(1), 'id_type': 'songmid'}
    songmid = re.search(r'(?:songmid|songMid|mid)=([A-Za-z0-9]+)', compact_text, re.I)
    if songmid:
        return {'player_id': songmid.group(1), 'id_type': 'songmid'}

    song_detail = re.search(r'/songDetail/([A-Za-z0-9]+)', text, re.I)
    if song_detail:
        return {'player_id': song_detail.group(1), 'id_type': 'songmid'}
    song_detail = re.search(r'/songDetail/([A-Za-z0-9]+)', compact_text, re.I)
    if song_detail:
        return {'player_id': song_detail.group(1), 'id_type': 'songmid'}

    return None

def _resolve_songid_from_songmid(songmid):
    cache_key = 'qqmusic_songmid:' + hashlib.sha256(str(songmid).encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        response = requests.get(
            f'https://i.y.qq.com/v8/playsong.html?songmid={songmid}&type=0',
            allow_redirects=True,
            timeout=8,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        )
    except requests.RequestException as exc:
        logger.warning('resolve songid from songmid failed: %s', exc)
        return None

    match = (
        re.search(r'"songid"\s*:\s*(\d+)', response.text, re.I)
        or re.search(r'"id"\s*:\s*(\d+)', response.text, re.I)
        or re.search(r'songid=(\d+)', response.text, re.I)
    )
    if not match:
        return None

    songid = match.group(1)
    cache.set(cache_key, songid, 86400)
    return songid

def _resolve_qqmusic_share_payload(raw_text):
    direct_ids = _extract_qqmusic_ids(raw_text)
    if direct_ids:
        if direct_ids['id_type'] == 'songid':
            return {'player_id': direct_ids['player_id'], 'id_type': 'songid'}, None

        resolved_songid = _resolve_songid_from_songmid(direct_ids['player_id'])
        if resolved_songid:
            return {'player_id': resolved_songid, 'id_type': 'songid'}, None
        return None, '未能从 songmid 换算出 songid'

    share_url = _extract_first_url(raw_text)
    if not share_url:
        share_url = _extract_first_url(_compact_qqmusic_text(raw_text))
    if not share_url or not _is_allowed_qqmusic_url(share_url):
        return None, '无效的 QQ 音乐分享链接'

    cache_key = 'qqmusic_share:' + hashlib.sha256(share_url.encode('utf-8')).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached, None

    try:
        response = requests.get(
            share_url,
            allow_redirects=True,
            timeout=8,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            }
        )
    except requests.RequestException as exc:
        logger.warning('resolve qqmusic share failed: %s', exc)
        return None, 'QQ 音乐短链解析失败'

    candidates = [response.url, response.text]
    candidates.extend(history.url for history in response.history if getattr(history, 'url', None))

    for candidate in candidates:
        resolved = _extract_qqmusic_ids(candidate)
        if resolved:
            if resolved['id_type'] == 'songid':
                cache.set(cache_key, resolved, 86400)
                return resolved, None

            resolved_songid = _resolve_songid_from_songmid(resolved['player_id'])
            if resolved_songid:
                final_payload = {'player_id': resolved_songid, 'id_type': 'songid'}
                cache.set(cache_key, final_payload, 86400)
                return final_payload, None

    return None, '未能从分享链接中提取歌曲信息'

@require_http_methods(["GET"])
def resolve_qqmusic_share_api(request):
    try:
        raw_text = request.GET.get('text', '').strip() or request.GET.get('url', '').strip()
        if not raw_text:
            return JsonResponse({'error': '缺少分享内容'}, status=400)

        resolved, error = _resolve_qqmusic_share_payload(raw_text)
        if error:
            return JsonResponse({'error': error}, status=400)

        return JsonResponse({'ok': True, **resolved})
    except Http404:
        raise
    except Exception as exc:
        logger.error('resolve_qqmusic_share_api failed: %s', exc, exc_info=True)
        return JsonResponse({'error': 'QQ 音乐解析失败'}, status=500)

