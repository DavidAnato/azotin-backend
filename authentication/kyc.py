"""Helpers KYC — statut effectif et gate postuler / créer une offre."""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.response import Response

_APPROVED_ALIASES = frozenset({"approved", "certified", "verified"})
_KNOWN = frozenset({"none", "pending", "approved", "rejected"})


def get_kyc_submission(user):
    try:
        return user.kyc_submission
    except ObjectDoesNotExist:
        return None


def effective_kyc_status(user) -> str:
    if getattr(user, "is_certified", False):
        return "approved"
    submission = get_kyc_submission(user)
    if submission is None:
        return "none"
    raw = getattr(submission, "status", None) or "none"
    status_value = str(raw).strip().lower() or "none"
    if status_value in _APPROVED_ALIASES:
        return "approved"
    if status_value in _KNOWN:
        return status_value
    return "none"


def user_kyc_is_approved(user) -> bool:
    return effective_kyc_status(user) == "approved"


def kyc_required_response():
    return Response(
        {
            "detail": "La vérification d'identité (KYC) est requise avant cette action.",
            "code": "kyc_required",
            "kyc_status": "none",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def kyc_pending_response():
    return Response(
        {
            "detail": (
                "Votre vérification d'identité est en cours d'examen. "
                "Vous pourrez postuler et publier dès l'approbation."
            ),
            "code": "kyc_pending",
            "kyc_status": "pending",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def kyc_block_if_needed(user):
    """403 tant que le KYC n'est pas approuvé. None si l'action peut continuer.

    - jamais soumis / rejeté → ``kyc_required``
    - en attente → ``kyc_pending`` (message explicatif, pas un nouveau dépôt)
    - approuvé / certifié → None
    """
    kyc = effective_kyc_status(user)
    if kyc == "approved":
        return None
    if kyc == "pending":
        return kyc_pending_response()
    return kyc_required_response()
