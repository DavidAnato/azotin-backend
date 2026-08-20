"""Mini-modèle de recherche : mots-clés + synonymes FR/EN (sans API externe)."""

from __future__ import annotations

import re
import unicodedata
from typing import List

# Expansion bidirectionnelle : chaque terme pointe vers ses équivalents.
_JOB_SYNONYMS = {
    "plombier": ["plumber", "plomberie", "fuite", "robinet", "sanitaire"],
    "plumber": ["plombier", "plomberie", "fuite"],
    "plomberie": ["plombier", "plumber"],
    "menage": ["cleaning", "nettoyage", "femme de menage", "housework"],
    "cleaning": ["menage", "nettoyage", "housework"],
    "nettoyage": ["menage", "cleaning"],
    "electricien": ["electrician", "electricite", "cable", "prise"],
    "electrician": ["electricien", "electricite"],
    "electricite": ["electricien", "electrician"],
    "peintre": ["painter", "peinture"],
    "painter": ["peintre", "peinture"],
    "peinture": ["peintre", "painter"],
    "macon": ["mason", "maconnerie", "bricklayer"],
    "mason": ["macon", "maconnerie"],
    "jardinier": ["gardener", "jardinage", "paysagiste"],
    "gardener": ["jardinier", "jardinage"],
    "jardinage": ["jardinier", "gardener"],
    "chauffeur": ["driver", "conducteur", "taxi"],
    "driver": ["chauffeur", "conducteur"],
    "cuisinier": ["cook", "chef", "cuisine"],
    "cook": ["cuisinier", "chef", "cuisine"],
    "chef": ["cuisinier", "cook"],
    "nounou": ["nanny", "babysitter", "garde d enfants", "baby-sitter"],
    "nanny": ["nounou", "babysitter"],
    "coiffeur": ["hairdresser", "coiffure", "barber"],
    "hairdresser": ["coiffeur", "coiffure"],
    "couturier": ["tailor", "couture", "seamstress"],
    "tailor": ["couturier", "couture"],
    "menuisier": ["carpenter", "menuiserie", "bois"],
    "carpenter": ["menuisier", "menuiserie"],
    "soudeur": ["welder", "soudure"],
    "welder": ["soudeur", "soudure"],
    "mecanicien": ["mechanic", "mecanique", "garage"],
    "mechanic": ["mecanicien", "mecanique"],
    "climatisation": ["clim", "hvac", "ac", "froid"],
    "hvac": ["climatisation", "clim"],
    "gardien": ["security", "garde", "vigil"],
    "security": ["gardien", "garde", "vigil"],
    "livraison": ["delivery", "coursier", "livreur"],
    "delivery": ["livraison", "coursier", "livreur"],
    "informatique": ["it", "computer", "dev", "developpeur"],
    "developpeur": ["informatique", "it", "developer"],
    "developer": ["developpeur", "informatique", "it"],
}

_SUFFIXES = (
    "euse",
    "eurs",
    "euses",
    "eur",
    "ière",
    "ieres",
    "ier",
    "ing",
    "tion",
    "ments",
    "ment",
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _normalize_token(token: str) -> str:
    token = _strip_accents(token.lower().strip())
    token = re.sub(r"[^a-z0-9]+", "", token)
    return token


def _stem(token: str) -> str:
    if len(token) < 5:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def expand_search_query(query: str) -> List[str]:
    """Découpe la requête et ajoute synonymes / stems FR-EN. Ordre stable, sans doublons."""
    if not query or not str(query).strip():
        return []

    raw_tokens = re.split(r"[\s,;|/]+", str(query).strip())
    expanded: List[str] = []
    seen = set()

    def _add(term: str) -> None:
        cleaned = (term or "").strip()
        if not cleaned:
            return
        key = _normalize_token(cleaned)
        if not key or key in seen:
            return
        seen.add(key)
        expanded.append(cleaned)

    for raw in raw_tokens:
        if not raw:
            continue
        _add(raw)
        normalized = _normalize_token(raw)
        if not normalized:
            continue
        _add(normalized)
        stemmed = _stem(normalized)
        _add(stemmed)
        for extra in _JOB_SYNONYMS.get(normalized, []):
            _add(extra)
        for extra in _JOB_SYNONYMS.get(stemmed, []):
            _add(extra)
        # Si le token est une valeur de synonyme, remonter à la clé.
        for key, values in _JOB_SYNONYMS.items():
            if normalized in values or stemmed in values:
                _add(key)
                for extra in values:
                    _add(extra)

    return expanded


def compute_match_score(job_offer, keywords: List[str]) -> int:
    """Score simple : titre > catégorie > description > sous-catégorie."""
    if not keywords:
        return 0

    title = _normalize_token(getattr(job_offer, "title", None) or "")
    description = _normalize_token(getattr(job_offer, "description", None) or "")
    category = ""
    sub_category = ""
    cat = getattr(job_offer, "category", None)
    if cat is not None:
        category = _normalize_token(getattr(cat, "name", "") or "")
    sub = getattr(job_offer, "sub_category", None)
    if sub is not None:
        sub_category = _normalize_token(getattr(sub, "name", "") or "")

    score = 0
    matched = set()
    for kw in keywords:
        key = _normalize_token(kw)
        if not key or key in matched:
            continue
        hit = False
        if key in title:
            score += 4
            hit = True
        if key in category:
            score += 3
            hit = True
        if key in description:
            score += 2
            hit = True
        if key in sub_category:
            score += 1
            hit = True
        if hit:
            matched.add(key)
    return score
