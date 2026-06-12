# -*- coding: utf-8 -*-
from __future__ import annotations

# 这些是主界面快捷组合：只负责选择顺序流水线和最后的 WAV 整理。
# 最终导出始终是一个 WAV；中间临时文件只在系统临时目录里传递，完成后清理。

PLATFORM_PRESETS = {
    "A1": {
        "code": "A1",
        "name": "单方案保真 1",
        "short": "1",
        "desc": "优先使用方案1单独处理，保留低频、高频和人声细节，速度最快。",
        "schemes": [1],
        "format": "WAV",
        "postprocess": False,
    },
    "AE17": {
        "code": "AE17",
        "name": "电音低频 17",
        "short": "电音17",
        "desc": "给低频重、鼓组密、尾段能量大的曲子用，减少多方案叠加带来的波形扁平化。",
        "schemes": [17],
        "format": "WAV",
        "postprocess": False,
    },
    "A19": {
        "code": "A19",
        "name": "实测组合 1-9",
        "short": "1-9",
        "desc": "先做轻量底层整理，再接空气感收尾，适合你这类曲谱要保留、整体变化不能太重的素材。",
        "schemes": [1, 9],
        "format": "WAV",
        "postprocess": False,
        "chain": (
            "highpass=f=28,"
            "equalizer=f=120:g=0.25:width_type=h:width=100,"
            "equalizer=f=1800:g=0.20:width_type=h:width=1200,"
            "equalizer=f=7200:g=-0.18:width_type=h:width=3800,"
            "acompressor=threshold=-19dB:ratio=1.18:attack=24:release=210:makeup=1,"
            "alimiter=limit=0.96"
        ),
        "args": ["-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-c:a", "pcm_s16le"],
    },
    "A952": {
        "code": "A952",
        "name": "实测组合 9-5-2",
        "short": "9-5-2",
        "desc": "先保留空气感，再做 48k 主体层，最后按 2 号逻辑收尾。",
        "schemes": [9, 5, 2],
        "format": "WAV",
        "postprocess": False,
        "chain": (
            "highpass=f=28,"
            "equalizer=f=95:g=0.35:width_type=h:width=90,"
            "equalizer=f=180:g=0.28:width_type=h:width=140,"
            "equalizer=f=3200:g=-0.22:width_type=h:width=1800,"
            "equalizer=f=9600:g=-0.30:width_type=h:width=4200,"
            "acompressor=threshold=-19dB:ratio=1.28:attack=22:release=190:makeup=1,"
            "loudnorm=I=-16.5:TP=-1.6:LRA=10,alimiter=limit=0.94"
        ),
        "args": ["-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-c:a", "pcm_s16le"],
    },
    "A52": {
        "code": "A52",
        "name": "实测组合 5-2",
        "short": "5-2",
        "desc": "48k 主体层接 2 号收尾，适合多数 MP3 先跑这一套。",
        "schemes": [5, 2],
        "format": "WAV",
        "postprocess": False,
        "chain": (
            "highpass=f=26,"
            "equalizer=f=160:g=0.30:width_type=h:width=120,"
            "equalizer=f=2800:g=-0.18:width_type=h:width=1600,"
            "equalizer=f=9200:g=-0.25:width_type=h:width=3600,"
            "acompressor=threshold=-19dB:ratio=1.25:attack=24:release=190:makeup=1,"
            "loudnorm=I=-16.5:TP=-1.6:LRA=10,alimiter=limit=0.94"
        ),
        "args": ["-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-c:a", "pcm_s16le"],
    },
    "A92": {
        "code": "A92",
        "name": "实测组合 9-2",
        "short": "9-2",
        "desc": "空气感保留接 2 号收尾，适合原曲质量比较好的素材。",
        "schemes": [9, 2],
        "format": "WAV",
        "postprocess": False,
        "chain": (
            "highpass=f=28,"
            "equalizer=f=110:g=0.32:width_type=h:width=100,"
            "equalizer=f=2400:g=-0.20:width_type=h:width=1400,"
            "equalizer=f=8500:g=-0.28:width_type=h:width=3600,"
            "acompressor=threshold=-19.5dB:ratio=1.22:attack=24:release=210:makeup=1,"
            "loudnorm=I=-16.5:TP=-1.6:LRA=11,alimiter=limit=0.94"
        ),
        "args": ["-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-c:a", "pcm_s16le"],
    },
    "A72": {
        "code": "A72",
        "name": "实测组合 7-2",
        "short": "7-2",
        "desc": "高音质 SoX 层接 2 号收尾，适合要保留曲谱细节的素材。",
        "schemes": [7, 2],
        "format": "WAV",
        "postprocess": False,
        "chain": (
            "highpass=f=26,"
            "equalizer=f=140:g=0.30:width_type=h:width=120,"
            "equalizer=f=3000:g=-0.16:width_type=h:width=1700,"
            "equalizer=f=10500:g=-0.24:width_type=h:width=4200,"
            "acompressor=threshold=-19dB:ratio=1.24:attack=24:release=200:makeup=1,"
            "loudnorm=I=-16.5:TP=-1.6:LRA=10,alimiter=limit=0.94"
        ),
        "args": ["-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-c:a", "pcm_s16le"],
    },
}

PLATFORM_ORDER = ["A1", "AE17", "A19", "A52", "A72"]
