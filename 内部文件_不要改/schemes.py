# -*- coding: utf-8 -*-
from __future__ import annotations

# Parameters are aligned with the packaged V3.0 executable, not the loose tools
# script. The first-stage SoX schemes intentionally use pitch + 44.1k output;
# using the older tempo+bend set changes duration/loudness and drifts in combos.

SCHEMES = [
    {
        "index": 1, "num": "一", "id": "H", "name": "音质无损",
        "tag": "保真", "tag_bg": "#1a3d25", "tag_fg": "#4ed87a",
        "desc": "轻量保真打底，低频、高频和人声细节保留最多，适合单独使用或作为第一步。",
        "engine": "sox", "role": "轻修保真",
        "sox_args": ["highpass", "24", "pitch", "-22", "treble", "-0.18", "8500",
                     "treble", "0", "7000", "treble", "-1.4", "10500", "treble", "-2.2", "13500",
                     "lowpass", "15500", "reverb", "14", "34", "48", "52",
                     "gain", "-n", "-1.2", "rate", "48000", "dither", "-s"],
    },
    {
        "index": 2, "num": "二", "id": "I", "name": "厚度补偿",
        "tag": "厚度", "tag_bg": "#1a3d25", "tag_fg": "#4ed87a",
        "desc": "在保真基础上补一点低频和厚度，适合整体偏薄、声音不够稳的素材。",
        "engine": "sox", "role": "低频补偿",
        "sox_args": ["highpass", "28", "pitch", "-25", "bass", "4",
                     "treble", "-0.32", "8500", "treble", "0", "7000",
                     "treble", "-3", "9000", "treble", "-6", "10000",
                     "lowpass", "10000", "reverb", "20", "40", "55", "60",
                     "gain", "-n", "-1.8", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 3, "num": "三", "id": "J", "name": "空间层次",
        "tag": "空间", "tag_bg": "#1e1030", "tag_fg": "#a78bfa",
        "desc": "低频和空间感更明显，适合器乐、氛围、鼓组层次需要打开的素材。",
        "engine": "sox", "role": "层次重塑",
        "sox_args": ["highpass", "28", "pitch", "-25", "bass", "4",
                     "treble", "-0.32", "8500", "treble", "0", "6000",
                     "treble", "-3", "8000", "treble", "-6", "9000",
                     "lowpass", "9000", "reverb", "25", "45", "55", "65",
                     "gain", "-n", "-1.8", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 4, "num": "四", "id": "K", "name": "谐波收束",
        "tag": "稳定", "tag_bg": "#2a2110", "tag_fg": "#c9a84c",
        "desc": "温和整理谐波和刺耳高频，适合数码味重、齿音偏尖的素材。",
        "engine": "sox", "role": "高频收束",
        "sox_args": ["highpass", "28", "pitch", "-25", "bass", "5",
                     "treble", "-0.32", "8500", "treble", "0", "10000",
                     "treble", "-3", "12000", "treble", "-7", "14000",
                     "lowpass", "14000", "overdrive", "2", "80",
                     "reverb", "20", "45", "55", "65",
                     "gain", "-n", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 5, "num": "五", "id": "L", "name": "高频保真",
        "tag": "空气", "tag_bg": "#0d1e2e", "tag_fg": "#38bdf8",
        "desc": "保留更多空气感和高频细节，适合原曲音质较好、需要轻补亮度的素材。",
        "engine": "sox", "role": "高频保真",
        "sox_args": ["highpass", "28", "pitch", "-25", "bass", "4",
                     "treble", "-0.1", "9500", "treble", "0", "13000",
                     "treble", "-2", "15000", "treble", "-5", "17500",
                     "lowpass", "17500", "overdrive", "2", "80",
                     "reverb", "30", "52", "60", "70",
                     "gain", "-n", "-1.5", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 6, "num": "六", "id": "F", "name": "标准均衡",
        "tag": "均衡", "tag_bg": "#0d1e2e", "tag_fg": "#38bdf8",
        "desc": "中度高频整理与空间调整，适合偏硬、偏亮或空间不均的素材。",
        "engine": "sox", "role": "空间均衡",
        "sox_args": ["pitch", "-25", "highpass", "40", "bass", "5",
                     "treble", "-3", "4500", "treble", "-5", "7000",
                     "treble", "-8", "12000", "treble", "0", "6000",
                     "treble", "-3", "8000", "treble", "-6", "9000",
                     "lowpass", "9000", "reverb", "25", "50", "60", "70",
                     "dither", "-s", "rate", "44100", "gain", "-n", "-2"],
    },
    {
        "index": 7, "num": "七", "id": "G", "name": "通用均衡",
        "tag": "曲谱", "tag_bg": "#0d1e2e", "tag_fg": "#38bdf8",
        "desc": "比标准均衡更保留高频，适合旋律和人声都要稳的素材。",
        "engine": "sox", "role": "曲谱均衡",
        "sox_args": ["pitch", "-25", "highpass", "40", "bass", "4",
                     "treble", "0", "5000", "treble", "-3", "8000",
                     "treble", "-7", "12000", "treble", "0", "8000",
                     "treble", "-3", "10000", "treble", "-6", "11000",
                     "lowpass", "11000", "reverb", "25", "40", "50", "60",
                     "gain", "-n", "-2", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 8, "num": "八", "id": "H", "name": "重低频修整",
        "tag": "低频", "tag_bg": "#0d1e2e", "tag_fg": "#38bdf8",
        "desc": "低频更厚、空间更深，适合声音偏薄或中高频偏刺的素材。",
        "engine": "sox", "role": "厚度修正",
        "sox_args": ["tempo", "1.0185", "pitch", "-25", "highpass", "40",
                     "bass", "6", "treble", "0", "5000", "treble", "-3", "8000",
                     "treble", "-7", "12000", "lowpass", "9000",
                     "reverb", "30", "60", "70", "80",
                     "gain", "-n", "-2", "rate", "44100", "dither", "-s"],
    },
    {
        "index": 9, "num": "九", "id": "B", "name": "空气感保留",
        "tag": "进阶", "tag_bg": "#2d1111", "tag_fg": "#ff6b6b",
        "desc": "保留全频段空气感和瞬态信息，适合 1-9 人声通用链路的收尾。",
        "engine": "ffmpeg", "role": "空气收尾",
        "af": ("rubberband=pitch=0.975,"
               "equalizer=f=80:g=4.0:width_type=h:width=80,"
               "equalizer=f=150:g=3.0:width_type=h:width=100,"
               "equalizer=f=300:g=-1.5:width_type=h:width=200,"
               "equalizer=f=1500:g=-1.0:width_type=h:width=400,"
               "equalizer=f=4000:g=3.5:width_type=h:width=2000,"
               "equalizer=f=8000:g=1.8:width_type=h:width=4000,"
               "aecho=0.8:0.5:35|45:0.2|0.15,volume=2.0,highpass=f=45,"
               "crystalizer=i=0.15,"
               "acompressor=threshold=-18dB:ratio=2.0:attack=10:release=120:makeup=1.5,"
               "loudnorm=I=-12.6:TP=-0.5:LRA=11"),
        "extra_args": ["-map_metadata", "-1", "-ar", "48000", "-ac", "2",
                       "-sample_fmt", "s32", "-acodec", "pcm_s24le"],
    },
    {
        "index": 10, "num": "十", "id": "C", "name": "纯净人声",
        "tag": "人声", "tag_bg": "#1e1030", "tag_fg": "#a78bfa",
        "desc": "轻微声场和人声动态整理，适合人声过直、过平的素材。",
        "engine": "ffmpeg", "role": "人声自然",
        "af": ("vibrato=f=4.7:d=0.018,"
               "equalizer=f=400:g=-1.0:width_type=h:width=200,"
               "equalizer=f=2500:g=0.9:width_type=h:width=1000,"
               "aecho=0.90:0.70:28|38:0.10|0.08,highpass=f=55,"
               "lowpass=f=12000:width_type=h:width=1200:poles=2,crystalizer=i=0.08,"
               "acompressor=threshold=-18dB:ratio=1.35:attack=14:release=130:makeup=1.0,"
               "loudnorm=I=-15.5:TP=-1.8:LRA=11"),
        "extra_args": ["-map_metadata", "-1", "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le"],
    },
    {
        "index": 11, "num": "十一", "id": "D", "name": "母带精调",
        "tag": "母带", "tag_bg": "#2a2110", "tag_fg": "#c9a84c",
        "desc": "多段 EQ 和动态轻整，适合后期制作或二次整理。",
        "engine": "ffmpeg", "role": "母带整理",
        "af": ("vibrato=f=4.8:d=0.014,highpass=f=58,"
               "equalizer=f=100:g=1.1:width_type=h:width=70,"
               "equalizer=f=250:g=0.8:width_type=h:width=120,"
               "equalizer=f=600:g=-0.4:width_type=h:width=180,"
               "equalizer=f=2400:g=-0.5:width_type=h:width=1200,"
               "equalizer=f=5000:g=-0.9:width_type=h:width=2200,"
               "aecho=0.90:0.72:30|48:0.10|0.08,crystalizer=i=0.08,"
               "acompressor=threshold=-21dB:ratio=1.22:attack=18:release=160:makeup=1.0,"
               "loudnorm=I=-15.8:TP=-1.8:LRA=11"),
        "extra_args": ["-map_metadata", "-1", "-ar", "48000", "-ac", "2",
                       "-sample_fmt", "s32", "-acodec", "pcm_s24le"],
    },
    {
        "index": 12, "num": "十二", "id": "E", "name": "强效精修",
        "tag": "强效", "tag_bg": "#1a1200", "tag_fg": "#f0b429",
        "desc": "净化、瞬态和 EQ 加强，适合底噪重、数码感强的音频。",
        "engine": "ffmpeg", "role": "强效修整",
        "af": ("afftdn=nf=-20,vibrato=f=5.0:d=0.035,highpass=f=80,"
               "equalizer=f=250:g=1.0:width_type=h:width=80,"
               "equalizer=f=500:g=0.8:width_type=h:width=120,"
               "equalizer=f=1200:g=3.5:width_type=h:width=600,"
               "equalizer=f=2500:g=2.0:width_type=h:width=1000,"
               "equalizer=f=3000:g=2.0:width_type=h:width=2000,"
               "equalizer=f=5000:g=1.5:width_type=h:width=2000,"
               "equalizer=f=8000:g=-2.0:width_type=h:width=4000,"
               "equalizer=f=11000:g=-5.0:width_type=h:width=4000,"
               "equalizer=f=14000:g=-10.0:width_type=h:width=4000,"
               "aecho=0.90:0.85:40|55:0.18|0.12,crystalizer=i=0.20,"
               "acompressor=threshold=-16dB:ratio=1.8:attack=5:release=70:makeup=1.5,"
               "equalizer=f=7000:g=1.5:width_type=s:width=1,loudnorm=I=-14:TP=-1.5:LRA=11"),
        "extra_args": ["-map_metadata", "-1", "-ar", "48000", "-ac", "2", "-acodec", "pcm_s16le"],
    },
    {
        "index": 13, "num": "十三", "id": "N", "name": "保真净化",
        "tag": "净化", "tag_bg": "#0d1e2e", "tag_fg": "#38bdf8",
        "desc": "频域降噪和高频保留，适合底噪、杂音和轻度毛刺整理。",
        "engine": "ffmpeg", "role": "噪声净化",
        "af": "afftdn=nf=-20,highpass=f=40,lowpass=f=17500",
        "extra_args": ["-ar", "44100", "-ac", "2", "-map_metadata", "-1", "-acodec", "pcm_s24le"],
    },
    {
        "index": 14, "num": "十四", "id": "O", "name": "发布定稿",
        "tag": "定稿", "tag_bg": "#1a3d25", "tag_fg": "#4ed87a",
        "desc": "发布前统一响度、净化和格式整理，适合成品收尾。",
        "engine": "ffmpeg", "role": "发布定稿",
        "af": "afftdn=nf=-20,highpass=f=40,lowpass=f=17500",
        "extra_args": ["-ar", "44100", "-ac", "2", "-map_metadata", "-1",
                       "-fflags", "+bitexact", "-acodec", "pcm_s24le"],
    },
    {
        "index": 15, "num": "十五", "id": "P", "name": "曲谱修整",
        "tag": "曲谱", "tag_bg": "#10263d", "tag_fg": "#5eead4",
        "desc": "轻量整理旋律线和中频轮廓，适合修后声音偏低、主旋律不够清楚的素材。",
        "engine": "ffmpeg", "role": "旋律回稳",
        "af": ("highpass=f=34,"
               "equalizer=f=70:g=-1.8:width_type=h:width=55,"
               "equalizer=f=180:g=0.4:width_type=h:width=110,"
               "equalizer=f=520:g=0.8:width_type=h:width=420,"
               "equalizer=f=1600:g=1.2:width_type=h:width=1100,"
               "equalizer=f=3900:g=1.6:width_type=h:width=2500,"
               "equalizer=f=8200:g=0.8:width_type=h:width=4300,"
               "equalizer=f=15000:g=-0.6:width_type=h:width=5000,"
               "acompressor=threshold=-21dB:ratio=1.12:attack=24:release=220:makeup=1.0,"
               "alimiter=limit=0.975"),
        "extra_args": ["-map_metadata", "-1", "-ar", "48000", "-ac", "2", "-acodec", "pcm_s16le"],
    },
    {
        "index": 16, "num": "十六", "id": "Q", "name": "自然母带",
        "tag": "母带", "tag_bg": "#1f2937", "tag_fg": "#93c5fd",
        "desc": "轻量统一响度和空间细节，适合最后定稿，尽量不改变旋律和原有人声。",
        "engine": "ffmpeg", "role": "自然定稿",
        "af": ("highpass=f=30,"
               "equalizer=f=90:g=-0.6:width_type=h:width=80,"
               "equalizer=f=300:g=0.4:width_type=h:width=220,"
               "equalizer=f=1200:g=0.5:width_type=h:width=900,"
               "equalizer=f=3200:g=0.7:width_type=h:width=1800,"
               "equalizer=f=7600:g=0.35:width_type=h:width=3600,"
               "acompressor=threshold=-22dB:ratio=1.08:attack=30:release=260:makeup=1.0,"
               "alimiter=limit=0.975"),
        "extra_args": ["-map_metadata", "-1", "-ar", "48000", "-ac", "2", "-acodec", "pcm_s16le"],
    },
    {
        "index": 17, "num": "十七", "id": "R", "name": "DJ低频保真",
        "tag": "电音", "tag_bg": "#102a2a", "tag_fg": "#5eead4",
        "desc": "给低频重、鼓组密的曲子用，减少扁平化，保留尾段能量、鼓点弹性和空气感。",
        "engine": "sox", "role": "低频保真",
        "sox_args": ["highpass", "18", "pitch", "-14", "bass", "1.6",
                     "treble", "-0.06", "9000", "treble", "-0.45", "12500",
                     "treble", "-0.9", "17000", "lowpass", "18500",
                     "reverb", "7", "24", "36", "42",
                     "gain", "-n", "-0.9", "rate", "48000", "dither", "-s"],
    },
    {
        "index": 18, "num": "十八", "id": "S", "name": "小体积轻量",
        "tag": "轻量", "tag_bg": "#10263d", "tag_fg": "#5eead4",
        "desc": "轻度保真整理，保留低频和尾段动态，适合小体积 MP3 输出。",
        "engine": "ffmpeg", "role": "小体积输出",
        "af": ("highpass=f=24,"
               "lowpass=f=18500,"
               "equalizer=f=70:g=0.35:width_type=h:width=70,"
               "equalizer=f=160:g=0.25:width_type=h:width=120,"
               "equalizer=f=2600:g=-0.18:width_type=h:width=1400,"
               "equalizer=f=7600:g=-0.12:width_type=h:width=3600,"
               "acompressor=threshold=-22dB:ratio=1.10:attack=35:release=260:makeup=1.0,"
               "alimiter=limit=0.97"),
        "extra_args": ["-map_metadata", "-1", "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le"],
    },
]

SCHEME_BY_ID = {int(s["index"]): s for s in SCHEMES}

# Show the complete scheme library. Style presets can still choose shorter
# chains, but advanced users should see all 18 available routes.
DISPLAY_SCHEME_IDS = list(range(1, 19))
DISPLAY_SCHEMES = [s for s in SCHEMES if int(s["index"]) in DISPLAY_SCHEME_IDS]
MERGED_SCHEME_IDS = []
