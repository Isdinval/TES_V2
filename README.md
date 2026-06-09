# TES v2 — UI Mapper 🚀

**TES v2** est un outil de mapping d'interface graphique (GUI) conçu pour permettre aux humains de créer des ensembles de données de mapping haute précision, destinés à être utilisés par des agents d'automatisation intelligents.

En combinant la puissance d'**OmniParser V2** (YOLO + Florence-2) et une interface PyQt6 intuitive, TES v2 permet d'identifier, de qualifier et de lier les éléments d'une interface métier complexe.

---

## ✨ Fonctionnalités Clés

- **📸 Capture Multi-écrans** : Capture instantanée de n'importe quel moniteur connecté.
- **🔍 Détection Assistée par IA** : Utilise OmniParser V2 pour suggérer des bounding boxes et générer des descriptions automatiques (captions).
- **🛠 Mapping Haute Précision** :
    - **Types d'UI & Actions** : Filtrage dynamique des actions autorisées par type d'élément (bouton, input, checkbox, etc.).
    - **Cibles de Clic Multiples** : Pour les groupes de boutons radio ou les dropdowns, enregistrez précisément chaque point de clic individuel.
    - **Visualisation Permanente** : Affichez les bboxes (vertes/oranges) et les points de clic (jaunes) directement sur le screenshot.
- **🗺 Navigation & Graphe** : Identifiez les boutons de navigation pour permettre à un agent de naviguer de page en page.
- **💾 Persistance & Session** : Restauration automatique des éléments déjà mappés pour une application/écran donné via un store local (`corrections_store.json`).
- **📤 Export JSON** : Génération de fichiers de mapping structurés prêts à l'emploi.

---

## 🚀 Installation

### 1. Prérequis
- Python 3.10+
- Un environnement CUDA recommandé (pour la détection OmniParser)

### 2. Dépendances
```bash
pip install -r requirements.txt
```

### 3. Poids des Modèles
Placez les poids d'OmniParser V2 dans un dossier `weights/` à la racine :
- `weights/icon_detect/model.pt` (ou `best.pt`)
- `weights/icon_caption_florence/` (modèle Florence-2)

---

## 📖 Comment l'utiliser ?

1. **Lancer l'application** : `python main.py`
2. **Configurer le Contexte** : Renseignez le nom de l'**App** (ex: `CRM_Pro`) et de l'**Écran** (ex: `Fiche_Client`).
3. **Capturer & Détecter** : Cliquez sur "Capturer", puis sur "Détecter" pour laisser l'IA suggérer les éléments.
4. **Mapper les Éléments** :
    - Cliquez sur une boîte bleue (suggérée) ou dessinez la vôtre.
    - Renseignez la **Logical Key** (nom unique utilisé par l'agent).
    - Pour les éléments complexes (Radios), utilisez le mode **Cible** (🎯) pour cliquer sur chaque option.
5. **Exporter** : Sauvegardez le résultat en JSON pour l'intégrer à votre agent.

---

## 📂 Structure du Projet

- `core/` : Logique métier (capture, détection, stockage des corrections).
- `ui/` : Interface graphique PyQt6 (Canvas, Formulaire, Liste).
- `docs/` : Documentation détaillée sur l'architecture et le modèle de données.
- `corrections_store.json` : Base de données locale des éléments validés par l'humain.

---

## 🛠 Problématiques adressées

- **Précision des clics** : L'outil permet de compenser le "jitter" ou les imprécisions de l'IA en permettant un ajustement manuel fin des cibles de clic.
- **Cohérence des données** : Le store local assure qu'un élément identique sur un même écran garde les mêmes propriétés entre deux sessions.
- **Navigation complexe** : En mappant explicitement les liens entre écrans, TES v2 jette les bases d'un graphe de navigation pour les agents autonomes.

---

*Développé avec ❤️ pour l'automatisation intelligente.*
