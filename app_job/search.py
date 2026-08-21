"""Mini-modèle de recherche : mots-clés + synonymes FR/EN (sans API externe)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from django.db.models import Q

# Expansion bidirectionnelle : chaque terme pointe vers ses équivalents.
# Couvre les métiers seed Azotin (Bénin) + variantes courantes FR/EN.
_JOB_SYNONYMS = {
    # Plomberie
    "plombier": ["plumber", "plomberie", "fuite", "robinet", "sanitaire", "canalisation", "wc", "chauffe eau"],
    "plumber": ["plombier", "plomberie", "fuite", "pipe"],
    "plomberie": ["plombier", "plumber", "sanitaire", "fuite"],
    "fuite": ["plombier", "plomberie", "plumber"],
    # Ménage / nettoyage
    "menage": ["cleaning", "nettoyage", "femme de menage", "housework", "entretien", "repassage", "menager", "menagere"],
    "menager": ["menage", "menagere", "nettoyage", "cleaning", "entretien"],
    "menagere": ["menage", "menager", "nettoyage", "cleaning"],
    "cleaning": ["menage", "nettoyage", "housework", "cleaner"],
    "nettoyage": ["menage", "cleaning", "entretien", "menager"],
    "repassage": ["ironing", "menage", "linge"],
    "ironing": ["repassage", "linge"],
    # Électricité
    "electricien": ["electrician", "electricite", "electrique", "cable", "prise", "disjoncteur", "eclairage"],
    "electrician": ["electricien", "electricite", "wiring"],
    "electricite": ["electricien", "electrician", "electrique", "cable"],
    "electrique": ["electricien", "electricite", "electrician"],
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
    "demenageur": ["demenagement", "moving", "cartons"],
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
    "coiffure": ["coiffeur", "hairdresser", "barber", "tresses"],
    "hairdresser": ["coiffeur", "coiffure"],
    "couturier": ["tailor", "couture", "seamstress", "tailleur"],
    "couture": ["couturier", "tailor", "tailleur", "seamstress"],
    "tailor": ["couturier", "couture", "tailleur"],
    "tailleur": ["couturier", "tailor", "couture"],
    # Bois / métal
    "menuisier": ["carpenter", "menuiserie", "bois", "ebeniste"],
    "menuiserie": ["menuisier", "carpenter", "bois", "ebeniste"],
    "carpenter": ["menuisier", "menuiserie"],
    "soudeur": ["welder", "soudure"],
    "soudure": ["soudeur", "welder"],
    "welder": ["soudeur", "soudure"],
    # Mécanique / clim
    "mecanicien": ["mechanic", "mecanique", "garage", "auto"],
    "mecanique": ["mecanicien", "mechanic", "garage", "auto"],
    "mechanic": ["mecanicien", "mecanique"],
    "climatisation": ["clim", "hvac", "ac", "froid", "climaticien"],
    "climaticien": ["climatisation", "clim", "froid", "hvac"],
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
    "decorateur": ["decoration", "event", "evenement", "fete"],
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

# Plus longs d'abord : plomberie (erie) avant ier, peinture (ure) avant re.
_STEM_SUFFIXES = (
    "euses",
    "eries",
    "ieres",
    "iennes",
    "ments",
    "tions",
    "iques",
    "istes",
    "ateurs",
    "atrices",
    "ations",
    "euse",
    "erie",
    "iere",
    "iers",
    "iens",
    "ienne",
    "ique",
    "iste",
    "ateur",
    "atrice",
    "ation",
    "eurs",
    "eur",
    "ier",
    "ien",
    "ites",
    "ite",
    "ages",
    "age",
    "ures",
    "ure",
    "ants",
    "ant",
    "ings",
    "ing",
    "tion",
    "ment",
    "er",
    "re",
    "e",
)

# Métier ↔ activité : plombier↔plomberie, électricien↔électricité, etc.
_MORPH_MAP: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("iers", ("erie", "age")),
    ("ier", ("erie", "age", "iere")),
    ("erie", ("ier", "iers")),
    ("iens", ("ite", "ique")),
    ("ien", ("ite", "ique", "ienne")),
    ("ienne", ("ien", "ite")),
    ("ite", ("ien", "iens", "ique")),
    ("ique", ("ien", "ite")),
    ("eurs", ("ure", "age", "e")),
    ("eur", ("ure", "age", "euse", "e")),
    ("euse", ("eur", "ure")),
    ("ure", ("eur", "euse", "re")),
    ("ages", ("eur", "ier", "er")),
    ("age", ("eur", "ier", "er")),
    ("ateurs", ("ation",)),
    ("ateur", ("ation",)),
    ("atrice", ("ation",)),
    ("ation", ("ateur", "atrice")),
    ("er", ("age", "e")),
    ("re", ("ure",)),
    ("e", ("er",)),
)

_ACCENT_CLASS = {
    "a": "aàáâäãåAÀÁÂÄÃÅ",
    "e": "eéèêëEÉÈÊË",
    "i": "iîïìíIÎÏÌÍ",
    "o": "oôöòóõOÔÖÒÓÕ",
    "u": "uùûüúUÙÛÜÚ",
    "c": "cçCÇ",
    "y": "yÿýYŸÝ",
    "n": "nñNÑ",
}

JOB_OFFER_SEARCH_FIELDS = (
    "title",
    "description",
    "responsability",
    "location",
    "category__name",
    "sub_category__name",
)

WORKER_SEARCH_FIELDS = (
    "title__name",
    "job_types__name",
    "category__name",
    "skills",
    "certifications",
    "user__first_name",
    "user__last_name",
    "user__bio",
)

_MAX_KEYWORDS = 36
_MIN_STEM_LEN = 4
_SYNONYM_INDEX: Optional[Dict[str, List[str]]] = None


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _normalize_token(token: str) -> str:
    token = _strip_accents(token.lower().strip())
    token = re.sub(r"[^a-z0-9]+", "", token)
    return token


def _stem(token: str) -> str:
    """Racine FR partagée : plombier/plomberie → plomb, carreleur/carrelage → carrel."""
    if len(token) < 5:
        return token
    for suffix in _STEM_SUFFIXES:
        stem = token[: -len(suffix)] if token.endswith(suffix) else ""
        if stem and len(stem) >= _MIN_STEM_LEN:
            return stem
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _morph_variants(token: str) -> List[str]:
    """Variantes métier ↔ activité par substitution de suffixe (le plus long d'abord)."""
    if len(token) < 5:
        return []
    variants: List[str] = []
    seen = {token}
    for suffix, targets in _MORPH_MAP:
        if not token.endswith(suffix):
            continue
        stem = token[: -len(suffix)]
        min_stem = 4 if suffix in {"age", "ages", "e", "er", "re"} else 3
        if len(stem) < min_stem:
            continue
        for target in targets:
            candidate = stem + target
            if candidate not in seen and len(candidate) >= 4:
                seen.add(candidate)
                variants.append(candidate)
        break
    stemmed = _stem(token)
    if stemmed not in seen and len(stemmed) >= _MIN_STEM_LEN:
        variants.append(stemmed)
    return variants


def _accent_insensitive_regex(text: str) -> str:
    """Sous-chaîne regex insensible aux accents (Électricité ~ electricite)."""
    if not text:
        return ""
    parts: List[str] = []
    for ch in text:
        folded = _strip_accents(ch.lower())
        if folded in _ACCENT_CLASS:
            parts.append("[" + _ACCENT_CLASS[folded] + "]")
        elif ch.isalnum() or ch in " -'":
            parts.append(re.escape(ch) if ch in r".$^?*+{}[]\\|" else ch)
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def keywords_to_q(keywords: Sequence[str], fields: Sequence[str]) -> Q:
    """OR sur tous les champs × tous les mots-clés (accents ignorés)."""
    q_objects = Q()
    seen_patterns: Set[str] = set()
    for kw in keywords:
        cleaned = (kw or "").strip()
        if not cleaned:
            continue
        pattern = _accent_insensitive_regex(cleaned)
        if not pattern or pattern in seen_patterns:
            continue
        seen_patterns.add(pattern)
        for field in fields:
            q_objects |= Q(**{f"{field}__iregex": pattern})
            q_objects |= Q(**{f"{field}__icontains": cleaned})
    return q_objects


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
            folded = _normalize_token(term)
            aliases = {folded, _stem(folded), *_morph_variants(folded)}
            for alias in aliases:
                if not alias or alias == folded:
                    continue
                alias_bucket = _bucket_for(alias)
                for extra in group:
                    cleaned = (extra or "").strip()
                    if cleaned and cleaned not in alias_bucket:
                        alias_bucket.append(cleaned)

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
        morphs = _morph_variants(normalized)
        for variant in morphs:
            _add(variant)
        stemmed = _stem(normalized)
        _add(stemmed)

        lookup_keys = [normalized, stemmed, *morphs]
        seen_lookups: Set[str] = set()
        for lookup in lookup_keys:
            if not lookup or lookup in seen_lookups:
                continue
            seen_lookups.add(lookup)
            for extra in index.get(lookup, []):
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
