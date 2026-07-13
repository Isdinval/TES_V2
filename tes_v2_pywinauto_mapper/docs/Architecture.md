# Architecture Technique — UIA Mapper

## Vue d'ensemble

`tes_v2_pywinauto_mapper` suit une architecture **Human-in-the-Loop (HITL)** en couches strictement séparées : détection technique (UI Automation), gestion des données (persistance JSON), et interface utilisateur (PyQt6). Contrairement au module historique OmniParser de TES v2, aucune inférence de modèle de vision n'intervient : la "détection" consiste à interroger l'arbre d'accessibilité natif exposé par Windows.

```
┌─────────────────────────────────────────────────────────┐
│                      ui/main_window.py                    │
│         (orchestration : modes, signaux, sauvegarde)       │
└───────────┬─────────────────────────────────┬─────────────┘
            │                                 │
   ┌────────▼────────┐               ┌────────▼─────────┐
   │ ui/canvas_view   │               │ ui/element_form   │
   │ (rendu + input)  │               │ (édition mapping) │
   └────────┬────────┘               └────────┬─────────┘
            │                                 │
            │           core/element.py (UIElement)          │
            │                                 │
   ┌────────▼────────┐               ┌────────▼─────────┐
   │core/uia_scanner  │               │core/mapping_store │
   │ (scan + patterns)│               │ (persistance JSON)│
   └────────┬────────┘               └───────────────────┘
            │
   ┌────────▼────────┐
   │core/window_selec.│
   │ (win32gui/win32api)
   └──────────────────┘
```

## Composants principaux

### 1. Core (moteur)

- **`core/element.py`** — `UIElement` : dataclass unique représentant à la fois les propriétés techniques UIA (name, automation_id, control_type, class_name, rectangle, patterns...) et les propriétés métier de mapping (logical_key, ui_type, action, notes, expected_value...). Fournit `to_dict()` / `from_dict()` pour la sérialisation, avec calcul à la volée de `bbox_relative` et `stable_id`.

- **`core/uia_scanner.py`** — `UIAScanner` : cœur technique du projet.
  - `capture_window()` : capture d'écran de la fenêtre ciblée via `PIL.ImageGrab` (avec support multi-écrans `all_screens=True`), après restauration si la fenêtre est minimisée (`IsIconic` / `ShowWindow`).
  - `scan()` : orchestration du scan avec triple fallback `uia` → `win32` → `Desktop`, activé automatiquement si le premier backend renvoie moins de 3 éléments.
  - `_detect_true_patterns()` : sonde chaque interface COM UIA (`iface_invoke`, `iface_toggle`, `iface_value`, `iface_range_value`, `iface_selection_item`, `iface_expand_collapse`, `iface_grid`, `iface_scroll`...) en capturant `NoPatternInterfaceError`, garantissant que seuls les patterns **réellement supportés** sont retenus (contrairement à un simple `hasattr` qui remonterait des faux positifs hérités de la classe de base pywinauto).
  - `_infer_action_from_patterns()` : table de décision qui déduit `ui_type`/`action` par défaut à partir des patterns confirmés (ex. `Toggle` → checkbox/check, `Invoke` sur `MenuItem` → menu_item/click).
  - `_build_uia_path()` : reconstruit un chemin hiérarchique lisible (`Dialog[@title='Login'] > Edit[@auto_id='txtUser']`) en remontant l'arbre des parents, en ignorant les conteneurs structurels sans identité (`Pane`, `Custom` sans nom ni AutomationId).
  - `_group_elements()` : post-traitement qui fusionne les `RadioButton`/`TabItem` partageant le même parent stable en un seul `UIElement` de type `RadioGroup`/`TabGroup`, avec une liste `choices` (label, coordonnées relatives, stable_id).

- **`core/mapping_store.py`** — `MappingStore` : persistance des exports (`mappings/<App>_<Écran>.json`) et fusion (`merge_with_scanned_elements`) entre un nouveau scan et un mapping existant, avec résolution d'identité par priorité : `AutomationId` d'abord, puis couple `(Name, ControlType)`.

- **`core/utils.py`** — `name_to_logical_key()` : conversion déterministe d'un libellé affiché (potentiellement accentué, avec caractères d'accélérateur Win32 `&`) en clé logique ASCII normalisée (`"Prénom :"` → `"prenom"`).

- **`core/window_selector.py`** — `WindowSelector` : sélection de fenêtre par pointage souris (`WindowFromPoint` + remontée à la fenêtre racine via `GetAncestor(GA_ROOT)`), interrogée par polling toutes les 50 ms tant qu'aucun clic n'est détecté.

### 2. UI (interface)

- **`ui/canvas_view.py`** — `CanvasView` : widget central gérant le rendu du screenshot mis à l'échelle et de tous les overlays (bounding boxes colorées selon l'état de l'élément, points de membres de groupe, rectangles de sélection/dessin/suppression). Implémente un système de coordonnées relatives (`scale`/`offset`) pour rester cohérent quelle que soit la taille de la fenêtre applicative. Gère quatre modes d'interaction exclusifs : sélection normale, dessin manuel (`_draw_mode`), regroupement par glisser (`_drag_mode`), et sélection ponctuelle de coordonnées (`_pick_mode`), plus une suppression par glisser-clic droit.

- **`ui/element_form.py`** — `ElementForm` : formulaire dynamique dont les champs visibles changent selon le `ui_type` sélectionné (ex. affichage du bloc "Choices" uniquement pour les types groupés, affichage du bloc "Trigger" pour les listes déroulantes). Contient `ChoiceListWidget`, un sous-composant listant les options d'un groupe avec badges colorés par type UIA et détection heuristique des options non interactives.

- **`ui/element_info_panel.py`** — `ElementInfoPanel` : panneau en lecture seule affichant les métadonnées techniques brutes de l'élément sélectionné (utile pour le diagnostic), avec un bandeau d'avertissement si l'élément a été créé manuellement (pas de données UIA).

- **`ui/main_window.py`** — `MainWindow` : chef d'orchestre. Gère le cycle sélection de fenêtre → scan → affichage, la persistance de la disposition des panneaux (`QSettings`), la sauvegarde automatique après chaque suppression ou mise à jour d'élément, et la logique de résolution des `trigger` pour les groupes liés à un élément `dropdown`.

## Flux de données

1. **Sélection** : l'utilisateur clique sur "Select Window" puis sur une fenêtre à l'écran ; `WindowSelector` résout le handle natif de la fenêtre racine.
2. **Capture** : `UIAScanner.capture_window()` prend un screenshot de la zone de la fenêtre.
3. **Scan** : `UIAScanner.scan()` interroge l'arbre UIA (avec fallback win32 si nécessaire), détecte les patterns réels par élément, infère `ui_type`/`action`, et regroupe radios/tabs.
4. **Fusion** : si un mapping existe déjà pour le couple App/Écran, `MappingStore.merge_with_scanned_elements()` réinjecte les `logical_key`, `notes`, etc. déjà validés par l'humain.
5. **Édition** : l'utilisateur clique sur un élément dans `CanvasView`, le formulaire `ElementForm` se pré-remplit (suggestion de clé logique en cascade : AutomationId → nom normalisé → hash du rectangle), l'utilisateur ajuste puis valide.
6. **Sauvegarde** : chaque validation ou suppression déclenche un export silencieux (`_on_export_requested(silent=True)`) vers `mappings/<App>_<Écran>.json`.

## Stack technique

- **GUI** : PyQt6
- **Automatisation UI** : `pywinauto` (backends `uia` et `win32`), `pywin32` (`win32gui`, `win32api`, `win32con`)
- **Image** : Pillow (`ImageGrab` pour la capture d'écran)
- **Packaging (optionnel)** : PyInstaller
