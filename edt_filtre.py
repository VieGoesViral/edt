#!/usr/bin/env python3
"""
Filtre l'emploi du temps HyperPlanning d'Avignon Université :
télécharge le flux ICS, retire tous les événements dont le
titre commence par "Réservation de salles" (bruit administratif),
convertit les horaires UTC du flux source en heure locale Europe/Paris
explicite (TZID), puis écrit un fichier .ics propre dans docs/
(servi ensuite par GitHub Pages).

Utilisation :
    EDT_URL="https://edt-api.univ-avignon.fr/..." python3 edt_filtre.py
"""

import os
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Timezone, TimezoneStandard, TimezoneDaylight, vRecur

# --- Config ---------------------------------------------------------
URL = os.environ["EDT_URL"]
OUTPUT_FILE = "docs/edt_filtre.ics"
FUSEAU = ZoneInfo("Europe/Paris")

# Motifs à exclure du résumé (SUMMARY), en minuscules
MOTS_A_EXCLURE = ["reservation de salles", "réservation de salles"]
# ---------------------------------------------------------------------


def normaliser(texte: str) -> str:
    """Minuscule + retire les accents simples pour comparer sans piège."""
    remplacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a",
        "î": "i", "ï": "i",
        "ô": "o",
        "ù": "u", "û": "u",
        "ç": "c",
    }
    texte = texte.lower()
    for accent, plain in remplacements.items():
        texte = texte.replace(accent, plain)
    return texte


def construire_vtimezone() -> Timezone:
    """Bloc VTIMEZONE standard pour Europe/Paris (CET/CEST)."""
    tz = Timezone()
    tz.add("TZID", "Europe/Paris")

    ete = TimezoneDaylight()
    ete.add("TZNAME", "CEST")
    ete.add("DTSTART", datetime(1970, 3, 29, 2, 0, 0))
    ete.add("TZOFFSETFROM", timedelta(hours=1))
    ete.add("TZOFFSETTO", timedelta(hours=2))
    ete.add("RRULE", vRecur(FREQ="YEARLY", BYMONTH=3, BYDAY="-1SU"))
    tz.add_component(ete)

    hiver = TimezoneStandard()
    hiver.add("TZNAME", "CET")
    hiver.add("DTSTART", datetime(1970, 10, 25, 3, 0, 0))
    hiver.add("TZOFFSETFROM", timedelta(hours=2))
    hiver.add("TZOFFSETTO", timedelta(hours=1))
    hiver.add("RRULE", vRecur(FREQ="YEARLY", BYMONTH=10, BYDAY="-1SU"))
    tz.add_component(hiver)

    return tz


def convertir_en_heure_locale(composant):
    """Remplace les DTSTART/DTEND UTC par une heure locale Europe/Paris explicite (TZID)."""
    for champ in ("dtstart", "dtend"):
        valeur = composant.get(champ)
        if valeur is not None and getattr(valeur.dt, "tzinfo", None) is not None:
            heure_locale = valeur.dt.astimezone(FUSEAU)
            del composant[champ]
            composant.add(champ, heure_locale)


def telecharger_ics(url: str) -> bytes:
    with urllib.request.urlopen(url) as reponse:
        return reponse.read()


def filtrer_calendrier(donnees_ics: bytes) -> Calendar:
    cal_source = Calendar.from_ical(donnees_ics)
    cal_filtre = Calendar()

    # Recopie les métadonnées du calendrier (nom, description, etc.)
    for cle, valeur in cal_source.items():
        cal_filtre.add(cle, valeur)

    # Bloc de fuseau horaire, pour que tous les calendriers affichent
    # la bonne heure locale (au lieu de l'UTC brut du flux source)
    cal_filtre.add_component(construire_vtimezone())

    nb_total = 0
    nb_retires = 0

    for composant in cal_source.walk():
        if composant.name == "VEVENT":
            nb_total += 1
            resume = str(composant.get("summary", ""))
            resume_norm = normaliser(resume)

            if any(mot in resume_norm for mot in
                   (normaliser(m) for m in MOTS_A_EXCLURE)):
                nb_retires += 1
                continue  # on saute cet événement

            convertir_en_heure_locale(composant)
            cal_filtre.add_component(composant)

    print(f"Événements analysés : {nb_total}")
    print(f"Événements retirés (réservation de salles) : {nb_retires}")
    print(f"Événements conservés : {nb_total - nb_retires}")

    return cal_filtre


def main():
    print("Téléchargement de l'emploi du temps...")
    donnees = telecharger_ics(URL)

    print("Filtrage...")
    cal_filtre = filtrer_calendrier(donnees)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "wb") as f:
        f.write(cal_filtre.to_ical())

    print(f"\nFichier généré : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
