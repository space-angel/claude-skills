#!/usr/bin/env python3
"""ko-tech-prose 후보 검출기.

한국어 기술 문서에서 문장 규칙 위반 '후보'를 찾는다. 판정은 하지 않는다.
정규식만으로는 정밀도가 20~53%에 그치기 때문에(README의 측정치 참고),
이 스크립트는 재현율만 담당하고 최종 판정은 호출한 에이전트가 한다.

사용법:
    python3 detect.py <파일.md> [파일2.md ...]
    python3 detect.py --json <파일.md>
    cat draft.md | python3 detect.py -

출력은 규칙 ID, 티어, 줄 번호, 걸린 표현, 해당 문장이다.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 규칙 정의
#
# tier A — 패턴이 좁다. 걸리면 거의 위반이다. 판정 부담이 작다.
# tier B — 패턴이 넓다. 후보일 뿐이다. 반드시 문맥을 보고 판정해야 한다.
# tier C — 문서 전체를 봐야 판단할 수 있다. 문장 단위 정규식으로는 못 잡는다.
# ---------------------------------------------------------------------------

# '의'로 끝나는 명사. 조사 '의'로 오인하면 "회의 준비의"가 의-연쇄로 잡힌다.
UI_NOUN = (
    r"(?:회의|정의|강의|주의|의의|편의|문의|합의|논의|협의|거의|사의"
    r"|동의|유의|임의|고의|호의|성의|예의|타의|자의|의)"
)


@dataclass(frozen=True)
class Rule:
    rid: str
    tier: str
    name: str
    pattern: str
    hint: str


SENTENCE_RULES: list[Rule] = [
    # --- tier A ------------------------------------------------------------
    Rule(
        "S2", "A", "이중피동·불필요한 수동",
        r"되어지|여집니다|되어야 (?:한다|합니다|해요)|하게 되(?:며|었|ㅂ니다|습니다)",
        "행동 주체를 드러내 능동형으로 바꾼다. '설정이 완료되어야 합니다' → '설정을 완료하세요'",
    ),
    Rule(
        "B2", "A", "메타 담화",
        r"아시다시피|앞서 (?:말했|언급했|설명했|살펴봤)|결론적으로|살펴보자|다시 말해|주지하다시피",
        "통째로 지운다. 내용이 아니라 내용에 대한 언급이다.",
    ),
    Rule(
        "K1", "A", "잉여 한자어",
        r"(?:을|를) (?:수행|진행|실시)(?:합니다|한다|해요|했다|하세요)|작업을 (?:수행|진행)",
        "동사 하나로 줄인다. '삭제하는 작업을 수행합니다' → '삭제합니다'",
    ),
    Rule(
        "K3", "A", "의-연쇄",
        rf"(?<![가-힣])(?!{UI_NOUN} )[가-힣]{{2,}}의 (?!{UI_NOUN} )[가-힣]{{2,}}의 ",
        "'의'를 둘 이상 겹치지 않는다. '훈련 데이터의 레이블의 분포' → '훈련 데이터에서 레이블 분포'",
    ),
    # --- tier B ------------------------------------------------------------
    Rule(
        "K2", "A", "번역체 조사구",
        r"에 있어서|(?:으)?로 인하여|(?:을|를) 통해서(?:는)? |에 다름 아니",
        "동사로 푼다. '설계에 있어서 중요한' → '설계할 때 중요한'",
    ),
    Rule(
        "C2", "B", "모호한 수식어",
        r"일부 |다양한 |여러 가지|적절히|필요에 따라|가능성이 있|등을 통해|충분히 ",
        "수치나 고유명으로 바꿀 수 있을 때만 잡는다. 등급 정의·인용문은 그대로 둔다.",
    ),
    Rule(
        # '했는데', '좋은데' 같은 대조 연결은 정상이라 뺐다. 측정에서 오탐의 대부분이었다.
        "B1", "B", "겹문장 접속",
        r"[가-힣]며, |[가-힣]하고서, ",
        "대등한 항목 나열이면 그대로 둔다. 서로 다른 생각이 이어붙었으면 자른다.",
    ),
    Rule(
        "C1", "B", "명사화",
        r"(?:이|가) 가능(?:합니다|하다|해요)|(?:화|처리|설정|적용|구현|배포) (?:진행|수행|필요)",
        "명사 대신 동사로. '배포 수행이 필요합니다' → '배포하세요'",
    ),
    Rule(
        "S1", "B", "도구가 주어",
        r"(?:라이브러리|시스템|서비스|모듈|스크립트|플랫폼|툴)(?:는|은|이|가) [^.\n]{0,30}(?:을|를) "
        r"(?:수행|처리|제공)",
        "도구의 동작 자체를 설명하는 문장이면 그대로 둔다. 독자가 할 일이면 독자를 주어로.",
    ),
]

# 문장 길이. 한국어 기술 문서에서 80자를 넘으면 생각이 둘 이상 섞였을 확률이 높다.
LONG_SENTENCE = 80

# tier C — 문서 전역 규칙
SYNONYM_GROUPS: list[tuple[str, list[str]]] = [
    ("추가", ["추가", "첨부", "삽입", "등록"]),
    ("설정", ["설정", "세팅", "구성"]),
    ("조회", ["조회", "검색", "탐색", "질의"]),
    ("삭제", ["삭제", "제거", "지우기"]),
    ("실행", ["실행", "구동", "기동"]),
    ("반환", ["반환", "리턴", "돌려줌"]),
]

SPELLING_PAIRS: list[tuple[str, str]] = [
    ("프런트엔드", "프론트엔드"),
    ("백엔드", "백앤드"),
    ("데이터", "데이타"),
    ("서비스", "써비스"),
    ("업데이트", "업뎃"),
]

ABBREV = re.compile(r"(?<![A-Za-z])[A-Z]{2,6}(?![A-Za-z])")

# 한 번 스치는 약어는 독자를 막지 않는다. 문서 안에서 이만큼 반복될 때만 잡는다.
ABBREV_MIN_COUNT = 3

# 풀어쓸 필요 없는 것들. 크게 셋이다.
ABBREV_SKIP = {
    # 1) 업계 관용어 — 풀어쓰면 오히려 읽기 나쁘다
    "API", "URL", "URI", "HTTP", "HTTPS", "JSON", "YAML", "TOML", "HTML", "CSS",
    "SQL", "CLI", "GUI", "TUI", "UI", "UX", "ID", "OS", "PDF", "CSV", "TSV",
    "MD", "AI", "LLM", "RAG", "MCP", "SDK", "IDE", "VM", "RAM", "CPU", "GPU",
    "SSD", "HDD", "DNS", "TCP", "UDP", "SSH", "FTP", "SMTP", "REST", "RPC",
    "GRPC", "CRUD", "ORM", "JWT", "SSO", "CDN", "TTL", "LRU", "DAG", "FSM",
    "UUID", "ASCII", "UTF", "XML", "SVG", "PNG", "JPG", "JPEG", "GIF", "ZIP",
    "DB", "CI", "CD", "GIT", "NPM", "AWS", "GCP", "SaaS", "CORS", "DOM", "SPA",
    "SSR", "CSR", "SEO", "RSS", "IP", "MAC", "USB", "RGB", "PPI", "DPI",
    # 2) 영어 단어를 대문자로 쓴 것 — 약어가 아니다
    "OK", "NG", "YES", "NO", "NOT", "AND", "OR", "ALL", "ANY", "NEW", "OLD",
    "MORE", "LESS", "INPUT", "OUTPUT", "TRUE", "FALSE", "NULL", "NONE", "TODO",
    "FIXME", "NOTE", "WARN", "ERROR", "DEBUG", "INFO", "TIP", "FAQ", "README",
    "BEFORE", "AFTER", "START", "END", "STOP", "NEXT", "PREV", "MAIN", "TEST",
    # 3) SQL·HTTP 예약어
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "JOIN", "LIMIT", "OFFSET",
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "MAX", "MIN",
    "SUM", "AVG", "COUNT", "STDEV", "GET", "POST", "PUT", "PATCH", "HEAD",
    # 4) 조직·표준·시간대
    "ACM", "IEEE", "ISO", "OMG", "WHO", "RFC", "GMT", "UTC", "KST",
}

# ---------------------------------------------------------------------------
# 보호 구역 — 검사하지 않는다
# ---------------------------------------------------------------------------

FENCE_LINE = re.compile(r"^\s*(```|~~~)")
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK_TARGET = re.compile(r"\]\([^)\n]*\)")
IMAGE = re.compile(r"!\[[^\]]*\]")
URL = re.compile(r"https?://\S+")
# [[위키링크]]는 문장이 아니라 참조다. 나열되면 긴 문장으로 오인된다.
WIKILINK = re.compile(r"\[\[[^\]]*\]\]")


def mask_line(line: str) -> str:
    """줄 안의 코드·링크·URL을 공백으로 덮는다. 길이는 보존해 열 번호가 어긋나지 않는다."""
    for pat in (INLINE_CODE, WIKILINK, LINK_TARGET, IMAGE, URL):
        line = pat.sub(lambda m: " " * len(m.group()), line)
    return line


HANGUL = re.compile(r"[가-힣]")


def is_korean_prose(s: str) -> bool:
    """한글이 절반에 못 미치면 한국어 산문이 아니다. 영문 인용·코드 잔여물을 거른다."""
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 10:
        return False
    return sum(1 for c in letters if HANGUL.match(c)) / len(letters) >= 0.5


def prepare(text: str) -> list[tuple[int, str, str]]:
    """(줄번호, 원본, 검사대상) 목록을 만든다. 보호 구역은 검사대상이 빈 문자열이다."""
    # frontmatter는 줄 수를 유지한 채 비운다
    fm = FRONTMATTER.match(text)
    if fm:
        blanked = "\n" * fm.group().count("\n")
        text = blanked + text[fm.end():]

    out: list[tuple[int, str, str]] = []
    in_fence = False
    for i, raw in enumerate(text.splitlines(), start=1):
        if FENCE_LINE.match(raw):
            in_fence = not in_fence
            out.append((i, raw, ""))
            continue
        if in_fence:
            out.append((i, raw, ""))
            continue
        stripped = raw.lstrip()
        # 인용문과 표는 대개 남의 말이거나 정형 데이터다
        if stripped.startswith((">", "|")):
            out.append((i, raw, ""))
            continue
        out.append((i, raw, mask_line(raw)))
    return out


# 문장 끝맺음. '각 절마다 '처럼 '다'로 끝나는 아무 단어에서나 자르면 안 되므로
# 종결 어미를 명시한다. Python 정규식은 가변 길이 lookbehind를 못 쓰기 때문에
# 구분자를 심었다가 나누는 방식을 쓴다.
_ENDING = (
    r"니다|해요|예요|어요|아요|아라|세요|한다|된다|이다|았다|었다|겠다"
    r"|없다|있다|같다|온다|든다|만다|친다|간다|산다|본다|난다"
)
_PUNCT_BREAK = re.compile(r"([.!?])\s+")
_ENDING_BREAK = re.compile(rf"({_ENDING})\s+(?=[가-힣A-Z(\[])")
_SEP = "\x00"


def sentences(line: str) -> list[str]:
    tmp = _PUNCT_BREAK.sub(r"\1" + _SEP, line)
    tmp = _ENDING_BREAK.sub(r"\1" + _SEP, tmp)
    return [s.strip() for s in tmp.split(_SEP) if s.strip()]


# ---------------------------------------------------------------------------
# 검출
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    rule: str
    tier: str
    name: str
    line: int
    match: str
    context: str
    hint: str


def scan(text: str) -> list[Finding]:
    lines = prepare(text)
    findings: list[Finding] = []

    for lineno, raw, target in lines:
        if not target.strip():
            continue
        for rule in SENTENCE_RULES:
            for m in re.finditer(rule.pattern, target):
                ctx = next(
                    (s for s in sentences(raw) if m.group().strip() and m.group().strip() in s),
                    raw.strip(),
                )
                findings.append(
                    Finding(rule.rid, rule.tier, rule.name, lineno,
                            m.group().strip(), ctx.strip()[:160], rule.hint)
                )
        for s in sentences(target):
            if not is_korean_prose(s):
                continue
            body = re.sub(r"[*_#>\-\s]", "", s)
            if len(body) > LONG_SENTENCE:
                findings.append(
                    Finding("B3", "B", "긴 문장", lineno, f"{len(body)}자",
                            s.strip()[:160],
                            f"{LONG_SENTENCE}자를 넘는다. 생각이 둘 이상이면 자른다. 하나면 그대로 둔다.")
                )
            # '에 대한'은 하나만으로는 정상이다. 한 문장에 겹칠 때만 문제가 된다.
            stacked = re.findall(r"에 (?:대한|대해|대하여)", s)
            if len(stacked) >= 2:
                findings.append(
                    Finding("K4", "B", "'에 대한' 중첩", lineno, f"{len(stacked)}회",
                            s.strip()[:160],
                            "한 문장에서 '에 대한'을 겹쳐 쓴다. 하나만 남기고 나머지는 동사로 푼다.")
                )

    findings.extend(scan_global(lines))
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


def scan_global(lines: list[tuple[int, str, str]]) -> list[Finding]:
    """문서 전체를 봐야 판단되는 규칙."""
    out: list[Finding] = []
    body = "\n".join(t for _, _, t in lines)

    # T1 — 같은 개념을 여러 말로 부른다
    for canon, group in SYNONYM_GROUPS:
        used = {w for w in group if re.search(rf"{w}(?:하|한|합|해|했|된|됩|을|를|이|가|\s)", body)}
        if len(used) >= 2:
            first = next(
                (ln for ln, _, t in lines if any(w in t for w in used)), 1
            )
            out.append(Finding(
                "T1", "C", "용어 혼용", first, " / ".join(sorted(used)),
                f"같은 문서에서 {len(used)}가지 표현을 섞어 쓴다",
                f"하나로 통일한다. 문서 전체에서 뜻이 정말 다르면 그대로 둔다. (기준 후보: {canon})",
            ))

    # T2 — 풀어쓰지 않은 약어
    freq = collections.Counter(
        ab for _, _, t in lines for ab in ABBREV.findall(t) if ab not in ABBREV_SKIP
    )
    seen: set[str] = set()
    for lineno, _, target in lines:
        for m in ABBREV.finditer(target):
            ab = m.group()
            if ab in ABBREV_SKIP or ab in seen:
                continue
            if freq[ab] < ABBREV_MIN_COUNT:
                continue
            seen.add(ab)
            # 문서 어디서든 괄호로 풀었으면 통과
            if re.search(rf"{ab}\s*\(|\)\s*{ab}", body):
                continue
            out.append(Finding(
                "T2", "C", "약어 미정의", lineno, ab, target.strip()[:160],
                f"{freq[ab]}번 쓰는데 풀어쓴 곳이 없다. 첫 등장에서 {ab}(전체 표기)로 푼다. "
                "독자에게 관용어면 그대로 둔다.",
            ))

    # T3 — 표기 흔들림
    for good, bad in SPELLING_PAIRS:
        if good in body and bad in body:
            first = next((ln for ln, _, t in lines if bad in t), 1)
            out.append(Finding(
                "T3", "C", "표기 흔들림", first, f"{good} / {bad}",
                "같은 문서에서 두 표기를 섞어 쓴다",
                f"'{good}'으로 통일한다.",
            ))
    return out


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

TIER_LABEL = {"A": "A 확실", "B": "B 후보", "C": "C 전역"}


def render(path: str, findings: list[Finding]) -> str:
    if not findings:
        return f"# {path}\n\n걸린 것 없음.\n"

    lines = [f"# {path}", ""]
    by_tier: dict[str, list[Finding]] = {"A": [], "B": [], "C": []}
    for f in findings:
        by_tier[f.tier].append(f)

    counts = ", ".join(f"{TIER_LABEL[t]} {len(v)}건" for t, v in by_tier.items() if v)
    lines.append(f"후보 {len(findings)}건 — {counts}")
    lines.append("")

    for tier in ("A", "B", "C"):
        items = by_tier[tier]
        if not items:
            continue
        lines.append(f"## tier {TIER_LABEL[tier]}")
        lines.append("")
        for f in items:
            lines.append(f"- **{f.rule} {f.name}** (L{f.line}) — `{f.match}`")
            lines.append(f"  - 문맥: {f.context}")
            lines.append(f"  - 지침: {f.hint}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="한국어 기술 문서 문장 규칙 후보 검출기")
    ap.add_argument("paths", nargs="+", help="검사할 마크다운 파일. '-'는 표준 입력")
    ap.add_argument("--json", action="store_true", help="JSON으로 출력")
    ap.add_argument("--tier", default="ABC", help="검출할 티어만 남긴다 (예: AB)")
    args = ap.parse_args()

    results: dict[str, list[Finding]] = {}
    for p in args.paths:
        if p == "-":
            text, label = sys.stdin.read(), "<stdin>"
        else:
            fp = Path(p)
            if not fp.is_file():
                print(f"파일 없음: {p}", file=sys.stderr)
                return 1
            text, label = fp.read_text(encoding="utf-8"), p
        results[label] = [f for f in scan(text) if f.tier in args.tier.upper()]

    if args.json:
        print(json.dumps(
            {k: [asdict(f) for f in v] for k, v in results.items()},
            ensure_ascii=False, indent=2,
        ))
    else:
        print("\n".join(render(k, v) for k, v in results.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
