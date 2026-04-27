import re
from typing import Dict, List, Pattern, Tuple

SIGNAL_PATTERNS: Dict[str, List[Pattern[str]]] = {
    "urgency": [
        re.compile(pattern) for pattern in [
            r"限時",
            r"馬上",
            r"立即",
            r"今天到期",
            r"緊急",
            r"馬上處理",
            r"趕快",
            r"最後機會",
            r"急件",
            r"限時優惠",
        ]
    ],
    "gift_or_prize": [
        re.compile(pattern) for pattern in [
            r"免費",
            r"中獎",
            r"獲得",
            r"贈品",
            r"禮品",
            r"恭喜",
            r"抽獎",
            r"禮券",
            r"好禮",
            r"大獎",
        ]
    ],
    "threat": [
        re.compile(pattern) for pattern in [
            r"帳號停用",
            r"法院傳票",
            r"警察",
            r"違規",
            r"凍結",
            r"停用",
            r"罰款",
            r"強制",
            r"處罰",
            r"違反",
        ]
    ],
    "impersonation": [
        re.compile(pattern) for pattern in [
            r"土地銀行",
            r"玉山銀行",
            r"台灣銀行",
            r"健保署",
            r"警政署",
            r"黑貓",
            r"7-11",
            r"全家",
            r"郵局",
            r"客服",
            r"郵局",
            r"銀行客服",
            r"客服人員",
        ]
    ],
    "payment_request": [
        re.compile(pattern) for pattern in [
            r"付款",
            r"轉帳",
            r"匯款",
            r"繳費",
            r"付費",
            r"手續費",
            r"代收",
        ]
    ],
}


def analyze_message_signals(text: str) -> List[str]:
    """Extract fraud-related signals from sanitized message text."""
    if not isinstance(text, str) or not text.strip():
        return []

    normalized = text.lower()
    signals: List[str] = []

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(normalized):
                signals.append(signal_name)
                break

    return signals


def analyze_message_signals_with_matches(text: str) -> List[Tuple[str, str]]:
    """Return detected signals and the matched keyword/pattern string."""
    if not isinstance(text, str) or not text.strip():
        return []

    normalized = text.lower()
    results: List[Tuple[str, str]] = []

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                results.append((signal_name, match.group(0)))
                break

    return results
