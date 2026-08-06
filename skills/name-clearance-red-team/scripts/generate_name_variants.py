#!/usr/bin/env python3
"""
Deterministic name-variant generator: orthographic variants (spacing,
hyphenation, umlaut/diacritic handling, heuristic plurals, single-character
transpositions), a rule-table phonetic substitution per language, and a
bidirectional Latin<->Cyrillic confusable-character table (relevant to
digital-squatting risk, not genuine phonetic transliteration).

Semantic variants (translations, synonyms, reversed word order, acronyms)
are deliberately NOT generated here — a hardcoded translation table would
substitute model knowledge for real research (rule #13). Instead this
script emits an empty "semantic_hint" slot per requested language; the
agent fills it in per METHODIK.md Phase 3 and appends the result to
variants.json.

Usage: python3 generate_name_variants.py "<name>" [--languages de,en] [--out <path>]
"""
import argparse
import datetime
import json
import re
import sys
import unicodedata

UMLAUT_TO_ASCII = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}

PHONETIC_RULES = {
    "de": [("ph", "f"), ("ck", "k"), ("tz", "z"), ("v", "f"), ("y", "i"), ("ei", "ai"), ("ai", "ei"), ("z", "ts")],
    "en": [("ph", "f"), ("ck", "k"), ("c", "k"), ("z", "s"), ("y", "i")],
}

# Common Latin<->Cyrillic look-alike characters. Deliberately small and
# hand-picked for visual confusability, not a full transliteration scheme.
LATIN_TO_CYRILLIC = {
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с",
    "y": "у", "x": "х", "i": "і", "j": "ј", "s": "ѕ", "h": "һ",
}
CYRILLIC_TO_LATIN = {v: k for k, v in LATIN_TO_CYRILLIC.items()}


def diacritic_strip(word):
    decomposed = unicodedata.normalize("NFKD", word)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def umlaut_ascii_variants(word):
    out = set()
    digraph = word
    for umlaut, ascii_eq in UMLAUT_TO_ASCII.items():
        digraph = digraph.replace(umlaut, ascii_eq)
    if digraph != word:
        out.add(digraph)
    stripped = diacritic_strip(word)
    if stripped != word:
        out.add(stripped)
    reverse = word
    for umlaut, ascii_eq in sorted(UMLAUT_TO_ASCII.items(), key=lambda kv: -len(kv[1])):
        reverse = reverse.replace(ascii_eq, umlaut)
    if reverse != word:
        out.add(reverse)
    out.discard(word)
    return sorted(out)


def spacing_variants(word):
    out = set()
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word)
    out.add(camel_split)
    out.add(camel_split.replace(" ", "-"))
    out.add(camel_split.replace(" ", ""))
    if " " in word:
        out.add(word.replace(" ", "-"))
        out.add(word.replace(" ", ""))
    if "-" in word:
        out.add(word.replace("-", " "))
        out.add(word.replace("-", ""))
    out.discard(word)
    out.discard("")
    return sorted(out)


def adjacent_transpositions(word):
    out = set()
    for i in range(len(word) - 1):
        chars = list(word)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        out.add("".join(chars))
    out.discard(word)
    return sorted(out)


def plural_heuristic_de(word):
    if word.endswith(("er", "en", "el", "s")):
        return None
    if word.endswith("e"):
        return word + "n"
    return word + "e"


def plural_heuristic_en(word):
    if word.endswith(("s", "x", "z")) or word.endswith(("ch", "sh")):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2].lower() not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def plural_variants(word, languages):
    out = []
    if "de" in languages:
        p = plural_heuristic_de(word)
        if p and p != word:
            out.append((p, "de"))
    if "en" in languages:
        p = plural_heuristic_en(word)
        if p and p != word:
            out.append((p, "en"))
    return out


def phonetic_variants(word, languages):
    out = []
    seen = set()
    for lang in languages:
        for pattern, replacement in PHONETIC_RULES.get(lang, []):
            for candidate in (word, word.lower()):
                if pattern in candidate:
                    variant = candidate.replace(pattern, replacement)
                    if variant != word and variant not in seen:
                        seen.add(variant)
                        out.append((variant, lang, pattern))
    return out


def transliteration_variants(word):
    out = []
    lower = word.lower()
    if any(ch in LATIN_TO_CYRILLIC for ch in lower):
        translit = "".join(LATIN_TO_CYRILLIC.get(ch, ch) for ch in lower)
        if translit != lower:
            out.append(translit)
    if any(ch in CYRILLIC_TO_LATIN for ch in word):
        back = "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in word)
        if back != word:
            out.append(back)
    return out


def generate(name, languages):
    variants = []

    def add(variant, cls, rule, priority):
        if variant and variant != name:
            variants.append({"variant": variant, "class": cls, "rule": rule, "search_priority": priority})

    for v in umlaut_ascii_variants(name):
        add(v, "orthographic", "umlaut_ascii", "high")
    for v in spacing_variants(name):
        add(v, "orthographic", "spacing_hyphenation", "high")
    for v in adjacent_transpositions(name):
        add(v, "orthographic", "typo_transpose", "medium")
    for v, lang in plural_variants(name, languages):
        add(v, "orthographic", f"plural_{lang}", "medium")
    for v, lang, rule in phonetic_variants(name, languages):
        add(v, "phonetic", f"homophone_{lang}_{rule}", "medium")
    for v in transliteration_variants(name):
        add(v, "transliteration", "latin_cyrillic_confusable", "low")

    # dedupe, keep first occurrence (highest-priority rule wins on a tie)
    seen = set()
    deduped = []
    for entry in variants:
        if entry["variant"] not in seen:
            seen.add(entry["variant"])
            deduped.append(entry)

    semantic_hints = [
        {
            "language": lang,
            "translation": None,
            "synonyms": [],
            "acronym": None,
            "note": "fill in per METHODIK.md Phase 3, then append to variants.json",
        }
        for lang in languages
    ]

    return {
        "input": name,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "variants": deduped,
        "semantic_hint": semantic_hints,
    }


def render_summary(result):
    lines = [f"# Variants for '{result['input']}' ({len(result['variants'])} generated)"]
    by_class = {}
    for entry in result["variants"]:
        by_class.setdefault(entry["class"], []).append(entry["variant"])
    for cls, items in by_class.items():
        lines.append(f"\n## {cls} ({len(items)})")
        lines.extend(f"- {item}" for item in items)
    lines.append(f"\n## semantic_hint slots to fill ({len(result['semantic_hint'])})")
    lines.extend(f"- {slot['language']}: not yet filled" for slot in result["semantic_hint"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--languages", default="de,en")
    parser.add_argument("--out")
    args = parser.parse_args()

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    result = generate(args.name, languages)

    print(render_summary(result))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    else:
        print("\n---\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
