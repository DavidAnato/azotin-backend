"""
Seed de développement — AZOTIN (branche dev).

Usage (depuis jobhub_api) :
  .\\venv\\Scripts\\python.exe seed_data.py
  .\\venv\\Scripts\\python.exe manage.py seed_data --reset

Variables d'environnement :
  SEED_RESET=1           — supprime les données métier avant regénérer
  SEED_SKIP_NETWORK=1    — pas de téléchargement ; placeholders PNG locaux
  SEED_SUPERUSER_PHONE   — défaut +22990000000
  SEED_SUPERUSER_PASSWORD — défaut admin1234

Images (si réseau) : photos de travail/chantier pour les offres, portraits pour les profils.

Comptes (mot de passe password123) :
  22997000000   — démo mobile, travailleur (PIN 1234)
  22997000001   — Amina Koffi, cliente (PIN 1234)
"""
from __future__ import annotations

import logging
import os
import random
import re
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobhub_api.settings.development")
django.setup()

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import signals as model_signals
from django.utils import timezone

try:
    import requests
except ImportError:
    requests = None


@contextmanager
def mute_all_signals():
    saved_post_save = model_signals.post_save.receivers[:]
    saved_post_delete = model_signals.post_delete.receivers[:]
    model_signals.post_save.receivers = []
    model_signals.post_delete.receivers = []
    try:
        yield
    finally:
        model_signals.post_save.receivers = saved_post_save
        model_signals.post_delete.receivers = saved_post_delete


from app_job.models import (  # noqa: E402
    Category,
    Job,
    JobApplication,
    JobFavorite,
    JobOffer,
    PaidService,
    SubCategory,
)
from app_messaging.models import Conversation, Message  # noqa: E402
from app_notification.models import NotificationToken, UserNotification  # noqa: E402
from app_profile.models import ClientProfile, PreviousWorkPhoto, WorkerProfile  # noqa: E402
from authentication.models import UserSettings  # noqa: E402
from app_escrow.models import (  # noqa: E402
    Contract,
    ContractStatus,
    Payment,
    PaymentStatus,
    Wallet,
    WalletTransaction,
    WalletTransactionType,
    Withdrawal,
    WithdrawalStatus,
)
User = get_user_model()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

DEFAULT_PASSWORD = "password123"

# --- Images : travail (offres / portfolio) vs personnes (profils) ------------

def _safe_seed_slug(key: str, max_len: int = 56) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "_", str(key)).strip("_")
    return (s or "azotin")[:max_len]


# Unsplash — scènes de travail par métier (pas de portraits)
SUBCATEGORY_WORK_IMAGES: dict[str, list[str]] = {
    "Plomberie": [
        "https://images.unsplash.com/photo-1607472586893-edb54cfbeb0d?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1585705273526-043b54702082?auto=format&w=900&q=80",
    ],
    "Électricité": [
        "https://images.unsplash.com/photo-1621905251918-48416bd8575a?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1473341304740-15ad4ffbd913?auto=format&w=900&q=80",
    ],
    "Peinture": [
        "https://images.unsplash.com/photo-1562259947-e79e243c8d75?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1589939705382-9584a9a1c6a5?auto=format&w=900&q=80",
    ],
    "Maçonnerie": [
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?auto=format&w=900&q=80",
    ],
    "Carrelage": [
        "https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?auto=format&w=900&q=80",
    ],
    "Ménage": [
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?auto=format&w=900&q=80",
    ],
    "Garde d'enfants": [
        "https://images.unsplash.com/photo-1503454537845-d7319b0baa0a?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1516627145497-ae6968895b74?auto=format&w=900&q=80",
    ],
    "Jardinage": [
        "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1592419044706-3972727a2879?auto=format&w=900&q=80",
    ],
    "Repassage": [
        "https://images.unsplash.com/photo-1582735682939-781b6c0f269e?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?auto=format&w=900&q=80",
    ],
    "Cuisine à domicile": [
        "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&w=900&q=80",
    ],
    "Livraison": [
        "https://images.unsplash.com/photo-1526367065039-aabd6fdf3be7?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088?auto=format&w=900&q=80",
    ],
    "Déménagement": [
        "https://images.unsplash.com/photo-1600880292089-90a7e086ee0c?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1600518464441-9154a4dea21b?auto=format&w=900&q=80",
    ],
    "Courses": [
        "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?auto=format&w=900&q=80",
    ],
    "Transport meubles": [
        "https://images.unsplash.com/photo-1600880292089-90a7e086ee0c?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&w=900&q=80",
    ],
    "Dépannage PC": [
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1593640408182-31c70c8268f5?auto=format&w=900&q=80",
    ],
    "Installation réseau": [
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1544197150-99ba26323f0e?auto=format&w=900&q=80",
    ],
    "Site web": [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&w=900&q=80",
    ],
    "Formation bureautique": [
        "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&w=900&q=80",
    ],
    "Décoration": [
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1513519245088-0e12902e35ca?auto=format&w=900&q=80",
    ],
    "Traiteur": [
        "https://images.unsplash.com/photo-1555244162-803834f70033?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&w=900&q=80",
    ],
    "Photographie": [
        "https://images.unsplash.com/photo-1492691527719-9d1e407e6968?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1452587925148-ce544e77e70d?auto=format&w=900&q=80",
    ],
    "Sonorisation": [
        "https://images.unsplash.com/photo-1511379938547-c1f69419868d?auto=format&w=900&q=80",
        "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&w=900&q=80",
    ],
}

DEFAULT_WORK_IMAGES = [
    "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&w=900&q=80",
    "https://images.unsplash.com/photo-1581094794329-c8112a89c8c8?auto=format&w=900&q=80",
]


def download_image_to_temp(url: str):
    if requests is None:
        return None, None
    try:
        response = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": "AzotinSeed/1.0", "Accept": "image/*"},
        )
        if response.status_code != 200:
            return None, None
        ctype = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }.get(ctype, "jpg")
        img_temp = NamedTemporaryFile(suffix="." + ext)
        img_temp.write(response.content)
        img_temp.flush()
        return img_temp, ext
    except Exception:
        return None, None


def job_image_urls(sub_category: str, seed_key: str) -> list[str]:
    pool = SUBCATEGORY_WORK_IMAGES.get(sub_category, DEFAULT_WORK_IMAGES)
    start = abs(hash(seed_key)) % len(pool)
    ordered = pool[start:] + pool[:start]
    safe = _safe_seed_slug(seed_key)
    # Secours thématique (tags métier, pas de visages)
    w, h = random.choice([(900, 600), (800, 600), (720, 480)])
    tag = quote(sub_category.lower().replace(" ", ",") or "construction,tools")
    ordered.append(f"https://loremflickr.com/{w}/{h}/{tag},work/all?lock={safe}")
    return ordered


def person_image_urls(seed_key: str, gender: str) -> list[str]:
    idx = abs(hash(seed_key)) % 99
    folder = "women" if gender == "female" else "men"
    safe = quote(seed_key)
    return [
        f"https://randomuser.me/api/portraits/{folder}/{idx}.jpg",
        f"https://randomuser.me/api/portraits/{folder}/{(idx + 17) % 99}.jpg",
        f"https://randomuser.me/api/portraits/{folder}/{(idx + 42) % 99}.jpg",
        f"https://i.pravatar.cc/400?u={safe}",
    ]


def fetch_job_image_file(seed_key: str, sub_category: str, skip_network: bool, tries: int = 5):
    if skip_network:
        return None, "job_offline.png"
    for url in job_image_urls(sub_category, seed_key)[:tries]:
        tmp, ext = download_image_to_temp(url)
        if tmp:
            return tmp, f"job_{_safe_seed_slug(seed_key, 40)}.{ext}"
    return None, "job_failed.jpg"


def fetch_person_image_file(seed_key: str, gender: str, skip_network: bool, tries: int = 4):
    if skip_network:
        return None, "person_offline.png"
    for url in person_image_urls(seed_key, gender)[:tries]:
        tmp, ext = download_image_to_temp(url)
        if tmp:
            return tmp, f"user_{_safe_seed_slug(seed_key, 40)}.{ext}"
    return None, "person_failed.jpg"


def placeholder_png_bytes(width: int = 320, height: int = 320) -> bytes:
    """PNG opaque navy (évite le 1×1 transparent invisible du seed offline)."""
    import struct
    import zlib

    # #1C2541
    r, g, b = 28, 37, 65
    accent = (91, 192, 190)  # teal coin
    rows = []
    for y in range(height):
        row = bytearray()
        row.append(0)  # filter none
        for x in range(width):
            if x > width * 0.72 and y < height * 0.28:
                row.extend(accent)
            else:
                row.extend((r, g, b))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def save_image_to_field(
    instance,
    field_name: str,
    seed_key: str,
    skip_network: bool,
    *,
    image_kind: str = "job",
    sub_category: str = "",
    gender: str = "",
) -> bool:
    if image_kind == "person":
        temp_img, fname = fetch_person_image_file(seed_key, gender, skip_network)
    else:
        temp_img, fname = fetch_job_image_file(seed_key, sub_category, skip_network)
    field = getattr(instance, field_name)
    stem = Path(fname).stem if fname else seed_key
    try:
        if temp_img:
            field.save(fname, File(temp_img), save=True)
            return True
        if skip_network:
            field.save(f"{stem}.png", ContentFile(placeholder_png_bytes()), save=True)
            return True
    finally:
        if temp_img:
            temp_img.close()
    return False


# --- Données métier -----------------------------------------------------------

LOCATIONS = {
    "Cotonou": (Decimal("6.3703"), Decimal("2.3912")),
    "Porto-Novo": (Decimal("6.4969"), Decimal("2.6289")),
    "Parakou": (Decimal("9.3372"), Decimal("2.6303")),
    "Abomey-Calavi": (Decimal("6.4485"), Decimal("2.3558")),
    "Godomey": (Decimal("6.4214"), Decimal("2.3483")),
    "Akpakpa": (Decimal("6.3558"), Decimal("2.4356")),
    "Fidjrossè": (Decimal("6.3589"), Decimal("2.4021")),
}

CATEGORIES = [
    (
        "Bâtiment & travaux",
        "Travaux de construction, rénovation et maintenance du bâti.",
        ["Plomberie", "Électricité", "Peinture", "Maçonnerie", "Carrelage"],
    ),
    (
        "Services à domicile",
        "Aide à la personne et entretien de l'habitat.",
        ["Ménage", "Garde d'enfants", "Jardinage", "Repassage", "Cuisine à domicile"],
    ),
    (
        "Transport & livraison",
        "Déplacements, courses et logistique urbaine.",
        ["Livraison", "Déménagement", "Courses", "Transport meubles"],
    ),
    (
        "Informatique & tech",
        "Support numérique pour particuliers et PME.",
        ["Dépannage PC", "Installation réseau", "Site web", "Formation bureautique"],
    ),
    (
        "Événementiel",
        "Organisation et prestations pour vos événements.",
        ["Décoration", "Traiteur", "Photographie", "Sonorisation"],
    ),
]

DEMO_USERS = [
    {
        "phone": "22997000000",
        "email": "demo.mobile@azotin.local",
        "first_name": "Demo",
        "last_name": "Mobile",
        "code_pin": "1234",
        "role": "worker",
        "city": "Cotonou",
        "gender": "male",
        "bio": "Compte de démonstration mobile — plombier & bricolage général.",
        "sub_idx": 0,
        "skills": "Plomberie sanitaire, détection de fuites, installation robinetterie, entretien chauffe-eau.",
        "certifications": "CAP Plomberie · Attestation sécurité chantier 2024",
        "experience": 8,
        "price": Decimal("3500"),
        "frequency": "hour",
        "avatar_seed": "demo_mobile",
    },
    {
        "phone": "22997000001",
        "email": "amina.client@azotin.local",
        "first_name": "Amina",
        "last_name": "Koffi",
        "code_pin": "1234",
        "role": "client",
        "city": "Cotonou",
        "gender": "female",
        "bio": "Cliente régulière — recherche des profils fiables pour la maison.",
        "service_name": "Résidence Koffi",
        "service_type": "home",
        "service_description": "Villa familiale, besoins ménage et jardinage.",
        "location_description": "Quartier Cadjehoun.",
        "avatar_seed": "amina_koffi",
    },
    {
        "phone": "22997000002",
        "email": "kofi.worker@azotin.local",
        "first_name": "Kofi",
        "last_name": "Mensah",
        "code_pin": "5678",
        "role": "worker",
        "city": "Porto-Novo",
        "gender": "male",
        "bio": "Électricien certifié — installations résidentielles et tableaux divisionnaires.",
        "sub_idx": 1,
        "skills": "Câblage, tableaux électriques, domotique basique, dépannage urgent.",
        "certifications": "BTS Électrotechnique · Habilitation BR",
        "experience": 11,
        "price": Decimal("4000"),
        "frequency": "hour",
        "avatar_seed": "kofi_mensah",
    },
    {
        "phone": "22997000003",
        "email": "aicha.worker@azotin.local",
        "first_name": "Aïcha",
        "last_name": "Diallo",
        "code_pin": "9012",
        "role": "worker",
        "city": "Parakou",
        "gender": "female",
        "bio": "Spécialiste ménage profond & repassage — références disponibles.",
        "sub_idx": 4,
        "skills": "Ménage, désinfection, repassage, organisation intérieure.",
        "certifications": "Formation hygiène HORECA",
        "experience": 6,
        "price": Decimal("2500"),
        "frequency": "hour",
        "avatar_seed": "aicha_diallo",
    },
    {
        "phone": "22997000004",
        "email": "jean.client@azotin.local",
        "first_name": "Jean",
        "last_name": "Agbessi",
        "code_pin": "1234",
        "role": "client",
        "city": "Abomey-Calavi",
        "gender": "male",
        "bio": "Propriétaire de plusieurs locations meublées.",
        "service_name": "Locations Agbessi",
        "service_type": "business",
        "service_description": "Gestion de 6 studios étudiants — maintenance rapide exigée.",
        "location_description": "Campus Abomey-Calavi.",
        "avatar_seed": "jean_agbessi",
    },
    {
        "phone": "22997000005",
        "email": "marc.worker@azotin.local",
        "first_name": "Marc",
        "last_name": "Zinsou",
        "code_pin": "1234",
        "role": "worker",
        "city": "Cotonou",
        "gender": "male",
        "bio": "Peintre décorateur — intérieur / extérieur, conseils couleurs.",
        "sub_idx": 2,
        "skills": "Peinture acrylique, enduits, papier peint, préparation supports.",
        "certifications": "10 ans d'expérience chantier",
        "experience": 10,
        "price": Decimal("3000"),
        "frequency": "hour",
        "avatar_seed": "marc_zinsou",
    },
    {
        "phone": "22997000006",
        "email": "fatou.worker@azotin.local",
        "first_name": "Fatou",
        "last_name": "Soglo",
        "code_pin": "1234",
        "role": "worker",
        "city": "Cotonou",
        "gender": "female",
        "bio": "Livreuse & courses — véhicule utilitaire, zone Cotonou–Calavi.",
        "sub_idx": 6,
        "skills": "Livraison express, manutention, emballage fragile.",
        "certifications": "Permis B · Assurance transport",
        "experience": 4,
        "price": Decimal("2000"),
        "frequency": "hour",
        "avatar_seed": "fatou_soglo",
    },
]

# Offres détaillées : clés utilisées par seed_job_offers
JOB_OFFERS_DATA = [
    {
        "title": "Réparation fuite cuisine — urgence",
        "description": (
            "Fuite persistante sous l'évier depuis 48 h. Accès facile, "
            "matériaux de base fournis. Intervention souhaitée avant vendredi."
        ),
        "responsability": (
            "Diagnostic, remplacement joints et siphon si nécessaire, "
            "test d'étanchéité 30 min, conseils entretien."
        ),
        "location": "Akpakpa, Cotonou",
        "city": "Cotonou",
        "sub": "Plomberie",
        "price": 15000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_plomberie_fuite",
        "days_offset": 2,
    },
    {
        "title": "Installation 8 prises salon + TV",
        "description": (
            "Appartement T3 rénové. Tracé déjà défini, gouaches à poser. "
            "Tableau divisionnaire récent (< 2 ans)."
        ),
        "responsability": (
            "Pose prises NF, mise à la terre, étiquetage, remise schéma simple."
        ),
        "location": "Fidjrossè, Cotonou",
        "city": "Cotonou",
        "sub": "Électricité",
        "price": 45000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_electricite_prises",
        "days_offset": 5,
    },
    {
        "title": "Peinture chambre parentale 14 m²",
        "description": (
            "Murs en bon état, plafond à refaire en blanc mat. "
            "Couleur murs : beige chaud RAL 1015."
        ),
        "responsability": (
            "Protection sols, 2 couches acrylique, finitions angles, "
            "nettoyage fin de chantier."
        ),
        "location": "Cadjehoun, Cotonou",
        "city": "Cotonou",
        "sub": "Peinture",
        "price": 35000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_peinture_chambre",
        "days_offset": 7,
        "is_recurring": False,
    },
    {
        "title": "Grand ménage villa avant réception",
        "description": (
            "Villa 5 pièces + terrasse. Dernier ménage il y a 3 mois. "
            "Produits écologiques appréciés."
        ),
        "responsability": (
            "Dépoussiérage complet, sols, sanitaires, vitres accessibles, "
            "cuisine et réfrigérateur intérieur."
        ),
        "location": "Godomey, Abomey-Calavi",
        "city": "Abomey-Calavi",
        "sub": "Ménage",
        "price": 28000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_menage_villa",
        "days_offset": 3,
    },
    {
        "title": "Livraison colis fragile Akpakpa → centre",
        "description": "3 cartons (vaisselle), manipulation délicate. Poids total ~25 kg.",
        "responsability": "Collecte 9h, livraison avant 14h, signature destinataire, photo preuve.",
        "location": "Akpakpa → Ganhi",
        "city": "Cotonou",
        "sub": "Livraison",
        "price": 8000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_livraison_colis",
        "days_offset": 1,
    },
    {
        "title": "Déménagement studio T1 Godomey",
        "description": "Studio meublé, 3e étage sans ascenseur. Destination 2 km.",
        "responsability": "Emballage fragiles, monte-meubles si besoin, démontage lit.",
        "location": "Godomey",
        "city": "Godomey",
        "sub": "Déménagement",
        "price": 55000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_demengement_studio",
        "days_offset": 10,
    },
    {
        "title": "Jardinage villa — tonte & haies",
        "description": "Terrain 400 m², haies 25 m linéaires, évacuation déchets verts.",
        "responsability": "Tonte, taille, nettoyage allées, conseils arrosage.",
        "location": "Calavi centre",
        "city": "Abomey-Calavi",
        "sub": "Jardinage",
        "price": 22000,
        "frequency": "week",
        "type": "part_time",
        "image_seed": "job_jardinage_villa",
        "days_offset": 4,
        "is_recurring": True,
        "recurrence_frequency": "weekly",
    },
    {
        "title": "Garde enfants samedi soir",
        "description": "2 enfants (6 et 9 ans), parents en sortie 18h–23h.",
        "responsability": "Surveillance, repas léger fourni, coucher 21h30.",
        "location": "Les Cocotiers, Cotonou",
        "city": "Cotonou",
        "sub": "Garde d'enfants",
        "price": 12000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_garde_enfants",
        "days_offset": 6,
    },
    {
        "title": "Rénovation salle de bain complète",
        "description": (
            "Dépose ancien carrelage, nouvelle faïence, douche italienne, "
            "robinetterie chromée fournie par client."
        ),
        "responsability": "Coordination plomberie + carrelage, étanchéité, finitions.",
        "location": "Porto-Novo centre",
        "city": "Porto-Novo",
        "sub": "Carrelage",
        "price": 180000,
        "frequency": "week",
        "type": "contract",
        "image_seed": "job_sdb_renovation",
        "days_offset": 14,
    },
    {
        "title": "Entretien climatiseurs bureau (×3)",
        "description": "Bureaux open space, split 24000 BTU ×3, dernière maintenance > 1 an.",
        "responsability": "Nettoyage filtres, recharge gaz si besoin, rapport par unité.",
        "location": "Zone industrielle, Cotonou",
        "city": "Cotonou",
        "sub": "Électricité",
        "price": 42000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_clim_bureau",
        "days_offset": 8,
    },
    {
        "title": "Montage meubles IKEA chambre & salon",
        "description": "Lit, armoire PAX, table basse, étagère KALLAX — notice fournie.",
        "responsability": "Montage, fixation murale étagère, évacuation cartons.",
        "location": "Cotonou 10e arrondissement",
        "city": "Cotonou",
        "sub": "Maçonnerie",
        "price": 32000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_montage_meubles",
        "days_offset": 5,
    },
    {
        "title": "Nettoyage bureaux PME (hebdo)",
        "description": "Open space 120 m² + 2 salles réunion, chaque vendredi 18h.",
        "responsability": "Aspiration, sanitaires, cuisineette, poubelles.",
        "location": "Boulevard St Michel",
        "city": "Cotonou",
        "sub": "Ménage",
        "price": 18000,
        "frequency": "week",
        "type": "part_time",
        "image_seed": "job_menage_bureau",
        "days_offset": 2,
        "is_recurring": True,
        "recurrence_frequency": "weekly",
    },
    {
        "title": "Baie réseau 24 ports + brassage",
        "description": "PME 15 postes, câbles CAT6 existants non étiquetés.",
        "responsability": "Brassage baie, tests fluke, documentation ports.",
        "location": "Haie Vive, Cotonou",
        "city": "Cotonou",
        "sub": "Installation réseau",
        "price": 95000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_reseau_pme",
        "days_offset": 12,
    },
    {
        "title": "Peinture façade immeuble R+2",
        "description": "Façade ~180 m², échafaudage loué par client, traitement fissures inclus.",
        "responsability": "Préparation, primaire, 2 couches façade, sécurité chantier.",
        "location": "Parakou centre-ville",
        "city": "Parakou",
        "sub": "Peinture",
        "price": 220000,
        "frequency": "week",
        "type": "contract",
        "image_seed": "job_peinture_facade",
        "days_offset": 21,
    },
    {
        "title": "Courses supermarché — personne âgée",
        "description": "Liste fournie la veille, budget max 45000 FCFA, ticket à remettre.",
        "responsability": "Achats, livraison même jour, aide rangement placards.",
        "location": "Aïbatin, Cotonou",
        "city": "Cotonou",
        "sub": "Courses",
        "price": 6000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_courses_aide",
        "days_offset": 1,
        "is_recurring": True,
        "recurrence_frequency": "weekly",
    },
    {
        "title": "Réparation portail coulissant motorisé",
        "description": "Portail bloqué mi-course, moteur Bubendorff, télécommande OK.",
        "responsability": "Diagnostic, réglage fins de course, graissage, test 10 cycles.",
        "location": "Tankpè, Porto-Novo",
        "city": "Porto-Novo",
        "sub": "Électricité",
        "price": 38000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_portail_motorise",
        "days_offset": 4,
    },
    {
        "title": "Remplacement chauffe-eau 150 L",
        "description": "Ancien cumulus percé, nouveau appareil déjà acheté (Atlantic).",
        "responsability": "Dépose, pose, raccordements eau/élec, mise en service.",
        "location": "Vedoko, Cotonou",
        "city": "Cotonou",
        "sub": "Plomberie",
        "price": 48000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_chauffe_eau",
        "days_offset": 6,
    },
    {
        "title": "Ménage fin de chantier appartement neuf",
        "description": "Après travaux peinture & carrelage, poussières fines partout.",
        "responsability": "Aspiration industrielle, vitres, sanitaires, cuisine.",
        "location": "Cocotomey, Calavi",
        "city": "Abomey-Calavi",
        "sub": "Ménage",
        "price": 24000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_menage_chantier",
        "days_offset": 3,
    },
    {
        "title": "Transport frigo américain Cotonou → Parakou",
        "description": "Appareil 140 kg, 2 personnes minimum, hayon souhaité.",
        "responsability": "Emballage angles, transport vertical sécurisé, installation destination.",
        "location": "Cotonou → Parakou",
        "city": "Cotonou",
        "sub": "Transport meubles",
        "price": 75000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_transport_frigo",
        "days_offset": 9,
    },
    {
        "title": "Repassage linge — 60 pièces / semaine",
        "description": "Chemises, draps, nappes — récupération lundi, retour mercredi.",
        "responsability": "Repassage vapeur, pliage, livraison sac propre.",
        "location": "Gbegamey, Cotonou",
        "city": "Cotonou",
        "sub": "Repassage",
        "price": 14000,
        "frequency": "week",
        "type": "part_time",
        "image_seed": "job_repassage",
        "days_offset": 2,
        "is_recurring": True,
        "recurrence_frequency": "weekly",
    },
    {
        "title": "Mise aux normes tableau électrique",
        "description": "Maison années 90, disjoncteurs vétustes, pas de différentiel 30 mA.",
        "responsability": "Devis matériel, pose différentiel, étiquetage, PV conformité simplifié.",
        "location": "Agla, Cotonou",
        "city": "Cotonou",
        "sub": "Électricité",
        "price": 85000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_tableau_elec",
        "days_offset": 11,
    },
    {
        "title": "Douche italienne & étanchéité",
        "description": "Receveur extra-plat 120×90, paroi verre, bonde linéaire.",
        "responsability": "Étanchéité SPEC, pose receveur, raccordements, silicone sanitaire.",
        "location": "Fidjrossè plage",
        "city": "Cotonou",
        "sub": "Plomberie",
        "price": 125000,
        "frequency": "week",
        "type": "contract",
        "image_seed": "job_douche_italienne",
        "days_offset": 15,
    },
    {
        "title": "Traiteur cocktail — 40 personnes",
        "description": "Anniversaire entreprise, buffet froid + 2 pièces chaudes, service 19h–23h.",
        "responsability": "Menu validé J-3, préparation sur site, vaisselle incluse.",
        "location": "Résidence Hôtelière, Cotonou",
        "city": "Cotonou",
        "sub": "Traiteur",
        "price": 195000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_traiteur_cocktail",
        "days_offset": 20,
    },
    {
        "title": "Photographie événement lancement produit",
        "description": "Soirée presse 2 h, livrables : 80 photos retouchées sous 72 h.",
        "responsability": "Reportage, portraits VIP, fichier WeTransfer HD.",
        "location": "Palais des Congrès",
        "city": "Cotonou",
        "sub": "Photographie",
        "price": 120000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_photo_event",
        "days_offset": 18,
    },
    {
        "title": "Dépannage PC portable + sauvegarde",
        "description": "Ne démarre plus après mise à jour Windows, données importantes.",
        "responsability": "Diagnostic, sauvegarde disque externe, réinstallation ou réparation.",
        "location": "Zongo, Parakou",
        "city": "Parakou",
        "sub": "Dépannage PC",
        "price": 25000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_depannage_pc",
        "days_offset": 2,
    },
    {
        "title": "Décoration anniversaire enfant (thème espace)",
        "description": "Salon 40 m², 15 enfants, ballons, cake table, photobooth simple.",
        "responsability": "Installation déco, démontage lendemain matin.",
        "location": "Menontin, Cotonou",
        "city": "Cotonou",
        "sub": "Décoration",
        "price": 45000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_deco_anniversaire",
        "days_offset": 12,
    },
    {
        "title": "Cuisine à domicile — diner 8 couverts",
        "description": "Menu béninois moderne, client fournit ingrédients (~budget 35k).",
        "responsability": "Préparation, service, vaisselle laissée propre.",
        "location": "Haie Vive",
        "city": "Cotonou",
        "sub": "Cuisine à domicile",
        "price": 30000,
        "frequency": "day",
        "type": "part_time",
        "image_seed": "job_cuisine_domicile",
        "days_offset": 7,
    },
    {
        "title": "Formation Excel — 3 sessions PME",
        "description": "Équipe compta 6 personnes, tableaux croisés & TCD.",
        "responsability": "3×2 h, support PDF, exercices fil rouge.",
        "location": "Bureau client, Ganhi",
        "city": "Cotonou",
        "sub": "Formation bureautique",
        "price": 60000,
        "frequency": "week",
        "type": "contract",
        "image_seed": "job_formation_excel",
        "days_offset": 10,
    },
    {
        "title": "Site vitrine WordPress 5 pages",
        "description": "Artisan local, hébergement déjà payé, charte logo fournie.",
        "responsability": "Maquette, intégration, formulaire contact, formation 1 h.",
        "location": "Télétravail + 1 réunion Cotonou",
        "city": "Cotonou",
        "sub": "Site web",
        "price": 150000,
        "frequency": "week",
        "type": "contract",
        "image_seed": "job_site_web",
        "days_offset": 25,
    },
    {
        "title": "Sonorisation mariage 150 invités",
        "description": "Jardin + salle, micro HF ×4, DJ set 4 h.",
        "responsability": "Installation, technicien sur place, démontage nuit.",
        "location": "Ouidah",
        "city": "Cotonou",
        "sub": "Sonorisation",
        "price": 175000,
        "frequency": "day",
        "type": "contract",
        "image_seed": "job_sono_mariage",
        "days_offset": 30,
    },
]

COVER_LETTERS = [
    "Bonjour,\n\nJe suis disponible dès {date}. J'ai réalisé des missions similaires à {city} — références sur demande.\n\nCordialement,\n{name}",
    "Madame, Monsieur,\n\nMon tarif proposé inclut le déplacement. Matériel professionnel fourni.\n\n{skills}\n\n{name}",
    "Salut ! Mission OK pour moi, je peux m'adapter à vos horaires. Expérience : {exp} ans.\n\n{name}",
    "Bonjour,\n\nJe connais bien le quartier {location}. Devis détaillé possible après visite gratuite.\n\n{name}",
]

CHAT_SCENARIOS = [
    [
        "Bonjour, votre offre « {title} » m'intéresse beaucoup.",
        "Merci ! Pouvez-vous vous déplacer pour un repérage demain matin ?",
        "Oui, entre 8h et 10h ça vous convient ?",
        "Parfait. Budget négociable si plusieurs prestations.",
        "Entendu, je vous envoie mon portfolio et mes références.",
    ],
    [
        "Bonjour, je cherche quelqu'un pour cette semaine.",
        "Je suis disponible — j'ai déjà fait ce type de chantier à {city}.",
        "Super. Vous avez vos propres outils ?",
        "Oui, tout le matériel pro. Durée estimée : 1 journée.",
        "Parfait, j'attends votre confirmation.",
    ],
]


def should_reset() -> bool:
    return os.environ.get("SEED_RESET", "").lower() in ("1", "true", "yes")


def should_skip_network() -> bool:
    return os.environ.get("SEED_SKIP_NETWORK", "").lower() in ("1", "true", "yes")


def _delete_file_field(file_field) -> None:
    if file_field and file_field.name:
        try:
            file_field.delete(save=False)
        except Exception:
            pass


def cleanup_media_files() -> None:
    for offer in JobOffer.objects.exclude(image="").iterator():
        _delete_file_field(offer.image)
    for user in User.objects.exclude(profile_picture="").iterator():
        _delete_file_field(user.profile_picture)
    for photo in PreviousWorkPhoto.objects.exclude(photo="").iterator():
        _delete_file_field(photo.photo)


def cleanup_data():
    logger.info("Nettoyage des données…")
    cleanup_media_files()
    Message.objects.all().delete()
    Conversation.objects.all().delete()
    # Escrow (dépend de Job / User)
    WalletTransaction.objects.all().delete()
    Withdrawal.objects.all().delete()
    Payment.objects.all().delete()
    Contract.objects.all().delete()
    Wallet.objects.all().delete()
    Job.objects.all().delete()
    JobFavorite.objects.all().delete()
    JobApplication.objects.all().delete()
    JobOffer.objects.all().delete()
    SubCategory.objects.all().delete()
    Category.objects.all().delete()
    UserNotification.objects.all().delete()
    NotificationToken.objects.all().delete()
    PreviousWorkPhoto.objects.all().delete()
    WorkerProfile.objects.all().delete()
    ClientProfile.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()
    logger.info("Nettoyage terminé.")


def ensure_superuser():
    phone = os.environ.get("SEED_SUPERUSER_PHONE", "+22990000000")
    user, created = User.objects.get_or_create(
        phone_number=phone,
        defaults={
            "email": "admin@azotin.local",
            "first_name": "Admin",
            "last_name": "AZOTIN",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    user.set_password(os.environ.get("SEED_SUPERUSER_PASSWORD", "admin1234"))
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    logger.info("Superuser %s.", "créé" if created else "à jour")


def upsert_user(spec: dict, subs: list[SubCategory], sub_by_name: dict, skip_network: bool) -> User:
    user, created = User.objects.get_or_create(
        phone_number=spec["phone"],
        defaults={
            "email": spec["email"],
            "first_name": spec["first_name"],
            "last_name": spec.get("last_name", ""),
            "is_active": True,
        },
    )
    city = spec.get("city", "Cotonou")
    lat, lng = LOCATIONS.get(city, LOCATIONS["Cotonou"])
    user.email = spec["email"]
    user.first_name = spec["first_name"]
    user.last_name = spec.get("last_name", "")
    user.city = city
    user.country = "Bénin"
    user.code_pin = spec.get("code_pin")
    user.bio = spec.get("bio", "")
    user.gender = spec.get("gender", "")
    user.is_certified = spec.get("is_certified", False)
    user.is_active = True
    user.location_latitude = lat + Decimal(random.randint(-200, 200)) / Decimal("10000")
    user.location_longitude = lng + Decimal(random.randint(-200, 200)) / Decimal("10000")
    user.set_password(DEFAULT_PASSWORD)
    user.save()
    UserSettings.objects.get_or_create(user=user)

    if spec.get("avatar_seed"):
        save_image_to_field(
            user,
            "profile_picture",
            spec["avatar_seed"],
            skip_network,
            image_kind="person",
            gender=spec.get("gender", ""),
        )

    if spec["role"] == "worker":
        sub = subs[spec.get("sub_idx", 0) % len(subs)]
        wp, _ = WorkerProfile.objects.get_or_create(user=user)
        wp.title = sub
        wp.category = sub.category
        wp.skills = spec.get("skills", "Polyvalent, ponctuel, sérieux.")
        wp.certifications = spec.get("certifications", "")
        wp.experience = spec.get("experience", random.randint(2, 10))
        wp.price = spec.get("price", Decimal("2500"))
        wp.frequency = spec.get("frequency", "hour")
        wp.available_for_hire = True
        wp.total_jobs_completed = random.randint(5, 45)
        wp.new_job_notification = True
        wp.new_message_notification = True
        wp.new_hire_notification = True
        wp.save()
        ClientProfile.objects.filter(user=user).delete()
        seed_worker_portfolio(
            wp,
            spec.get("avatar_seed", spec["phone"]),
            sub.name,
            skip_network,
        )
    else:
        cp, _ = ClientProfile.objects.get_or_create(user=user)
        cp.service_name = spec.get("service_name", "Services particuliers")
        cp.service_type = spec.get("service_type", "home")
        cp.service_description = spec.get("service_description", "")
        cp.location_description = spec.get("location_description", "")
        cp.average_spent = Decimal(str(random.randint(50000, 350000)))
        cp.loyalty_points = random.randint(0, 500)
        if subs:
            cp.category = subs[0].category
        cp.save()
        WorkerProfile.objects.filter(user=user).delete()

    logger.info("Utilisateur %s : %s (%s)", "créé" if created else "MAJ", spec["phone"], spec["role"])
    return user


def seed_worker_portfolio(
    wp: WorkerProfile, seed_prefix: str, sub_category: str, skip_network: bool
) -> None:
    PreviousWorkPhoto.objects.filter(worker_profile=wp).delete()
    n_photos = random.randint(3, 5)
    for i in range(n_photos):
        photo = PreviousWorkPhoto(worker_profile=wp)
        photo.save()
        save_image_to_field(
            photo,
            "photo",
            f"{seed_prefix}_work_{i}",
            skip_network,
            image_kind="job",
            sub_category=sub_category,
        )


def seed_categories():
    categories, subs, sub_by_name = [], [], {}
    for name, desc, sub_names in CATEGORIES:
        cat, _ = Category.objects.get_or_create(name=name, defaults={"description": desc})
        categories.append(cat)
        for sn in sub_names:
            sub, _ = SubCategory.objects.get_or_create(
                name=sn, category=cat, defaults={"description": f"{sn} — services {cat.name}."}
            )
            subs.append(sub)
            sub_by_name[sn] = sub
    return categories, subs, sub_by_name


def seed_job_offers(clients: list[User], sub_by_name: dict, skip_network: bool):
    offers = []
    now = timezone.now()
    for i, data in enumerate(JOB_OFFERS_DATA):
        client = clients[i % len(clients)]
        sub = sub_by_name.get(data["sub"])
        if not sub:
            sub = list(sub_by_name.values())[i % len(sub_by_name)]
        city = data.get("city", client.city or "Cotonou")
        lat, lng = LOCATIONS.get(city, LOCATIONS["Cotonou"])
        service_date = now + timedelta(days=data.get("days_offset", 3))
        offer = JobOffer(
            category=sub.category,
            sub_category=sub,
            client=client.client_profile,
            title=data["title"],
            description=data["description"],
            responsability=data["responsability"],
            location=data["location"],
            price=Decimal(str(data["price"])),
            frequency=data.get("frequency", "day"),
            type=data.get("type", "contract"),
            service_date=service_date,
            is_recurring=data.get("is_recurring", False),
            recurrence_frequency=data.get("recurrence_frequency", ""),
            location_latitude=lat + Decimal(str((i % 7) * 0.003)),
            location_longitude=lng + Decimal(str((i % 5) * 0.004)),
            is_filled=False,
        )
        offer.save()
        save_image_to_field(
            offer,
            "image",
            data.get("image_seed", f"job_{i}"),
            skip_network,
            image_kind="job",
            sub_category=data["sub"],
        )
        offers.append(offer)
    logger.info("%d offres créées (avec images).", len(offers))
    return offers


def seed_applications(offers: list[JobOffer], workers: list[User]):
    apps = []
    for offer in offers:
        sub_name = offer.sub_category.name if offer.sub_category else None
        matching = [
            w
            for w in workers
            if sub_name
            and w.worker_profile.title
            and w.worker_profile.title.name == sub_name
        ]
        pool = matching if matching else workers
        for worker in random.sample(pool, min(len(pool), random.randint(2, 4))):
            tpl = random.choice(COVER_LETTERS)
            letter = tpl.format(
                date=(timezone.now() + timedelta(days=2)).strftime("%d/%m/%Y"),
                city=worker.city or "Cotonou",
                name=f"{worker.first_name} {worker.last_name}",
                skills=worker.worker_profile.skills[:120],
                exp=worker.worker_profile.experience,
                location=offer.location,
            )
            status = random.choices(
                ["pending", "pending", "accepted", "rejected"],
                weights=[50, 20, 20, 10],
            )[0]
            app, created = JobApplication.objects.get_or_create(
                job_offer=offer,
                worker=worker.worker_profile,
                defaults={
                    "proposed_price": offer.price + Decimal(str(random.randint(-2000, 5000))),
                    "frequency": offer.frequency or "day",
                    "cover_letter": letter,
                    "status": status,
                },
            )
            if created:
                apps.append(app)

    accepted = [a for a in apps if a.status == "accepted"]
    for app in accepted[:10]:
        app.job_offer.is_filled = True
        app.job_offer.save(update_fields=["is_filled"])
        if not Job.objects.filter(job_offer=app.job_offer).exists():
            Job.objects.create(
                job_offer=app.job_offer,
                client=app.job_offer.client,
                worker=app.worker,
                description=app.job_offer.description,
                location=app.job_offer.location,
                price=app.proposed_price,
                frequency=app.frequency,
                completed=random.choice([True, False, False]),
            )
    logger.info("%d candidatures (%d acceptées).", len(apps), len(accepted))


def _contract_status_for_job(job: Job, index: int) -> str:
    """Répartit des statuts escrow réalistes pour la démo."""
    if job.completed:
        return ContractStatus.COMPLETED
    cycle = [
        ContractStatus.ACCEPTED,
        ContractStatus.WAITING_PAYMENT,
        ContractStatus.FUNDED,
        ContractStatus.WORKING,
        ContractStatus.SUBMITTED,
        ContractStatus.REVISION,
        ContractStatus.DISPUTE,
        ContractStatus.COMPLETED,
    ]
    return cycle[index % len(cycle)]


def seed_escrow(users: list[User]):
    """
    Portefeuilles + contrats escrow liés aux jobs (1-1),
    comme à l’acceptation d’un candidat.
    """
    now = timezone.now()
    contracts_created = 0
    wallets_touched = 0

    # Wallet pour chaque user (solde initial côté workers)
    for user in users:
        wallet, created = Wallet.objects.get_or_create(
            owner=user,
            defaults={"balance": Decimal("0"), "currency": "XOF"},
        )
        if created or wallet.balance == 0:
            if WorkerProfile.objects.filter(user=user).exists():
                wallet.balance = Decimal(str(random.choice([0, 15000, 35000, 75000, 120000])))
                wallet.save(update_fields=["balance", "updated_at"])
            wallets_touched += 1

    jobs = list(
        Job.objects.select_related(
            "job_offer",
            "client__user",
            "worker__user",
        ).order_by("id")
    )

    for i, job in enumerate(jobs):
        if Contract.objects.filter(job=job).exists():
            continue

        client_user = job.client.user
        freelancer_user = job.worker.user
        offer = job.job_offer
        title = (offer.title if offer else "").strip() or f"Mission #{job.pk}"
        amount = job.price or Decimal("25000")
        status = _contract_status_for_job(job, i)

        contract = Contract(
            client=client_user,
            freelancer=freelancer_user,
            job_offer=offer,
            job=job,
            title=title,
            description=(offer.description if offer else "") or title,
            amount=amount,
            currency="XOF",
            deadline=now + timedelta(days=random.randint(3, 21)),
            status=status,
        )

        if status in (
            ContractStatus.FUNDED,
            ContractStatus.WORKING,
            ContractStatus.SUBMITTED,
            ContractStatus.REVISION,
            ContractStatus.COMPLETED,
            ContractStatus.DISPUTE,
        ):
            contract.funded_at = now - timedelta(days=random.randint(1, 10))

        if status in (ContractStatus.SUBMITTED, ContractStatus.REVISION, ContractStatus.COMPLETED):
            contract.deliverable_note = (
                "Travail réalisé comme convenu. Photos et détails disponibles sur demande."
            )
            contract.deliverable_url = "https://example.com/livrable-demo"

        if status == ContractStatus.REVISION:
            contract.revision_note = "Merci de peaufiner les finitions côté gauche."

        if status == ContractStatus.DISPUTE:
            contract.dispute_reason = "Désaccord sur le périmètre livré."

        if status == ContractStatus.COMPLETED:
            contract.completed_at = now - timedelta(days=random.randint(0, 5))

        contract.save()
        contracts_created += 1

        # Paiement FedaPay simulé si déjà financé / terminé
        if status in (
            ContractStatus.WAITING_PAYMENT,
            ContractStatus.FUNDED,
            ContractStatus.WORKING,
            ContractStatus.SUBMITTED,
            ContractStatus.REVISION,
            ContractStatus.COMPLETED,
            ContractStatus.DISPUTE,
        ):
            pay_status = (
                PaymentStatus.APPROVED
                if status != ContractStatus.WAITING_PAYMENT
                else PaymentStatus.PENDING
            )
            Payment.objects.create(
                contract=contract,
                fedapay_transaction_id=f"seed-tx-{contract.pk}",
                fedapay_reference=f"SEED-REF-{contract.pk}",
                amount=amount,
                currency="XOF",
                status=pay_status,
                payment_url="https://sandbox.fedapay.com/pay/seed-demo",
                paid_at=contract.funded_at if pay_status == PaymentStatus.APPROVED else None,
            )

        # Crédit wallet freelance si contrat terminé
        if status == ContractStatus.COMPLETED:
            wallet, _ = Wallet.objects.get_or_create(owner=freelancer_user)
            wallet.balance = (wallet.balance or Decimal("0")) + amount
            wallet.save(update_fields=["balance", "updated_at"])
            WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransactionType.ESCROW_RELEASE,
                amount=amount,
                reason=f"Libération séquestre — {title[:80]}",
                contract=contract,
                balance_after=wallet.balance,
            )

    # Historique wallet démo pour le worker mobile
    demo = next((u for u in users if u.phone_number == "22997000000"), None)
    if demo:
        wallet, _ = Wallet.objects.get_or_create(owner=demo)
        if wallet.balance < Decimal("20000"):
            wallet.balance = Decimal("45000")
            wallet.save(update_fields=["balance", "updated_at"])
        if not wallet.transactions.exists():
            WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransactionType.CREDIT,
                amount=Decimal("45000"),
                reason="Solde initial démo",
                balance_after=wallet.balance,
            )
            Withdrawal.objects.create(
                wallet=wallet,
                amount=Decimal("10000"),
                status=WithdrawalStatus.COMPLETED,
                phone_number=demo.phone_number,
                method="mobile_money",
                note="Retrait démo",
                processed_at=now - timedelta(days=2),
            )

    # Cliente démo : au moins un contrat en attente de paiement
    amina = next((u for u in users if u.phone_number == "22997000001"), None)
    if amina and not Contract.objects.filter(client=amina).exists() and jobs:
        job = jobs[0]
        if job.client.user_id != amina.id:
            own = next((j for j in jobs if j.client.user_id == amina.id), None)
            job = own or job
        if not Contract.objects.filter(job=job).exists():
            offer = job.job_offer
            title = (offer.title if offer else "").strip() or f"Mission #{job.pk}"
            Contract.objects.create(
                client=job.client.user,
                freelancer=job.worker.user,
                job_offer=offer,
                job=job,
                title=title,
                description=(offer.description if offer else "") or title,
                amount=job.price or Decimal("30000"),
                currency="XOF",
                deadline=now + timedelta(days=7),
                status=ContractStatus.ACCEPTED,
            )
            contracts_created += 1

    logger.info(
        "Escrow : %d contrats, %d wallets (tx=%d, retraits=%d).",
        contracts_created,
        Wallet.objects.count(),
        WalletTransaction.objects.count(),
        Withdrawal.objects.count(),
    )


def seed_favorites(offers: list[JobOffer], users: list[User]):
    n = 0
    for user in users:
        for offer in random.sample(offers, min(8, len(offers))):
            _, c = JobFavorite.objects.get_or_create(user=user, job_offer=offer)
            if c:
                n += 1
    logger.info("%d favoris offres.", n)


def seed_favorite_workers(clients: list[User], workers: list[User]):
    from app_profile.models import FavoriteWorker

    n = 0
    for client in clients:
        for worker in random.sample(workers, min(3, len(workers))):
            _, c = FavoriteWorker.objects.get_or_create(
                user=client, worker_profile=worker.worker_profile
            )
            if c:
                n += 1
    logger.info("%d travailleurs favoris.", n)


def create_conversation(user_a: User, user_b: User, lines: list[str], offer=None):
    conv = Conversation.objects.create()
    conv.participants.add(user_a, user_b)
    base_time = timezone.now() - timedelta(days=2)
    for i, text in enumerate(lines):
        sender = user_a if i % 2 == 0 else user_b
        msg_time = base_time + timedelta(minutes=i * 37)
        Message.objects.create(
            conversation=conv,
            sender=sender,
            content=text,
            job_offer=offer if i == 0 and offer else None,
            status="read" if i < len(lines) - 1 else "sent",
            timestamp=msg_time,
            read_at=msg_time if i < len(lines) - 1 else None,
        )
    return conv


def seed_messages(users_by_phone: dict[str, User], offers: list[JobOffer]):
    amina = users_by_phone.get("22997000001")
    demo = users_by_phone.get("22997000000")
    workers = [
        users_by_phone[p]
        for p in ("22997000002", "22997000003", "22997000005", "22997000006")
        if p in users_by_phone
    ]
    count = 0
    if amina and offers:
        for i, w in enumerate(workers):
            offer = offers[i % len(offers)]
            scenario = random.choice(CHAT_SCENARIOS)
            lines = [
                line.format(title=offer.title, city=amina.city or "Cotonou")
                for line in scenario
            ]
            create_conversation(amina, w, lines, offer)
            count += 1
    if demo and amina:
        create_conversation(
            demo,
            amina,
            [
                "Bonjour, la mission livraison est terminée.",
                "Merci Demo ! Tu peux m'envoyer les photos ?",
                "Oui, tout est livré et signé.",
                "Parfait, je valide le paiement ce soir.",
            ],
        )
        count += 1
    if amina and workers:
        create_conversation(
            amina,
            workers[0],
            [
                "Bonjour, cherche quelqu'un pour le ménage hebdomadaire.",
                "Disponible chaque samedi matin.",
                "Tarif pour 4 h ?",
                "15000 FCFA, produits fournis.",
            ],
        )
        count += 1
    logger.info("%d conversations.", count)


def seed_user_notifications(users: list[User], offers: list[JobOffer]):
    amina = next((u for u in users if u.phone_number == "22997000001"), None)
    demo = next((u for u in users if u.phone_number == "22997000000"), None)
    if not offers:
        return
    specs = [
        (amina, "Nouvelle candidature sur « Réparation fuite ».", {"type": "new_application", "job_offer_id": offers[0].id}),
        (amina, "Kofi a postulé à votre offre électricité.", {"type": "new_application", "job_offer_id": offers[1].id, "applicant_name": "Kofi Mensah"}),
        (demo, "Mission assignée — livraison colis.", {"type": "job_assigned", "job_offer_id": offers[4].id}),
        (amina, "Nouveau message de Aïcha.", {"type": "new_message", "conversation_id": 1}),
        (demo, "Bienvenue sur AZOTIN !", {"type": "new_user"}),
        (amina, "Marc a aimé votre profil travailleur.", {"type": "profile_view"}),
    ]
    for recipient, msg, obj in specs:
        if not recipient:
            continue
        UserNotification.objects.create(recipient=recipient, message=msg, object=obj, is_read=random.choice([True, False]))
    for user in users:
        NotificationToken.objects.update_or_create(
            user=user,
            defaults={"token": f"ExponentPushToken[seed-{user.id}]"},
        )
    logger.info("Notifications et tokens Expo créés.")


def seed_paid_service():
    PaidService.objects.all().delete()
    PaidService.objects.create(
        is_job_offer_paid=False,
        is_job_offer_paid_price=Decimal("0"),
        is_job_application_paid=False,
        is_job_application_paid_price=Decimal("0"),
    )
    logger.info("PaidService (gratuit en dev) configuré.")


@transaction.atomic
def seed_data():
    skip_network = should_skip_network()
    logger.info("=== Seed AZOTIN (dev) — images %s ===", "OFF" if skip_network else "ON")
    with mute_all_signals():
        _run_seed(skip_network)


def _run_seed(skip_network: bool):
    if should_reset():
        cleanup_data()
    ensure_superuser()
    _, subs, sub_by_name = seed_categories()
    users, clients, workers = [], [], []
    by_phone = {}
    for spec in DEMO_USERS:
        u = upsert_user(spec, subs, sub_by_name, skip_network)
        users.append(u)
        by_phone[spec["phone"]] = u
        (clients if spec["role"] == "client" else workers).append(u)

    offers = seed_job_offers(clients, sub_by_name, skip_network)
    if workers:
        seed_applications(offers, workers)
    seed_escrow(users)
    seed_favorites(offers, users)
    if clients and workers:
        seed_favorite_workers(clients, workers)
    seed_messages(by_phone, offers)
    seed_user_notifications(users, offers)
    seed_paid_service()

    logger.info("--- Comptes ---")
    logger.info("Démo mobile : 22997000000 / PIN 1234")
    logger.info("Cliente démo : 22997000001 / PIN 1234")
    logger.info("Mot de passe : %s", DEFAULT_PASSWORD)
    logger.info(
        "=== Terminé (%d offres, %d users, %d contrats, %d wallets) ===",
        len(offers),
        len(users),
        Contract.objects.count(),
        Wallet.objects.count(),
    )

if __name__ == "__main__":
    seed_data()
