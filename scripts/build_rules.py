#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一构建三端（Clash / Surge / Loon）兼容的纯文本 classical 规则集：
1. generated/ai-suite.list : TannayeJ AI 源 + personal-ai.list
2. generated/tiktok.list   : blackmatrix7 TikTok 源，补齐缺失的海外 TikTok CDN / Shop / Live 域名
"""

import re
import sys
import urllib.request
from pathlib import Path
from typing import Iterable, Set

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated"
PERSONAL_AI = ROOT / "personal-ai.list"

ALLOWED_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6"}

AI_VENDORS = [
    "openai", "claude", "gemini", "grok", "mistral", "meta-ai", "perplexity",
    "poe", "openrouter", "github-copilot", "microsoft-copilot", "cursor",
    "windsurf", "midjourney", "stability-ai", "runway", "pika", "suno",
    "elevenlabs",
]
AI_BASE_URL = "https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/{vendor}.yaml"

TIKTOK_URLS = [
    "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/TikTok/TikTok.list",
]

# 补齐 blackmatrix7 缺失的海外 TikTok CDN / Shop / Live 域名（不含国内字节系）
TIKTOK_EXTRA_RULES = {
    "DOMAIN-SUFFIX,bytefcdn-oversea.com",
    "DOMAIN-SUFFIX,bytefcdn-ttpeu.com",
    "DOMAIN-SUFFIX,byteglb.com",
    "DOMAIN-SUFFIX,byteicdn.com",
    "DOMAIN-SUFFIX,byteigtm.com",
    "DOMAIN-SUFFIX,byteintl.com",
    "DOMAIN-SUFFIX,byteintl.net",
    "DOMAIN-SUFFIX,byteoversea.net",
    "DOMAIN-SUFFIX,bytetcdn.com",
    "DOMAIN-SUFFIX,sgsnssdk.com",
    "DOMAIN-SUFFIX,tiktok-usts.net",
    "DOMAIN-SUFFIX,tiktok.in",
    "DOMAIN-SUFFIX,tiktokcdn-eu.com",
    "DOMAIN-SUFFIX,tiktokcdn-eu.net",
    "DOMAIN-SUFFIX,tiktokcdn-in.com",
    "DOMAIN-SUFFIX,tiktokglobalshop.com",
    "DOMAIN-SUFFIX,tiktokglobalshopv.com",
    "DOMAIN-SUFFIX,tiktokshop.com",
    "DOMAIN-SUFFIX,tiktokstaticb.com",
    "DOMAIN-SUFFIX,tiktokv.eu",
    "DOMAIN-SUFFIX,tiktokw.us",
    "DOMAIN-SUFFIX,tlivecdn.com",
    "DOMAIN-SUFFIX,tlivepush.com",
    "DOMAIN-SUFFIX,ttadsmanager.com",
    "DOMAIN-SUFFIX,ttapis.com",
    "DOMAIN-SUFFIX,ttdns2.com",
    "DOMAIN-SUFFIX,ttlivecdn.com",
    "DOMAIN-SUFFIX,ttoversea.net",
    "DOMAIN-SUFFIX,ttoverseaus.net",
    "DOMAIN-SUFFIX,ttwstatic.com",
    "DOMAIN-SUFFIX,tzvbfs.com",
}


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "personal-proxy-rules-builder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return resp.read().decode("utf-8")


def fetch_first_ok(urls: Iterable[str]) -> str:
    last_err = None
    for url in urls:
        try:
            return fetch_text(url)
        except Exception as exc:
            last_err = exc
            print(f"[WARN] 拉取失败 {url}: {exc}", file=sys.stderr)
    raise RuntimeError(f"所有候选源均拉取失败: {last_err}")


def parse_lines(content: str, excluded_values: Set[str] = None, skipped: list = None) -> Set[str]:
    rules: Set[str] = set()
    excluded_values = excluded_values or set()
    for raw_line in content.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or line.startswith("payload:"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()

        line = re.sub(r"\s+#.*$", "", line).strip()
        if (line.startswith("'") and line.endswith("'")) or (
            line.startswith('"') and line.endswith('"')
        ):
            line = line[1:-1].strip()

        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue

        rule_type = parts[0].upper()
        if rule_type not in ALLOWED_TYPES:
            if skipped is not None:
                skipped.append(line)
            continue

        raw_val = parts[1]
        if raw_val.lower() in excluded_values:
            if skipped is not None:
                skipped.append(f"[excluded] {line}")
            continue

        value = raw_val.lower() if rule_type in ("DOMAIN", "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6") else raw_val
        extra = [p.lower() for p in parts[2:] if p.lower() == "no-resolve"]
        rules.add(",".join([rule_type, value] + extra))

    return rules


def write_ruleset(path: Path, header_comments: list, rules: Set[str]) -> None:
    lines = header_comments + [f"# Total rules: {len(rules)}", ""] + sorted(rules)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_ai() -> None:
    merged: Set[str] = set()
    skipped = []
    for vendor in AI_VENDORS:
        text = fetch_text(AI_BASE_URL.format(vendor=vendor))
        merged |= parse_lines(text, skipped=skipped)

    if PERSONAL_AI.exists():
        merged |= parse_lines(PERSONAL_AI.read_text(encoding="utf-8"), skipped=skipped)

    if len(merged) < 50:
        raise RuntimeError(f"AI 规则合并结果异常过少（仅 {len(merged)} 条）")

    write_ruleset(
        OUT_DIR / "ai-suite.list",
        [
            "# Auto-generated by scripts/build_rules.py",
            "# Sources: TannayeJ/ai-vendor-rules (19 vendors) + personal-ai.list",
        ],
        merged,
    )
    print(f"[OK] ai-suite.list: {len(merged)} 条（已过滤 {len(skipped)} 条）")


def build_tiktok() -> None:
    skipped = []
    text = fetch_first_ok(TIKTOK_URLS)
    rules = parse_lines(text, excluded_values=TIKTOK_EXCLUDED_VALUES, skipped=skipped)

    if len(rules) < 20:
        raise RuntimeError(f"TikTok 规则清洗结果异常过少（仅 {len(rules)} 条）")

    write_ruleset(
        OUT_DIR / "tiktok.list",
        [
            "# Auto-generated by scripts/build_rules.py",
            "# Source: luestr/ProxyResource TikTok.yaml (domestic ByteDance & IP-ASN filtered)",
        ],
        rules,
    )
    print(f"[OK] tiktok.list: {len(rules)} 条（已过滤 {len(skipped)} 条）")
    if skipped:
        print("  TikTok 过滤明细:", skipped)


def main() -> int:
    if OUT_DIR.exists() and not OUT_DIR.is_dir():
        print(f"[ERROR] {OUT_DIR} 当前是一个文件而非目录，请先在仓库中删除它。", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        build_ai()
        build_tiktok()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
