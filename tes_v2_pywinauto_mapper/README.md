# UIA Mapper — TES v2 🔍🪟

**Prototype de mapping d'interfaces graphiques Windows**, basé sur `pywinauto` et Microsoft **UI Automation (UIA)**.

Contrairement au module historique de TES v2 (basé sur OmniParser V2 / YOLO + Florence-2, qui *devine* visuellement les éléments d'une capture d'écran), **UIA Mapper** interroge directement l'arbre d'accessibilité Windows. Il obtient ainsi des identifiants **déterministes et stables** (AutomationId, ControlType, Patterns UIA) plutôt que des coordonnées de pixels devinées par un modèle de vision — ce qui rend le mapping plus rapide, plus fiable, et sans dépendance GPU.

Le fichier JSON produit est directement consommé par [`tes_v2_local_agent`](../tes_v2_local_agent) pour piloter l'automatisation.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20only-lightgrey)]()
[![GUI](https://img.shields.io/badge/GUI-PyQt6-41cd52)]()
[![Status](https://img.shields.io/badge/Status-Prototype-orange)]()

---

## 📚 Sommaire

- [Présentation](#-présentation)
- [Fonctionnalités clés](#-fonctionnalités-clés)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Utilisation rapide](#-utilisation-rapide)
- [Guide d'utilisation détaillé](#-guide-dutilisation-détaillé)
- [Structure du projet](#-structure-du-projet)
- [Format de sortie](#-format-de-sortie)
- [Documentation complémentaire](#-documentation-complémentaire)
- [Limitations connues](#-limitations-connues)
- [Roadmap](#-roadmap)
- [Contribuer](#-contribuer)

---

## 🧭 Présentation

`tes_v2_pywinauto_mapper` est un outil **Human-in-the-Loop (HITL)** : un humain sélectionne une fenêtre Windows, l'outil scanne son arbre UI Automation, propose automatiquement des éléments détectés (boutons, champs, cases à cocher, radios, onglets...), et l'humain valide, corrige ou complète ce mapping avant de l'exporter en JSON.

Ce JSON associe à chaque élément d'interface une **clé logique métier** (`logical_key`, ex. `bouton_connexion`) indépendante de la langue, de la résolution d'écran ou des variations mineures de mise en page — la base de tout scénario d'automatisation robuste.

Deux modes de scan sont utilisés en cascade :
1. **Backend `uia`** (Microsoft UI Automation) — le plus riche en métadonnées (patterns, valeurs, hiérarchie).
2. **Backend `win32`** — utilisé automatiquement en fallback si le scan UIA renvoie très peu d'éléments (ex. certaines applications legacy MFC/Win32 mal exposées en UIA).

L'outil fonctionne aussi bien sur des applications natives Windows (WinForms, WPF, Win32, Qt) que sur des pages web ouvertes dans Chrome/Edge (dont le DOM est exposé via UIA/Chromium accessibility tree).

---

## ✨ Fonctionnalités clés

- **🎯 Sélecteur de fenêtre "crosshair"** : cliquez n'importe où à l'écran pour cibler la fenêtre à mapper (`WindowSelector`).
- **🔎 Scan UIA avec double fallback** : `uia` → `win32` → `Desktop`, pour maximiser le nombre d'éléments détectés quel que soit le framework de l'application cible.
- **🧩 Détection de patterns UIA réels** : sonde effectivement les interfaces COM (`iface_invoke`, `iface_toggle`, `iface_selection_item`, `iface_value`, etc.) plutôt que de se fier à un simple `hasattr`, évitant les faux positifs hérités des classes de base.
- **🤖 Inférence automatique du type et de l'action** : à partir des patterns confirmés (ex. `Toggle` → `checkbox` / `check`, `Invoke` → `button` / `click`, `RangeValue` → `slider` / `set_value`...).
- **🗂 Regroupement intelligent** :
  - Les `RadioButton` et `TabItem` partageant un même parent sont automatiquement fusionnés en un seul élément logique (`radio_group` / `tab_bar`) avec une liste de `choices` cliquables.
  - **Mode "Map as Group"** : sélectionnez à la souris une zone contenant plusieurs éléments hétérogènes (ex. options de liste non reconnues comme un groupe UIA) pour les regrouper manuellement, avec reclassification automatique heuristique (ex. distinction `radio_group` vs `dropdown_group` selon l'espacement vertical).
- **✏️ Dessin manuel d'éléments** : si `pywinauto` ne détecte pas un élément (canvas HTML custom, contrôle non standard...), dessinez directement son rectangle sur le screenshot.
- **📍 Mode "Pick"** : cliquez sur le screenshot pour ajouter une `choice` (option d'un groupe) directement aux coordonnées cliquées, avec auto-remplissage du label si un élément UIA est détecté sous le curseur.
- **🖱 Déclencheur (trigger) pour listes déroulantes** : associez à un groupe de choix (ex. options d'un `<select>`) l'élément à cliquer pour les rendre visibles.
- **🗑 Suppression par glisser-déposer** : clic droit + glisser pour sélectionner et supprimer plusieurs éléments non pertinents en un geste, avec sauvegarde automatique.
- **💾 Persistance de session** : les éléments déjà mappés pour un couple *App / Écran* sont automatiquement restaurés et fusionnés (`merge_with_scanned_elements`) lors d'un nouveau scan, en se basant sur `AutomationId` puis sur `(Name, ControlType)`.
- **📐 Coordonnées relatives** : chaque rectangle est converti en `bbox_relative` (0.0–1.0), rendant le mapping indépendant de la résolution d'écran utilisée lors du scan.
- **📤 Export JSON structuré**, compatible avec le format attendu par `tes_v2_local_agent`.

---

## ⚙️ Prérequis

| Composant | Version | Remarque |
|---|---|---|
| OS | **Windows 10 / 11** | Obligatoire — `pywin32` et `win32gui`/`win32api`/`win32con` sont des API Windows natives, l'outil ne fonctionne pas sous Linux/macOS |
| Python | **3.10+** | Compatible avec les type hints modernes utilisés dans le code (`tuple[int, int]`) |
| GPU | Non requis | Contrairement au module OmniParser, aucun modèle IA local n'est chargé |

---

## 🚀 Installation

```bash
cd tes_v2_pywinauto_mapper
pip install -r requirements.txt
```

> 💡 **Astuce version figée** : le `requirements.txt` actuel ne fixe pas de versions précises. Pour un environnement reproductible, il est recommandé de générer un lock file une fois votre installation validée :
> ```bash
> pip freeze > requirements.lock.txt
> ```

`pyinstaller` (inclus dans `requirements.txt`) n'est utile que si vous souhaitez packager l'outil en exécutable autonome (`.exe`) ; ce n'est pas une dépendance nécessaire pour l'exécution via `python main.py`.

---

## ▶️ Utilisation rapide

```bash
python main.py
```

1. Renseignez le contexte **App** / **Écran** en haut de la fenêtre.
2. Cliquez sur **Select Window**, puis cliquez sur la fenêtre cible à l'écran.
3. Le scan se lance automatiquement : les éléments détectés apparaissent en couleur sur le screenshot.
4. Sélectionnez un élément, renseignez sa `Logical Key`, son `UI Type` et son `Action` dans le formulaire à droite.
5. Cliquez sur **Update Element**, qui sauvegarde automatiquement le mapping.
6. Utilisez **Save All Mappings** pour forcer un export à tout moment.

---

## 📖 Guide d'utilisation détaillé

Voir [`docs/user_guide.md`](docs/user_guide.md) pour la procédure complète (groupes de choix, mode dessin, triggers de listes déroulantes, code couleur des contours...).

---

## 📂 Structure du projet

```
tes_v2_pywinauto_mapper/
├── main.py                     # Point d'entrée de l'application PyQt6
├── requirements.txt
├── core/
│   ├── element.py              # Dataclass UIElement (modèle de données central)
│   ├── uia_scanner.py          # Scan UIA/win32, détection de patterns, regroupement
│   ├── mapping_store.py        # Persistance JSON, fusion avec scan existant
│   ├── window_selector.py      # Sélection de fenêtre via win32gui
│   └── utils.py                # Génération de logical_key (normalisation Unicode)
├── ui/
│   ├── main_window.py           # Fenêtre principale, orchestration des modes
│   ├── canvas_view.py           # Rendu du screenshot + overlays interactifs
│   ├── element_form.py          # Formulaire de mapping (type, action, choices, trigger)
│   └── element_info_panel.py    # Panneau de métadonnées techniques en lecture seule
├── mappings/                    # Fichiers JSON exportés (un par couple App/Écran)
└── docs/                        # Documentation détaillée (ce dossier)
```

---

## 🗃 Format de sortie

Chaque export génère un fichier `mappings/<App>_<Écran>.json` avec une section `meta` (résolution, backend, titre de fenêtre) et une liste `elements`. Détails complets, schéma et exemples : [`docs/data_model.md`](docs/data_model.md).

---

## 📘 Documentation complémentaire

| Document | Contenu |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Architecture technique détaillée, flux de données, stack |
| [`docs/data_model.md`](docs/data_model.md) | Schéma JSON complet du format d'export |
| [`docs/user_guide.md`](docs/user_guide.md) | Procédure pas-à-pas pour un mapping complet |
| [`docs/challenges.md`](docs/challenges.md) | Défis techniques rencontrés et solutions retenues |

---

## ⚠️ Limitations connues

- **Windows uniquement** : dépendance forte à `pywin32` / UI Automation.
- **Multi-écrans** : la résolution de référence (`ref_resolution`) utilisée pour calculer les `bbox_relative` est celle de l'écran **principal** (`GetSystemMetrics`), même si la fenêtre ciblée se trouve sur un écran secondaire de résolution différente. Pour des setups multi-écrans hétérogènes, vérifiez que la fenêtre à mapper est sur l'écran principal, ou attendez la correction listée en Roadmap.
- **Pas de tests automatisés** dans ce sous-module (à la différence de la racine du repo).
- **`__pycache__` non ignorés** : pensez à ajouter un `.gitignore` avant de committer.
- Certaines applications très custom (canvas HTML5, rendu Skia/Flutter) exposent peu ou pas d'arbre UIA exploitable ; utilisez alors le mode **✏ Draw Element**.

---

## 🗺 Roadmap

- [ ] Corriger le calcul de `ref_resolution` pour les configurations multi-écrans (utiliser la résolution de l'écran réel contenant la fenêtre, ex. via `win32api.MonitorFromWindow`).
- [ ] Ajouter un `.gitignore` (`__pycache__/`, `*.pyc`) et une licence au dépôt.
- [ ] Épingler les versions dans `requirements.txt` / séparer les dépendances de build (`pyinstaller`) dans un `requirements-dev.txt`.
- [ ] Couverture de tests unitaires pour `core/utils.py` et `core/mapping_store.py`.
- [ ] Remplacer les `print()` de debug par un logger configurable (`logging`).

---


---

*Développé dans le cadre du projet TES v2 — automatisation d'interfaces métier haute fidélité.*
