# Base sectorielle BVC

Indicateurs sectoriels des sociétés cotées à la Bourse de Casablanca, mis à jour
automatiquement et consultables dans un tableau de bord en ligne.

## Fonctionnement

| Fichier | Rôle |
|---|---|
| `catalogue.yaml` | Liste des séries suivies (secteur, source, unité, calculs). **Ajouter une série = ajouter une ligne.** |
| `collect/` | Un module de collecte par type de source (BKAM, Office des Changes, marchés) |
| `update.py` | Lance la collecte, fusionne et calcule les séries dérivées |
| `data/series.csv` | La base (format long : id, date, valeur) |
| `data/statut.json` | État de chaque source (dernier point, erreurs) |
| `app.py` | Tableau de bord Streamlit |
| `.github/workflows/update.yml` | Mise à jour automatique quotidienne |

Une source en échec conserve ses anciennes données ; GitHub envoie alors un e-mail.
