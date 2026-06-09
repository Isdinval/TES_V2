# Modèle de Données — TES v2

L'outil manipule deux formats JSON principaux : le store interne et le format d'export.

## 1. Corrections Store (`corrections_store.json`)

C'est la base de données locale de l'application. Elle est structurée par application et par écran.

```json
{
  "App::Ecran": {
    "stable_id": {
      "logical_key": "nom_du_champ",
      "ui_type": "button",
      "action": "click",
      "path": "Menu > Aide",
      "bbox_relative": { "x": 0.1, "y": 0.2, "w": 0.05, "h": 0.02 },
      "source": "human",
      "navigation_config": {
         "target_screen": "destination_name"
      },
      "choices": [
        { "label": "Option 1", "x": 0.11, "y": 0.21 }
      ]
    }
  }
}
```

## 2. Format d'Export

Ce format est celui consommé par les agents d'automatisation. Il inclut des métadonnées de résolution pour permettre la conversion des coordonnées relatives en pixels absolus si nécessaire.

### Structure Globale
- **meta** : Informations sur l'application, l'écran, la résolution de capture et la date.
- **elements** : Liste des éléments mappés.

### Spécificités par Type
- **Standard** : Contient `click_target` {x, y}.
- **Multi-choix** : Contient une liste `choices` avec les libellés et leurs coordonnées respectives.
- **Scroll Area** : Ne contient PAS de `click_target`, mais un objet `scroll_config` {direction, amount}.
- **Navigation** : Contient un objet `navigation_config` indiquant l'écran suivant.

## 3. Calcul du Click Target

Le `click_target` est calculé selon les règles suivantes :
- **Checkbox / Radio** : `x = x_start + width * 0.15` (pour viser la case à cocher et non le label).
- **Scroll Area** : Aucun point de clic généré.
- **Défaut** : Centre de la bounding box (`x + w/2`, `y + h/2`).
