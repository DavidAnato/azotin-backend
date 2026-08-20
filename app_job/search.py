"""Mini-modèle de recherche : mots-clés + synonymes FR/EN (sans API externe)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Dict, Iterable, List, Optional, Set

# Expansion bidirectionnelle : chaque terme pointe vers ses équivalents.
# Couvre les métiers seed Azotin (Bénin) + variantes courantes FR/EN.
_JOB_SYNONYMS = {
    # Plomberie
    "plombier": ["plumber", "plomberie", "fuite", "robinet", "sanitaire", "canalisation", "wc", "chauffe eau"],
    "plumber": ["plombier", "plomberie", "fuite", "pipe"],
    "plomberie": ["plombier", "plumber", "sanitaire", "fuite"],
    "fuite": ["plombier", "plomberie", "plumber"],
    # Ménage / nettoyage
    "menage": ["cleaning", "nettoyage", "femme de menage", "housework", "entretien", "repassage"],
    "cleaning": ["menage", "nettoyage", "housework", "cleaner"],
    "nettoyage": ["menage", "cleaning", "entretien"],
    "repassage": ["ironing", "menage", "linge"],
    "ironing": ["repassage", "linge"],
    # Électricité
    "electricien": ["electrician", "electricite", "cable", "prise", "disjoncteur", "eclairage"],
    "electrician": ["electricien", "electricite", "wiring"],
    "electricite": ["electricien", "electrician", "cable"],
    # Peinture
    "peintre": ["painter", "peinture", "enduit", "badigeon"],
    "painter": ["peintre", "peinture"],
    "peinture": ["peintre", "painter", "enduit"],
    # Maçonnerie / carrelage
    "macon": ["mason", "maconnerie", "bricklayer", "parpaing", "beton", "manoeuvre"],
    "mason": ["macon", "maconnerie"],
    "maconnerie": ["macon", "mason", "beton"],
    "carrelage": ["carreleur", "tile", "tiler", "faience"],
    "carreleur": ["carrelage", "tile", "tiler"],
    "tile": ["carrelage", "carreleur", "tiler"],
    # Jardinage
    "jardinier": ["gardener", "jardinage", "paysagiste", "tonte", "pelouse"],
    "gardener": ["jardinier", "jardinage"],
    "jardinage": ["jardinier", "gardener", "paysagiste", "tonte"],
    # Transport / livraison
    "chauffeur": ["driver", "conducteur", "taxi", "zemidjan", "moto"],
    "driver": ["chauffeur", "conducteur"],
    "livraison": ["delivery", "coursier", "livreur", "courses"],
    "delivery": ["livraison", "coursier", "livreur"],
    "livreur": ["livraison", "delivery", "coursier"],
    "demenagement": ["moving", "demenageur", "cartons", "transport meubles"],
    "moving": ["demenagement", "demenageur"],
    "courses": ["livraison", "errands", "shopping"],
    # Cuisine
    "cuisinier": ["cook", "chef", "cuisine", "traiteur"],
    "cook": ["cuisinier", "chef", "cuisine"],
    "chef": ["cuisinier", "cook", "traiteur"],
    "cuisine": ["cuisinier", "cook", "traiteur", "repas"],
    "traiteur": ["catering", "cuisine", "cuisinier", "evenement"],
    "catering": ["traiteur", "cuisine"],
    # Garde d'enfants
    "nounou": ["nanny", "babysitter", "garde d enfants", "baby-sitter", "garde enfants"],
    "nanny": ["nounou", "babysitter", "garde d enfants"],
    "babysitter": ["nounou", "nanny", "garde d enfants"],
    "garde": ["nounou", "nanny", "babysitter", "enfants"],
    # Coiffure / couture
    "coiffeur": ["hairdresser", "coiffure", "barber", "tresses"],
    "hairdresser": ["coiffeur", "coiffure"],
    "couturier": ["tailor", "couture", "seamstress", "tailleur"],
    "tailor": ["couturier", "couture", "tailleur"],
    "tailleur": ["couturier", "tailor", "couture"],
    # Bois / métal
    "menuisier": ["carpenter", "menuiserie", "bois", "ebeniste"],
    "carpenter": ["menuisier", "menuiserie"],
    "soudeur": ["welder", "soudure"],
    "welder": ["soudeur", "soudure"],
    # Mécanique / clim
    "mecanicien": ["mechanic", "mecanique", "garage", "auto"],
    "mechanic": ["mecanicien", "mecanique"],
    "climatisation": ["clim", "hvac", "ac", "froid", "climaticien"],
    "hvac": ["climatisation", "clim"],
    "clim": ["climatisation", "hvac", "froid"],
    # Sécurité
    "gardien": ["security", "garde", "vigil", "agent de securite"],
    "security": ["gardien", "garde", "vigil"],
    # Informatique
    "informatique": ["it", "computer", "dev", "developpeur", "pc", "depannage"],
    "developpeur": ["informatique", "it", "developer", "site web"],
    "developer": ["developpeur", "informatique", "it"],
    "depannage": ["informatique", "pc", "ordinateur", "reparation"],
    "ordinateur": ["pc", "informatique", "computer", "depannage"],
    "reseau": ["wifi", "internet", "informatique", "installation"],
    "bureautique": ["word", "excel", "formation", "informatique"],
    # Événementiel
    "decoration": ["decorateur", "event", "evenement", "fete"],
    "photographie": ["photographe", "photo", "shooting"],
    "photographe": ["photographie", "photo", "photographer"],
    "sonorisation": ["sono", "dj", "son", "evenement"],
    "evenement": ["event", "fete", "decoration", "traiteur", "sonorisation"],
    # Urgence (aide le ranking / le filtre implicite)
    "urgent": ["urgence", "asap", "immediat", "tout de suite", "rapide"],
    "urgence": ["urgent", "asap", "immediat", "rapide"],
    "asap": ["urgent", "urgence", "immediat"],
}

_STOPWORDS = frozenset(
    {
        "a",
        "au",
        "aux",
        "avec",
        "chez",
        "d",
        "de",
        "des",
        "du",
        "en",
        "et",
        "l",
        "la",
        "le",
        "les",
        "ou",
        "pour",
        "un",
        "une",
        "the",
        "an",
        "and",
        "for",
        "of",
        "in",
        "on",
        "to",
        "at",
        "job",
        "jobs",
        "offre",
        "offres",
        "cherche",
        "recherche",
        "besoin",
    }
)

_URGENCY_TOKENS = frozenset(
    {
        "urgent",
        "urgence",
        "asap",
        "immediat",
        "immediate",
        "toutsuite",
        "toutdesuite",
        "rapide",
    }
)

_SUFFIXES = (
    "euse",
    "eurs",
    "euses",
    "eur",
    "iere",
    "ieres",
    "ier",
    "ing",
    "tion",
    "ments",
    "ment",
)

_MAX_KEYWORDS = 24
_SYNONYM_INDEX: Optional[Dict[str, List[str]]] = None


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
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _synonym_index() -> Dict[str, List[str]]:
    """Index normalisé clé + valeurs → tous les équivalents du groupe."""
    global _SYNONYM_INDEX
    if _SYNONYM_INDEX is not None:
        return _SYNONYM_INDEX

    index: Dict[str, List[str]] = {}

    def _bucket_for(term: str) -> List[str]:
        key = _normalize_token(term)
        if not key:
            return []
        if key not in index:
            index[key] = []
        return index[key]

    for key, values in _JOB_SYNONYMS.items():
        group = [key, *values]
        for term in group:
            bucket = _bucket_for(term)
            for extra in group:
                cleaned = (extra or "").strip()
                if cleaned and cleaned not in bucket:
                    bucket.append(cleaned)
            stemmed = _stem(_normalize_token(term))
            if stemmed and stemmed != _normalize_token(term):
                stem_bucket = _bucket_for(stemmed)
                for extra in group:
                    cleaned = (extra or "").strip()
                    if cleaned and cleaned not in stem_bucket:
                        stem_bucket.append(cleaned)

    _SYNONYM_INDEX = index
    return index


def is_urgency_token(token: str) -> bool:
    normalized = _normalize_token(token)
    return normalized in _URGENCY_TOKENS or _stem(normalized) in _URGENCY_TOKENS


def has_urgency_intent(tokens: Iterable[str]) -> bool:
    return any(is_urgency_token(token) for token in tokens)


def has_only_urgency_keywords(tokens: Iterable[str]) -> bool:
    material = [t for t in tokens if _normalize_token(t)]
    return bool(material) and all(is_urgency_token(t) for t in material)


def expand_search_query(query: str) -> List[str]:
    """Découpe la requête et ajoute synonymes / stems FR-EN. Ordre stable, sans doublons."""
    if not query or not str(query).strip():
        return []

    raw_query = str(query).strip()
    raw_tokens = re.split(r"[\s,;|/]+", raw_query)
    expanded: List[str] = []
    seen: Set[str] = set()
    index = _synonym_index()

    def _add(term: str) -> None:
        if len(expanded) >= _MAX_KEYWORDS:
            return
        cleaned = (term or "").strip()
        if not cleaned:
            return
        key = _normalize_token(cleaned)
        if not key or key in seen:
            return
        seen.add(key)
        expanded.append(cleaned)

    # Phrase complète (ex. "garde d'enfants", "site web").
    if " " in raw_query or "'" in raw_query:
        _add(raw_query)
        _add(_strip_accents(raw_query.lower()))

    for raw in raw_tokens:
        if not raw or len(expanded) >= _MAX_KEYWORDS:
            continue
        normalized = _normalize_token(raw)
        if not normalized:
            continue
        if normalized in _STOPWORDS and normalized not in index:
            continue
        if len(normalized) < 2 and normalized not in index:
            continue

        _add(raw)
        _add(normalized)
        stemmed = _stem(normalized)
        _add(stemmed)

        for extra in index.get(normalized, []):
            _add(extra)
        if stemmed != normalized:
            for extra in index.get(stemmed, []):
                _add(extra)

    return expanded


def compute_match_score(
    job_offer,
    keywords: List[str],
    *,
    urgency_intent: bool = False,
) -> int:
    """Score : titre > catégorie > sous-catégorie > description > lieu, + urgence/échéance."""
    if not keywords:
        return 0

    title = _normalize_token(getattr(job_offer, "title", None) or "")
    description = _normalize_token(getattr(job_offer, "description", None) or "")
    responsibility = _normalize_token(getattr(job_offer, "responsability", None) or "")
    location = _normalize_token(getattr(job_offer, "location", None) or "")
    category = ""
    sub_category = ""
    cat = getattr(job_offer, "category", None)
    if cat is not None:
        category = _normalize_token(getattr(cat, "name", "") or "")
    sub = getattr(job_offer, "sub_category", None)
    if sub is not None:
        sub_category = _normalize_token(getattr(sub, "name", "") or "")

    score = 0
    matched: Set[str] = set()
    for kw in keywords:
        key = _normalize_token(kw)
        if not key or key in matched:
            continue
        hit = False
        if key in title:
            score += 5
            hit = True
        if key in category:
            score += 4
            hit = True
        if key in sub_category:
            score += 3
            hit = True
        if key in description or key in responsibility:
            score += 2
            hit = True
        if key in location:
            score += 1
            hit = True
        if hit:
            matched.add(key)

    if getattr(job_offer, "is_urgent", False):
        score += 3 if urgency_intent else 1

    deadline = getattr(job_offer, "deadline", None)
    if deadline:
        try:
            days_left = (deadline - date.today()).days
        except TypeError:
            days_left = None
        if days_left is not None and 0 <= days_left <= 7:
            score += 1

    return score
