# Architecture Technique — TES v2

## Vue d'ensemble

TES v2 est conçu comme un outil de "Human-in-the-loop" (HITL) pour raffiner les prédictions d'OmniParser. L'application sépare strictement la détection IA, la gestion des données et l'interface utilisateur.

## Composants Principaux

### 1. Core (Moteur)
- **OmniParser Bridge** (`core/omniparser_bridge.py`) : Gère le chargement des modèles YOLO (détection d'icônes) et Florence-2 (génération de descriptions). Il convertit les sorties des modèles en objets `BboxCandidate` normalisés.
- **Mapping Store** (`core/mapping_store.py`) : Le cerveau de la persistance. Il gère le `corrections_store.json`, effectue les calculs de `click_target` et prépare les exports JSON.
- **Stable ID** (`core/stable_id.py`) : Génère des identifiants déterministes basés sur les coordonnées quantifiées des bboxes pour assurer la cohérence entre les sessions.

### 2. UI (Interface)
- **Canvas View** (`ui/canvas_view.py`) : Widget personnalisé gérant le rendu du screenshot et des overlays (candidates IA, éléments mappés, points de clic). Il implémente un système de coordonnées relatives pour être indépendant de la résolution d'affichage.
- **Element Form** (`ui/element_form.py`) : Formulaire dynamique qui change ses champs en fonction du `ui_type`. Il pilote le mode de "Target Sampling".
- **Main Window** (`ui/main_window.py`) : Chef d'orchestre coordonnant les threads de détection, les captures d'écran et la communication entre les widgets.

## Flux de Données

1. **Capture** : Le screenshot est pris via `mss` ou le système natif.
2. **Détection** : Une image PIL est envoyée au `DetectionWorker` (thread séparé).
3. **Sélection** : L'utilisateur clique sur un candidat. Le `MappingStore` cherche une correction existante pour pré-remplir le formulaire.
4. **Validation** : Lors de la confirmation, `build_element` calcule la cible de clic finale.
5. **Stockage** : L'élément est ajouté à la liste UI et mergé dans le `corrections_store.json`.

## Stack Technique
- **GUI** : PyQt6
- **IA** : Ultralytics (YOLOv8/v10), HuggingFace Transformers (Florence-2)
- **Image** : Pillow (PIL)
- **Capture** : mss
