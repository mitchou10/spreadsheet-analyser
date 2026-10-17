"""A small lexical search engine (BM25 over weighted fields) tuned for spreadsheet vocabulary.

What makes it forgiving: accents/case/plurals are folded, snake_case and camelCase are split, FR/EN synonyms
are expanded, prefixes match ('vent' finds 'ventes'), typos are corrected against the index vocabulary, and a
document matching every query word outranks one matching a single word. It needs no model and no network."""

import difflib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.agent.text import SYNONYMS, tokenize

K1, B = 1.4, 0.6
SYNONYM_WEIGHT, PREFIX_WEIGHT, FUZZY_WEIGHT = 0.6, 0.75, 0.7


@dataclass
class Doc:
    """One searchable item. `fields` maps a field name to its tokens; `payload` is whatever the caller wants back."""

    payload: object
    fields: dict[str, list[str]]
    counts: dict[str, Counter] = field(init=False)

    def __post_init__(self) -> None:
        self.counts = {name: Counter(tokens) for name, tokens in self.fields.items()}


@dataclass
class Hit:
    doc: Doc
    score: float
    # For explanations: which index words matched which query word, per field.
    matches: dict[str, set[str]]


class Index:
    def __init__(self, docs: list[Doc], field_weights: dict[str, float]) -> None:
        self.docs = docs
        self.weights = field_weights
        self.postings: dict[str, set[int]] = defaultdict(set)
        document_frequency: Counter = Counter()
        field_lengths: dict[str, int] = defaultdict(int)
        for number, doc in enumerate(docs):
            seen = set()
            for name, counts in doc.counts.items():
                field_lengths[name] += sum(counts.values())
                seen.update(counts)
            for token in seen:
                self.postings[token].add(number)
                document_frequency[token] += 1
        count = max(len(docs), 1)
        self.average_length = {name: (field_lengths[name] / count) or 1.0 for name in field_weights}
        self.idf = {
            token: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }
        self.vocabulary = sorted(self.postings)

    def _variants(self, token: str) -> list[tuple[str, float]]:
        """The index words a query word can stand for, with a confidence weight."""
        variants: dict[str, float] = {}
        if token in self.postings:
            variants[token] = 1.0
        for synonym in SYNONYMS.get(token, ()):
            if synonym in self.postings:
                variants.setdefault(synonym, SYNONYM_WEIGHT)
        if token not in self.postings:
            if len(token) >= 3:
                for word in self.vocabulary:
                    if word.startswith(token) and len(word) - len(token) <= 4:
                        variants.setdefault(word, PREFIX_WEIGHT)
            if not variants and len(token) >= 4:
                for word in difflib.get_close_matches(token, self.vocabulary, n=2, cutoff=0.8):
                    variants.setdefault(word, FUZZY_WEIGHT)
        return list(variants.items())

    def _field_score(self, doc: Doc, word: str) -> tuple[float, list[str]]:
        total, fields = 0.0, []
        for name, weight in self.weights.items():
            frequency = doc.counts.get(name, {}).get(word, 0)
            if not frequency:
                continue
            length = sum(doc.counts[name].values())
            saturation = frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / self.average_length[name]))
            total += weight * saturation
            fields.append(name)
        return total, fields

    def search(self, query: str, limit: int = 8, accept=None) -> list[Hit]:
        query_tokens = list(dict.fromkeys(tokenize(query)))
        if not query_tokens:
            return []
        expanded = {token: self._variants(token) for token in query_tokens}
        candidates: set[int] = set()
        for variants in expanded.values():
            for word, _ in variants:
                candidates |= self.postings[word]
        hits = []
        for number in candidates:
            doc = self.docs[number]
            if accept is not None and not accept(doc):
                continue
            total, matched_tokens = 0.0, 0
            matches: dict[str, set[str]] = defaultdict(set)
            for variants in expanded.values():
                best, best_word, best_fields = 0.0, None, []
                for word, weight in variants:
                    score, fields = self._field_score(doc, word)
                    if score and weight * self.idf[word] * score > best:
                        best, best_word, best_fields = weight * self.idf[word] * score, word, fields
                if best_word is not None:
                    total += best
                    matched_tokens += 1
                    for name in best_fields:
                        matches[name].add(best_word)
            if total > 0:
                # Matching every word of the query beats matching only the rarest one.
                total *= 0.5 + 0.5 * matched_tokens / len(query_tokens)
                hits.append(Hit(doc, total, dict(matches)))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]
