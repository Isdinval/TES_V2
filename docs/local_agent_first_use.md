# Guide de première utilisation - TES_V2 Local Agent 🚀

Ce guide vous explique comment configurer et lancer l'agent local pour la première fois, en profitant des nouvelles fonctionnalités de robustesse.

## 1. Installation

Assurez-vous d'avoir Python 3.11+ d'installé.

```bash
# Cloner le dépôt et entrer dans le dossier
# Installer les dépendances
pip install -r requirements.txt
```

## 2. Configuration de la robustesse

L'agent utilise un fichier de configuration pour ajuster son comportement face aux interfaces dynamiques.

Le fichier par défaut se trouve dans : `tes_v2_local_agent/config/default_robustness.yaml`.

**Paramètres clés :**
- `template_matching_threshold`: Précision pour la recherche des étiquettes (labels).
- `max_scroll_attempts`: Nombre maximum de scrolls vers le bas si un élément n'est pas trouvé.
- `mask_inputs_in_hash`: Masque les champs de saisie lors de la détection d'écran pour tolérer les formulaires déjà remplis.

## 3. Préparation des Mappings (Robustesse)

Pour rendre vos mappings existants "robustes", vous pouvez ajouter manuellement des ancres dans vos fichiers JSON :

```json
{
  "logical_key": "patient_nom",
  "requires_relocation": true,
  "label_anchor": {
    "bbox_relative": {"x": 0.1, "y": 0.2, "w": 0.05, "h": 0.02},
    "template_path": "anchors/patient_nom_label.png"
  },
  ...
}
```
*Note : Le `template_path` est relatif au dossier contenant le JSON du mapping.*

## 4. Lancement de l'Agent

Utilisez la commande suivante pour lancer un scénario :

```bash
python -m tes_v2_local_agent.main \
  --data data/source.xlsx \
  --scenario Login,Dashboard,FichePatient \
  --mappings mappings/ \
  --refs reference_screenshots/ \
  --dry-run # Toujours commencer par un dry-run !
```

## 5. Fonctionnement en cas d'erreur

Si l'agent ne trouve pas un élément ou un écran :
1. Il tentera de **scroller** automatiquement vers le bas.
2. Il attendra que l'image se **stabilise** (évite de cliquer pendant une animation).
3. En cas d'échec final, une **capture d'écran d'erreur** (`error_*.png`) est générée à la racine pour diagnostic.

## 6. Arrêt d'urgence

À tout moment, appuyez sur la touche **Echap (ESC)** pour stopper l'exécution immédiatement.

---
*Développé pour une automatisation robuste avec TES_V2.*
