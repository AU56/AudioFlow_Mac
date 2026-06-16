# -*- coding: utf-8 -*-
from __future__ import annotations

# 主界面只展示歌曲风格入口，减少客户理解成本。
# 高级区只展示核心方案，重复方向折进风格预设和内部兼容链路。

CATEGORY_PRESETS = {
    "POP": {
        "code": "POP",
        "name": "人声流行",
        "short": "人声流行",
        "desc": "主力人声链路，适合流行、民谣、抒情、普通男声女声歌曲。",
        "schemes": [1, 9],
        "format": "WAV",
    },
    "INSTR": {
        "code": "INSTR",
        "name": "纯音乐器乐",
        "short": "纯音乐",
        "desc": "只做轻量保真，最大限度保留钢琴、吉他、弦乐、氛围和尾段动态。",
        "schemes": [1],
        "format": "WAV",
    },
    "DJ": {
        "code": "DJ",
        "name": "DJ 电音",
        "short": "DJ电音",
        "desc": "低频特化，适合电音、舞曲、鼓组密集、后半段低频很重的歌曲。",
        "schemes": [17],
        "format": "WAV",
    },
    "FOLK": {
        "code": "FOLK",
        "name": "古风民谣",
        "short": "古风民谣",
        "desc": "保留人声和器乐空气感，适合古风、民谣、轻编曲和细节较多的歌曲。",
        "schemes": [1, 5],
        "format": "WAV",
    },
    "RAP": {
        "code": "RAP",
        "name": "说唱节奏",
        "short": "说唱节奏",
        "desc": "保留节拍冲击和人声清晰度，适合说唱、快歌、节奏感强的素材。",
        "schemes": [1, 16],
        "format": "WAV",
    },
    "BRIGHT": {
        "code": "BRIGHT",
        "name": "明亮女声",
        "short": "明亮女声",
        "desc": "控制齿音和刺耳高频，同时保留亮度，适合高音、女声和偏亮歌曲。",
        "schemes": [1, 4],
        "format": "WAV",
    },
    "CURVE": {
        "code": "CURVE",
        "name": "曲谱修整",
        "short": "曲谱修整",
        "desc": "整理旋律线和中频轮廓，适合修后声音偏低、主旋律不够清楚的素材。",
        "schemes": [15],
        "format": "WAV",
    },
    "MASTER": {
        "code": "MASTER",
        "name": "自然母带",
        "short": "自然母带",
        "desc": "轻量统一响度和空间细节，适合已经修得不错、只需要最后整理的成品。",
        "schemes": [16],
        "format": "WAV",
    },
}

CATEGORY_ORDER = ["POP", "INSTR", "DJ", "FOLK", "RAP", "BRIGHT", "CURVE", "MASTER"]

PLATFORM_PRESETS = {
    "A1": {
        "code": "A1",
        "name": "纯音乐器乐 1",
        "short": "纯音乐1",
        "desc": "优先使用方案 1 单独处理，保留低频、高频和尾段细节，速度最快。",
        "schemes": [1],
        "format": "WAV",
        "postprocess": False,
    },
    "AE17": {
        "code": "AE17",
        "name": "DJ低频 17",
        "short": "DJ17",
        "desc": "给低频重、鼓组密、尾段能量大的曲子用，减少多方案叠加带来的波形扁平化。",
        "schemes": [17],
        "format": "WAV",
        "postprocess": False,
    },
    "A19": {
        "code": "A19",
        "name": "人声流行 1-9",
        "short": "1-9",
        "desc": "先做轻量底层整理，再接空气感收尾，适合大多数人声流行歌曲。",
        "schemes": [1, 9],
        "format": "WAV",
        "postprocess": False,
    },
    "A52": {
        "code": "A52",
        "name": "高频保真 5-2",
        "short": "5-2",
        "desc": "高频保真层接厚度收尾，适合原曲比较清晰但整体偏薄的素材。",
        "schemes": [5, 2],
        "format": "WAV",
        "postprocess": False,
    },
    "A72": {
        "code": "A72",
        "name": "曲谱均衡 7-2",
        "short": "7-2",
        "desc": "通用均衡接厚度补偿，适合要保留旋律和高频细节的素材。",
        "schemes": [7, 2],
        "format": "WAV",
        "postprocess": False,
    },
    "A18": {
        "code": "A18",
        "name": "小体积轻量 18",
        "short": "轻量18",
        "desc": "轻处理后导出 MP3，控制体积同时尽量保留细节。",
        "schemes": [18],
        "format": "MP3",
        "postprocess": False,
    },
}

PLATFORM_ORDER = ["A1", "AE17", "A19", "A52", "A72", "A18"]
