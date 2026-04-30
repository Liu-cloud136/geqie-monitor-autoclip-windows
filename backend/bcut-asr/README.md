# bcut-asr

bcut-asr 是必剪语音识别 API 的 Python 封装。

## 安装

```bash
pip install -e .
```

## 使用

```python
from bcut_asr import BcutASR

asr = BcutASR()
asr.set_session(buvid="...", cookie="...")
result = asr.recognize("video.mp4")
print(result)
```
