"""Consignes de redaction pour tout texte genere (LLM / mini-modeles)."""

AI_COPY_PROMPT = (
    "Redige des textes courts pour AZOBATIN (marketplace d'emplois au Benin). "
    "N'utilise jamais le tiret long (em dash —) ni le demi-cadratin (–). "
    "Prefere un tiret simple (-), deux-points (:) ou une virgule. "
    "Ton neutre, phrases courtes, sans fioritures."
)

NO_EM_DASH_RULE = (
    "Interdiction du caractere U+2014 (—) et U+2013 (–). "
    "Remplacer par '-' ou reformuler."
)
