# B 站视频 API 直链下载（替代 you-get / yt-dlp）

2026年6月实测：B 站对 you-get 和 yt-dlp 均返回 HTTP 412 Precondition Failed。改用 B 站官方 API 获取直链。

## 步骤

### 1. 获取视频元数据

```python
import urllib.request, ssl, json, re

url = "https://b23.tv/xxxxx"  # 或直接用 BV ID
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
}

# 解析短链获取 BV ID
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context())
bv = re.search(r'BV[\w]+', resp.geturl()).group(0)

# 获取视频信息
api = f'https://api.bilibili.com/x/web-interface/view?bvid={bv}'
req2 = urllib.request.Request(api, headers=headers)
resp2 = urllib.request.urlopen(req2, timeout=10, context=ssl.create_default_context())
data = json.loads(resp2.read().decode())
info = data['data']
cid = info['cid']  # 用于获取播放地址
```

### 2. 获取播放直链并下载

```python
# 获取播放地址（qn=16 即 360p，足够音频提取）
play_api = f'https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=16&fnval=1'
req3 = urllib.request.Request(play_api, headers=headers)
resp3 = urllib.request.urlopen(req3, timeout=10, context=ssl.create_default_context())
play_data = json.loads(resp3.read().decode())
video_url = play_data['data']['durl'][0]['url']

# 下载视频（需要带 Referer）
req4 = urllib.request.Request(video_url, headers=headers)
resp4 = urllib.request.urlopen(req4, timeout=120, context=ssl.create_default_context())
with open('/tmp/bilibili_video.mp4', 'wb') as f:
    f.write(resp4.read())
```

### 3. 提取音频

```bash
ffmpeg -y -i /tmp/bilibili_video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/bilibili_audio.wav
```

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `qn` | 16 | 360p，文件最小，够 Whisper 用 |
| `fnval` | 1 | 使用传统 flv/mp4 格式（非 DASH） |
| `cid` | 从 view API 获取 | 每个视频分P对应一个 cid |

## 注意事项

- 直链有时效性，获取后尽快下载
- 必须带 `Referer: https://www.bilibili.com/video/{BV}/` header
- 30 分钟视频约 57MB（360p），下载约 1 分钟
- API 无需 cookie 即可访问（≤360p）
