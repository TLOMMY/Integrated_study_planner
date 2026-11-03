# -*- coding: utf-8 -*-
"""
课程简称 / 别名与模糊匹配（任务搜索、联网搜索共用）。

  expand("高数")          -> ["高数", "高等数学"]                 简称 ↔ 全称（双向）
  expand("高数作业")      -> ["高数作业", "高等数学作业"]         词内的简称也会替换
  fuzzy_match("高数", "高等数学期中")  -> True                    按字顺序包含（字间允许少量间隔）
  expand_for_search("高数 期末")  -> "高等数学 期末"              联网搜索：只展开明确无歧义的简称
"""

import re
import unicodedata
from typing import Dict, Iterable, List, Set

# 全称: 常见简称（只收公认、几乎不会误伤的写法）
COURSE_ALIASES: Dict[str, List[str]] = {
    "高等数学": ["高数"],
    "线性代数": ["线代"],
    "概率论与数理统计": ["概率论", "概统", "概率统计", "概率"],
    "大学物理": ["大物"],
    "大学物理实验": ["大物实验", "物理实验"],
    "大学英语": ["大英"],
    "马克思主义基本原理": ["马原", "马克思原理"],
    "毛泽东思想和中国特色社会主义理论体系概论": ["毛概", "毛中特"],
    "习近平新时代中国特色社会主义思想概论": ["习概", "习思想"],
    "思想道德与法治": ["思修", "思政", "思想道德修养与法律基础"],
    "中国近现代史纲要": ["近代史", "史纲", "近现代史"],
    "形势与政策": ["形策", "形政"],
    "军事理论": ["军理"],
    "C语言程序设计": ["C语言", "C程序设计"],
    "C++程序设计": ["C++", "CPP", "C加加"],
    "Java程序设计": ["Java"],
    "Python程序设计": ["Python"],
    "数据结构": ["数据结构与算法", "数构"],
    "离散数学": ["离散"],
    "数字电子技术": ["数电"],
    "模拟电子技术": ["模电"],
    "电路分析": ["电路"],
    "计算机网络": ["计网"],
    "计算机组成原理": ["计组"],
    "操作系统": ["操统", "OS"],
    "数据库原理": ["数据库", "数据库系统"],
    "编译原理": ["编译"],
    "复变函数": ["复变"],
    "数学分析": ["数分"],
    "高等代数": ["高代"],
    "常微分方程": ["常微"],
    "工程制图": ["工图", "画法几何"],
    "大学英语四级": ["四级", "CET4", "CET-4"],
    "大学英语六级": ["六级", "CET6", "CET-6"],
}

# 联网搜索时不展开的简称：单独出现时含义太宽，展开反而把结果带偏
_SEARCH_KEEP = {"概率", "电路", "离散", "编译", "数据库", "Java", "Python", "C++", "CPP", "OS", "四级", "六级",
                "CET4", "CET-4", "CET6", "CET-6", "思政", "物理实验", "数据库系统", "数据结构与算法",
                "C语言", "C程序设计", "C加加"}


def normalize(text) -> str:
    """全角转半角、去空白、英文小写，便于比较。"""
    value = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"\s+", "", value).lower()


def _build_index() -> Dict[str, Set[str]]:
    index: Dict[str, Set[str]] = {}
    for full, shorts in COURSE_ALIASES.items():
        group = {full, *shorts}
        for word in group:
            index.setdefault(normalize(word), set()).update(group - {word})
    return index


_INDEX = _build_index()
# 按长度从长到短替换，避免"大物实验"先被"大物"截走
_WORDS = sorted(_INDEX, key=len, reverse=True)


def expand(query: str, limit: int = 8) -> List[str]:
    """
    返回 [原词, 同义写法...]（去重、保序，最多 limit 个）：
    1. 整个词就是某门课的简称 / 全称 → 加上其余写法；
    2. 词里包含简称（如"高数作业"）→ 再加上换成其他写法后的词（"高等数学作业"）。
    """
    raw = str(query or "").strip()
    key = normalize(raw)
    if not key:
        return []
    result: List[str] = [raw]

    def add(word: str) -> None:
        if word and normalize(word) not in {normalize(x) for x in result}:
            result.append(word)

    for other in sorted(_INDEX.get(key, ()), key=len, reverse=True):
        add(other)
    if key not in _INDEX:
        for word in _WORDS:
            if len(word) >= 2 and word in key:
                for other in sorted(_INDEX[word], key=len, reverse=True):
                    add(key.replace(word, normalize(other)))
                break
    return result[:limit]


_CJK = re.compile(r"^[一-鿿]{2,6}$")


def fuzzy_match(query: str, text: str) -> bool:
    """
    "按字顺序包含"：query 的每个字按顺序出现在 text 里，且首尾跨度不超过 2 倍字数
    （高数 → 高等数学、线代 → 线性代数；"数学"不会匹配"数据结构学习"这类相隔很远的字）。
    只对 2-6 个汉字的查询生效，英文 / 数字仍按普通包含匹配。
    """
    q, t = normalize(query), normalize(text)
    if not q or not t:
        return False
    if q in t:
        return True
    if not _CJK.match(q):
        return False
    limit = len(q) * 2
    for start, char in enumerate(t):
        if char != q[0]:
            continue
        cursor = start
        for wanted in q[1:]:
            cursor = t.find(wanted, cursor + 1)
            if cursor < 0 or cursor - start + 1 > limit:
                break
        else:
            return True
    return False


def matches(query: str, texts: Iterable[str]) -> bool:
    """任意一种写法（含别名）在任意字段里出现，或按字顺序包含。"""
    fields = [t for t in texts if t]
    for variant in expand(query):
        if any(normalize(variant) in normalize(field) or fuzzy_match(variant, field) for field in fields):
            return True
    return False


def like_patterns(query: str) -> List[str]:
    """SQL LIKE 预筛用的模式：每种写法一个 %词%；纯汉字短词再加一个 %字%字% 的顺序模式（精确判断交给 matches）。"""
    patterns = []
    for variant in expand(query):
        clean = variant.replace("%", "").replace("_", "").strip()
        if not clean:
            continue
        patterns.append(f"%{clean}%")
        if _CJK.match(normalize(clean)):
            patterns.append("%" + "%".join(normalize(clean)) + "%")
    return list(dict.fromkeys(patterns))


def expand_for_search(query: str) -> str:
    """联网搜索发查询前：把查询里明确无歧义的课程简称换成全称（"高数 期末复习" → "高等数学 期末复习"）。"""
    text = str(query or "")
    if not text.strip():
        return text
    full_names = set(COURSE_ALIASES)
    # 全称太长（如"毛泽东思想和……概论"）时搜索引擎反而不如简称好用，不展开
    words = (w for full, shorts in COURSE_ALIASES.items() if len(full) <= 10 for w in shorts if w not in _SEARCH_KEEP)
    for word in sorted(words, key=len, reverse=True):
        full = next(f for f, shorts in COURSE_ALIASES.items() if word in shorts)
        if word not in text or full in text:
            continue
        # 简称是其他全称的一部分时（如"大物"在"大物实验"里）跳过，交给更长的那条
        if any(word in other and other in text for other in full_names if other != full):
            continue
        text = re.sub(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z+])", full, text, count=1)
    return text
