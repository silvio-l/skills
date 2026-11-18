#!/usr/bin/env python3
"""Prose linter for redaktion: flags generated-text tells in long-form German or English prose.

Usage:
  prose_lint.py FILE [FILE ...] [--lang de|en] [--json] [--rules] [--stats]
  prose_lint.py - < draft.md

Reads Markdown, plain text or HTML. Front matter, code, URLs, link targets, tables, HTML tags and block
quotes are masked before matching, so quoted sources and code never count against the author.
Errors are strong tells that justify an edit on a single hit; warnings are cluster or density signals
to review, never a quota. Suppress a rule on one line with `prose-ignore: <rule>[, <rule>]` on the same
or the previous line (`all` covers every rule there). Exit 1 when errors remain.

The marketing buzzword lists are shared with the website-creator skill: when its `slop_lint.py` sits next
to this skill (same skills directory), its STRONG_BUZZ and SOFT_BUZZ lists are used, otherwise a small
built-in core list. `--stats` shows which source was used.
"""
import argparse
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True

RULES = {
    # errors: one hit is enough
    "stock-phrase": ("error", "Stock phrase typical of generated text; say the concrete thing instead."),
    "chat-residue": ("error", "Leftover from a chat answer (offer, greeting, sign-off to the requester)."),
    "marketing-buzzword": ("error", "Inflated marketing word; say what concretely changed or happens."),
    "superlative-chain": ("error", "Two or more superlatives or hype words in one sentence; keep one, prove it."),
    "placeholder": ("error", "Unfilled placeholder or TODO; fill it from a source or cut the claim."),
    # warnings: review, do not count
    "soft-buzzword": ("warning", "Two or more vague benefit words in one paragraph; name the effect."),
    "not-only-but": ("warning", "Contrast frame (\"not only X but Y\", \"not X, but Y\") used repeatedly."),
    "staged-reveal": ("warning", "Staged reveal (\"The result?\", \"Here's the thing:\"); state it plainly."),
    "fragment-drama": ("warning", "Run of dramatic one- to three-word sentences."),
    "triad-overuse": ("warning", "Many three-item lists; vary the count or keep only the items that matter."),
    "connector-stack": ("warning", "Paragraph opens several sentences with additive connectors."),
    "em-dash-overuse": ("warning", "Em-dash saturation (in German the spaced en dash is the normal dash)."),
    "rhetorical-questions": ("warning", "Three or more questions in one paragraph."),
    "exclamation-overuse": ("warning", "Many exclamation marks; let the fact carry the excitement."),
    "uniform-rhythm": ("warning", "Sentence lengths barely vary; mix short and long where the thought needs it."),
    "long-sentence": ("warning", "Very long sentence; check whether it reads aloud in one breath per clause."),
    "nominal-style": ("warning", "Noun pile (-ung/-heit/-keit/-ion); turn the main action back into a verb."),
    "long-paragraph": ("warning", "Paragraph over about 120 words; split at the turn of the thought."),
    "generic-heading": ("warning", "Generic heading (Fazit, Einleitung, Key Takeaways); name the topic."),
    "heading-overload": ("warning", "More headings than the text needs; headings are signposts, not decoration."),
    "bold-lead-bullets": ("warning", "Run of bullets that start with a bold label; write it as prose or a table."),
    "emoji-bullets": ("warning", "Emoji used as bullet or heading decoration."),
    "summary-closer": ("warning", "Closing paragraph opens with a summary formula; end on the last real point."),
}

# Strong tells. German and English, matched case-insensitively on masked prose.
STOCK_PHRASES = [
    r"in der heutigen (?:schnelllebigen |digitalen |modernen )?(?:welt|zeit)",
    r"in einer welt,? in der",
    r"(?:lass|lasst|lassen sie) uns (?:gemeinsam |tiefer |direkt )?(?:eintauchen|einen blick werfen)",
    r"tauchen wir (?:tiefer |gemeinsam )?ein",
    r"es ist (?:wichtig|erwähnenswert|entscheidend) (?:zu beachten|zu betonen|hervorzuheben)",
    r"zusammenfassend lässt sich sagen", r"abschließend lässt sich sagen", r"es bleibt spannend",
    r"am ende des tages", r"eine reise durch", r"auf eine reise", r"ein wahres? (?:feuerwerk|meisterwerk)",
    r"ein (?:echter|wahrer) game[- ]?changer", r"in diesem (?:artikel|beitrag) (?:werden wir|tauchen wir|erfährst du alles)",
    r"alles,? was (?:du|sie) (?:über|zu) .{1,40} wissen (?:musst|müssen)", r"ein neues kapitel aufschlagen",
    r"die zukunft (?:ist|beginnt) (?:jetzt|hier|heute)", r"(?:hebt|heben) .{1,40} auf (?:ein neues|das nächste) level",
    r"in today'?s (?:fast[- ]paced |digital |modern |ever[- ]changing )?(?:world|landscape|age)",
    r"in a world where", r"let'?s (?:dive|delve) (?:in|into|deeper)", r"\bdelv(?:e|es|ing)\b",
    r"it'?s (?:important|worth) (?:to note|noting|mentioning)", r"in conclusion", r"at the end of the day",
    r"\ba (?:rich |vibrant )?tapestry\b", r"\ba testament to\b", r"navigat\w* the (?:complex |ever[- ]changing )?landscape",
    r"\bever[- ]evolving\b", r"embark on a journey", r"(?:take|takes) .{1,30} to the next level",
    r"everything you need to know about", r"whether you'?re an? .{1,40} or an? ", r"the future is (?:here|now|bright)",
    r"\bbuckle up\b", r"\bunlock(?:s|ing)? the (?:full )?(?:power|potential)\b",
]
CHAT_RESIDUE = [
    r"^(?:gerne|natürlich|sicher|klar)[!,.] (?:hier|ich)", r"hier (?:ist|sind) (?:dein|deine|ihr|ihre|ein|eine) (?:überarbeitete|entwurf|text|blog)",
    r"ich hoffe,? (?:das|dieser|dieses|diese) (?:hilft|artikel|beitrag|text)", r"lass(?:t)? mich wissen,? (?:ob|wenn)",
    r"(?:melde|meld) dich gerne,? (?:wenn|falls) (?:du|ich)", r"als (?:ki|sprachmodell|ki-modell)",
    r"^(?:certainly|sure|absolutely|of course)[!,.] (?:here|i)", r"^(?:okay,? |sure,? )?here(?:'s| is) (?:a|an|the|your) (?:revised|rewritten|polished|draft|blog post|updated)",
    r"i hope this (?:helps|article|post)", r"feel free to (?:reach out|ask|let me know)", r"let me know if you(?:'d)? (?:want|like|need)",
    r"as an ai\b", r"great question",
]
STAGED_REVEALS = [
    r"(?:^|[.!?]\s+)(?:das|die|der) (?:ergebnis|antwort|lösung|clou|beste|pointe|kicker|haken)\s?[?:]",
    r"(?:^|[.!?]\s+)(?:und )?(?:das )?beste daran\s?[?:]", r"(?:^|[.!?]\s+)spoiler\s?:", r"(?:^|[.!?]\s+)kurz gesagt\s?:",
    r"(?:^|[.!?]\s+)(?:the )?(?:result|answer|catch|kicker|twist|best part)\s?[?:]", r"here'?s the (?:thing|kicker|catch)\s?:",
    r"(?:^|[.!?]\s+)(?:the )?bottom line\s?:", r"(?:^|[.!?]\s+)plot twist\s?:",
]
NOT_ONLY_BUT = [
    r"nicht nur\b[^.!?]{1,90}\bsondern(?: auch)?\b", r"\bnicht\b[^.!?]{1,50}[,;:–—-]\s*sondern\b",
    r"es geht nicht (?:um|darum)\b[^.!?]{1,60}\bsondern\b", r"not (?:only|just|merely)\b[^.!?]{1,90}\bbut(?: also)?\b",
    r"\b(?:it|this|that)(?:'s| is) not (?:just |only |merely )?(?:a |an |about )?[^.!?]{1,40}[,;:—–-]\s*(?:it|this|that)(?:'s| is)\b",
    r"\bisn'?t (?:just|only|merely)\b",
]
SUPERLATIVES = [
    r"größt\w*", r"beste[nmrs]?", r"stärkst\w*", r"schnellst\w*", r"mächtigst\w*", r"ultimativ\w*", r"unglaublich\w*",
    r"gewaltig\w*", r"massiv\w*", r"atemberaubend\w*", r"beispiellos\w*", r"einzigartig\w*", r"phänomenal\w*",
    r"spektakulär\w*", r"sensationell\w*", r"historisch\w*", r"episch\w*",
    r"biggest", r"greatest", r"best", r"fastest", r"most powerful", r"ultimate", r"incredible", r"incredibly",
    r"massive", r"huge", r"stunning", r"unprecedented", r"unparalleled", r"breathtaking", r"epic", r"historic",
    r"mind[- ]blowing", r"jaw[- ]dropping", r"insane(?:ly)?",
]
CONNECTORS = [r"darüber hinaus", r"zudem", r"außerdem", r"ferner", r"des weiteren", r"weiterhin", r"zusätzlich",
              r"furthermore", r"moreover", r"additionally", r"in addition", r"what'?s more"]
GENERIC_HEADINGS = [r"fazit", r"einleitung", r"zusammenfassung", r"das wichtigste in kürze", r"schlussgedanken",
                    r"conclusion", r"introduction", r"key takeaways?", r"final thoughts", r"tl;?dr", r"summary",
                    r"wrapping up", r"the bottom line"]
SUMMARY_CLOSERS = [r"zusammenfassend", r"abschließend", r"alles in allem", r"unterm strich", r"fazit\s?:",
                   r"in summary", r"in conclusion", r"to sum up", r"all in all", r"ultimately", r"in the end", r"overall,"]
PLACEHOLDERS = [r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b", r"\[(?:name|datum|date|zahl|number|link|quelle|source|x+)\]",
                r"\bXX+\s?%", r"lorem ipsum", r"\{\{[^}]*\}\}"]
# Built-in fallback when website-creator's slop_lint is not installed next to this skill.
FALLBACK_STRONG_BUZZ = [r"revolution\w*", r"revolutionär\w*", r"nahtlos\w*", r"seamless\w*", r"bahnbrechend\w*",
                        r"groundbreaking", r"game[- ]?changer\w*", r"cutting[- ]edge", r"next[- ]level",
                        r"state[- ]of[- ]the[- ]art", r"empower\w*", r"supercharg\w*"]
FALLBACK_SOFT_BUZZ = [r"ermöglich\w*", r"optimier\w*", r"effizient\w*", r"innovativ\w*", r"intuitiv\w*",
                      r"leistungsstark\w*", r"mühelos\w*", r"robust\w*", r"powerful", r"intuitive", r"effortless\w*"]
# Long-form words that only count in clusters (never on their own).
EXTRA_SOFT = [r"spannend\w*", r"landschaft", r"ökosystem\w*", r"herzstück", r"vielfältig\w*", r"maßgeblich\w*",
              r"entscheidend\w*", r"crucial", r"pivotal", r"landscape", r"ecosystem", r"vibrant", r"robust",
              r"comprehensive", r"umfassend\w*", r"leverage\w*", r"realm", r"myriad", r"plethora"]

ABBREVIATIONS = ["z. B.", "z.B.", "d. h.", "d.h.", "u. a.", "u.a.", "bzw.", "ca.", "evtl.", "ggf.", "inkl.", "Nr.",
                 "Dr.", "Prof.", "usw.", "etc.", "vgl.", "S.", "e.g.", "i.e.", "vs.", "Mr.", "Mrs.", "Ms.", "approx.",
                 "No.", "Jan.", "Feb.", "Okt.", "Dez.", "Sept."]
DE_HINTS = {"der", "die", "das", "und", "ist", "nicht", "ein", "eine", "mit", "auf", "für", "auch", "sich", "wir",
            "du", "ich", "es", "zu", "den", "dem", "von", "wird", "sind", "wenn", "aber"}
EN_HINTS = {"the", "and", "is", "not", "a", "an", "with", "on", "for", "also", "we", "you", "i", "it", "to", "of",
            "will", "are", "if", "but", "this", "that", "was", "in"}
IGNORE = re.compile(r"prose-ignore:\s*([a-z0-9_,\- ]+)", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705]")
WORD = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß'’-]*")


def load_buzz():
    """Use website-creator's buzzword lists when that skill is installed next to this one."""
    here = Path(__file__).resolve().parent
    cand = here.parent.parent / "website-creator" / "scripts" / "slop_lint.py"
    if cand.is_file():
        try:
            spec = importlib.util.spec_from_file_location("_wc_slop_lint", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return list(mod.STRONG_BUZZ), list(mod.SOFT_BUZZ), "website-creator/scripts/slop_lint.py"
        except Exception:  # a broken sibling must never stop the prose lint
            pass
    return FALLBACK_STRONG_BUZZ, FALLBACK_SOFT_BUZZ, "built-in fallback"


def compile_any(patterns):
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I | re.M)


def mask(text):
    """Blank out everything that is not the author's own prose, keeping line numbers intact."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"\A---\n.*?\n---\n", blank, text, flags=re.S)
    text = re.sub(r"^(```|~~~).*?^\1[^\n]*$", blank, text, flags=re.S | re.M)
    text = re.sub(r"<(script|style|pre|code)\b.*?</\1>", blank, text, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", lambda m: m.group(0) if IGNORE.search(m.group(0)) else blank(m), text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", blank, text)
    text = re.sub(r"\]\([^)\s]*\)", lambda m: "]" + " " * (len(m.group(0)) - 1), text)
    text = re.sub(r"https?://\S+|www\.\S+", blank, text)
    text = re.sub(r"^\s*>.*$", blank, text, flags=re.M)
    text = re.sub(r"^\s*\|.*\|\s*$", blank, text, flags=re.M)
    text = re.sub(r"<[^>\n]+>", blank, text)
    return text


def detect_lang(text):
    words = [w.lower() for w in WORD.findall(text)]
    de = sum(w in DE_HINTS for w in words) + 2 * sum(ch in text for ch in "äöüß")
    en = sum(w in EN_HINTS for w in words)
    return "de" if de >= en else "en"


def split_blocks(masked):
    """Yield (kind, start_line, text) for headings, list items and paragraphs."""
    blocks, buf, start = [], [], 0
    def flush():
        if buf:
            blocks.append(("para", start, " ".join(s.strip() for s in buf)))
            buf.clear()
    for n, line in enumerate(masked.split("\n"), 1):
        s = line.strip()
        if not s:
            flush()
            continue
        if re.match(r"#{1,6}\s", s):
            flush()
            blocks.append(("heading", n, re.sub(r"^#{1,6}\s+", "", s)))
        elif re.match(r"(?:[-*+]|\d+[.)])\s", s) or EMOJI.match(s):
            flush()
            blocks.append(("item", n, s))
        else:
            if not buf:
                start = n
            buf.append(s)
    flush()
    return blocks


def sentences(par):
    protected = par
    for abbr in ABBREVIATIONS:
        protected = protected.replace(abbr, abbr.replace(".", "\u2024"))
    protected = re.sub(r"(\d)\.(\d)", "\\1\u2024\\2", protected)
    parts = re.split(r"(?<=[.!?…])[\"“”»«’)]*\s+(?=[\"„“»«(]?[A-ZÄÖÜ0-9])", protected)
    return [p.replace("\u2024", ".").strip() for p in parts if p.strip()]


def words_of(s):
    return WORD.findall(s)


class Linter:
    def __init__(self, lang=None):
        self.lang_override = lang
        strong, soft, self.buzz_source = load_buzz()
        self.re_stock = compile_any(STOCK_PHRASES)
        self.re_chat = compile_any(CHAT_RESIDUE)
        self.re_reveal = compile_any(STAGED_REVEALS)
        self.re_contrast = compile_any(NOT_ONLY_BUT)
        self.re_super = re.compile(r"\b(?:" + "|".join(SUPERLATIVES) + r")\b", re.I)
        self.re_connector = re.compile(r"^(?:" + "|".join(CONNECTORS) + r")\b", re.I)
        self.re_generic = re.compile(r"^(?:\d+[.)]?\s*)?(?:" + "|".join(GENERIC_HEADINGS) + r")\s*[:!.]?\s*$", re.I)
        self.re_closer = re.compile(r"^(?:" + "|".join(SUMMARY_CLOSERS) + r")", re.I)
        self.re_placeholder = re.compile("|".join(PLACEHOLDERS), re.I)
        self.re_strong = re.compile(r"\b(?:" + "|".join(strong) + r")\b", re.I)
        self.re_soft = re.compile(r"\b(?:" + "|".join(soft + EXTRA_SOFT) + r")\b", re.I)

    def lint_text(self, raw, display="<stdin>"):
        lines = raw.split("\n")
        masked = mask(raw)
        prose = re.sub(r"\s+", " ", masked)
        lang = self.lang_override or detect_lang(prose)
        blocks = split_blocks(masked)
        findings = []

        def add(rule, line, detail):
            if self._ignored(lines, line, rule):
                return
            sev, msg = RULES[rule]
            findings.append({"rule": rule, "severity": sev, "file": display, "line": line,
                             "detail": detail[:160], "message": msg})

        def line_in_block(start, text, offset):
            return start + text[:offset].count("\n")

        # line-oriented phrase rules on the masked source keep exact line numbers
        for n, line in enumerate(masked.split("\n"), 1):
            if not line.strip():
                continue
            for regex, rule in ((self.re_stock, "stock-phrase"), (self.re_chat, "chat-residue"),
                                (self.re_strong, "marketing-buzzword")):
                m = regex.search(line.strip())
                if m:
                    add(rule, n, m.group(0))
            m = self.re_placeholder.search(line)
            if m:
                add("placeholder", n, m.group(0))

        total_words = len(words_of(prose))
        contrasts, reveals, triads, dashes, exclaims = [], [], [], 0, 0
        all_lengths, headings, bold_run, short_run = [], [], [], []
        paras = [b for b in blocks if b[0] == "para"]
        for kind, start, text in blocks:
            if kind == "heading":
                headings.append((start, text))
                if self.re_generic.match(text.strip()):
                    add("generic-heading", start, text)
                if EMOJI.search(text):
                    add("emoji-bullets", start, text)
                continue
            if kind == "item":
                if re.match(r"(?:[-*+]|\d+[.)])\s+\*\*[^*]+\*\*\s*[:–—-]", text):
                    bold_run.append(start)
                else:
                    if len(bold_run) >= 3:
                        add("bold-lead-bullets", bold_run[0], f"{len(bold_run)} bullets in a row")
                    bold_run = []
                if EMOJI.match(text) or re.match(r"(?:[-*+]|\d+[.)])\s+" + EMOJI.pattern, text):
                    add("emoji-bullets", start, text)
                continue
            if len(bold_run) >= 3:
                add("bold-lead-bullets", bold_run[0], f"{len(bold_run)} bullets in a row")
            bold_run = []
            sents = sentences(text)
            wc = len(words_of(text))
            if wc > 120:
                add("long-paragraph", start, f"{wc} words")
            soft = {m.group(0).lower() for m in self.re_soft.finditer(text)}
            if len(soft) >= 2:
                add("soft-buzzword", start, ", ".join(sorted(soft)))
            if text.count("?") >= 3:
                add("rhetorical-questions", start, f"{text.count('?')} questions")
            conn = [s for s in sents if self.re_connector.match(s)]
            if len(conn) >= 2:
                add("connector-stack", start, "; ".join(c.split()[0] for c in conn))
            for m in self.re_contrast.finditer(text):
                contrasts.append((start, m.group(0)))
            for m in self.re_reveal.finditer(text):
                reveals.append((start, m.group(0).strip(" .!?")))
            triads += [(start, m.group(0)) for m in re.finditer(
                r"\b[\wÄÖÜäöüß-]+(?: [\wÄÖÜäöüß-]+)?, [\wÄÖÜäöüß-]+(?: [\wÄÖÜäöüß-]+)? (?:und|oder|and|or) [\wÄÖÜäöüß-]+",
                text)]
            dashes += text.count("—") + (text.count(" – ") if lang == "en" else 0)
            exclaims += text.count("!")
            for s in sents:
                sw = len(words_of(s))
                all_lengths.append(sw)
                sup = [m.group(0) for m in self.re_super.finditer(s)]
                if len(sup) >= 2:
                    add("superlative-chain", start, ", ".join(sup))
                if sw > (45 if lang == "de" else 40):
                    add("long-sentence", start, f"{sw} words: {s[:60]}…")
                if lang == "de":
                    nouns = re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]+(?:ung|heit|keit|ion|ität)(?:en)?\b", s)
                    if len(nouns) >= 4 and len(nouns) / max(sw, 1) > 0.18:
                        add("nominal-style", start, ", ".join(nouns))
                short_run = short_run + [start] if 0 < sw <= 3 else []
                if len(short_run) == 3:
                    add("fragment-drama", short_run[0], "three very short sentences in a row")
            short_run = []
        if len(bold_run) >= 3:
            add("bold-lead-bullets", bold_run[0], f"{len(bold_run)} bullets in a row")

        if len(contrasts) >= 2:
            for start, detail in contrasts:
                add("not-only-but", start, detail)
        if len(reveals) >= 2 or any(re.search(r"here'?s the|spoiler|plot twist", d, re.I) for _, d in reveals):
            for start, detail in reveals:
                add("staged-reveal", start, detail)
        if len(triads) >= 4 and total_words and len(triads) / total_words > 1 / 120:
            add("triad-overuse", triads[0][0], f"{len(triads)} three-item lists in {total_words} words")
        if dashes >= 3 and total_words and dashes / total_words > 1 / 150:
            add("em-dash-overuse", paras[0][1] if paras else 1, f"{dashes} dashes in {total_words} words")
        if exclaims >= 3 and total_words and exclaims / total_words > 1 / 100:
            add("exclamation-overuse", paras[0][1] if paras else 1, f"{exclaims} in {total_words} words")
        if headings and total_words and len(headings) >= 4 and total_words / len(headings) < 90:
            add("heading-overload", headings[0][0], f"{len(headings)} headings for {total_words} words")
        if paras and self.re_closer.match(paras[-1][2]):
            add("summary-closer", paras[-1][1], paras[-1][2][:60])
        stats = self._stats(all_lengths, total_words, lang)
        if stats["sentences"] >= 8 and stats["cv"] < 0.35:
            add("uniform-rhythm", paras[0][1] if paras else 1,
                f"mean {stats['mean']} words, variation {stats['cv']} (human prose usually above 0.4)")
        return findings, stats

    def _stats(self, lengths, total_words, lang):
        mean = round(statistics.mean(lengths), 1) if lengths else 0
        cv = round(statistics.pstdev(lengths) / mean, 2) if len(lengths) > 1 and mean else 0
        return {"lang": lang, "words": total_words, "sentences": len(lengths), "mean": mean, "cv": cv,
                "buzzwords": self.buzz_source}

    @staticmethod
    def _ignored(lines, line, rule):
        for idx in (line - 1, line - 2):
            if 0 <= idx < len(lines):
                m = IGNORE.search(lines[idx])
                if m:
                    names = {r.strip(" -") for r in m.group(1).split(",")}
                    if rule in names or "all" in names:
                        return True
        return False


def lint(sources, lang=None):
    """sources: list of (display_name, text). Returns the report dict."""
    linter = Linter(lang)
    findings, stats = [], {}
    for display, text in sources:
        f, s = linter.lint_text(text, display)
        findings += f
        stats[display] = s
    seen, unique = set(), []
    for f in findings:
        key = (f["rule"], f["file"], f["line"], f["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: (f["severity"] != "error", f["file"], f["line"]))
    return {"tool": "redaktion-prose-lint", "findings": unique, "stats": stats,
            "summary": {"errors": sum(f["severity"] == "error" for f in unique),
                        "warnings": sum(f["severity"] == "warning" for f in unique)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", help="files to check, '-' for stdin")
    ap.add_argument("--lang", choices=["de", "en"], help="force language (default: detect per file)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stats", action="store_true", help="print words, sentence rhythm and buzzword source")
    ap.add_argument("--rules", action="store_true", help="list the rules and exit")
    args = ap.parse_args(argv)
    if args.rules:
        for name, (sev, msg) in RULES.items():
            print(f"{sev:7} {name:22} {msg}")
        return 0
    if not args.paths:
        ap.error("give at least one file or '-'")
    sources = []
    for p in args.paths:
        if p == "-":
            sources.append(("<stdin>", sys.stdin.read()))
        else:
            sources.append((p, Path(p).read_text(encoding="utf-8")))
    report = lint(sources, args.lang)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for f in report["findings"]:
            print(f"{f['file']}:{f['line']}: {f['severity']} {f['rule']}: {f['detail']}")
        if args.stats:
            for name, s in report["stats"].items():
                print(f"{name}: {s['lang']}, {s['words']} words, {s['sentences']} sentences, "
                      f"mean {s['mean']} words, variation {s['cv']}, buzzwords from {s['buzzwords']}")
        s = report["summary"]
        print(f"lint: {s['errors']} errors, {s['warnings']} warnings")
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
