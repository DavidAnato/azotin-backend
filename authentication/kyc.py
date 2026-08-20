"""Helpers KYC — statut effectif sans nouvelle app."""


def effective_kyc_status(user) -> str:
    if getattr(user, "is_certified", False):
        return "approved"
    return getattr(user, "kyc_status", None) or "none"


def user_kyc_is_approved(user) -> bool:
    return effective_kyc_status(user) == "approved"


def kyc_required_response():
    from rest_framework import status
    from rest_framework.response import Response

    return Response(
        {
            "detail": "La vérification d'identité (KYC) est requise avant cette action.",
            "code": "kyc_required",
        },
        status=status.HTTP_403_FORBIDDEN,
    )
