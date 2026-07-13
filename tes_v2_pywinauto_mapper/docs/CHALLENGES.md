# Défis Techniques et Solutions — UIA Mapper

## 1. Faux positifs sur les patterns UIA

**Problématique** : `pywinauto` expose des propriétés `iface_*` sur toutes ses classes de contrôle par héritage, y compris pour des patterns qu'un élément ne supporte pas réellement. Un simple `hasattr(ctrl, "iface_toggle")` renvoie donc souvent `True` même si l'élément ne supporte pas réellement le pattern `Toggle`, ce qui fausserait la classification automatique de `ui_type`/`action`.

**Solution** : `_detect_true_patterns()` tente d'accéder **effectivement** à chaque interface COM (`ctrl.iface_invoke`, `ctrl.iface_toggle`...) et capture `NoPatternInterfaceError` lorsque le pattern n'est pas réellement disponible. Seuls les patterns qui ne lèvent pas d'exception sont retenus — ce qui garantit une inférence de `ui_type`/`action` fiable (`Toggle` confirmé → `checkbox`/`check`, etc.).

## 2. Éléments UI à choix multiples sans structure UIA exploitable

**Problématique** : certaines interfaces (notamment des pages web avec des listes stylisées en CSS, ou des composants custom) n'exposent pas de parenté UIA claire entre les options d'un même groupe logique (radios, onglets), rendant le regroupement automatique par `_group_elements()` inopérant.

**Solution** : le **mode "Map as Group"** permet à l'humain de sélectionner visuellement une zone contenant plusieurs éléments hétérogènes. L'outil applique alors une heuristique de classification par vote majoritaire (`Counter` sur les `control_type` de la zone) et une détection de régularité d'espacement vertical pour distinguer un groupe de radios (souvent espacé de façon variable) d'une liste déroulante ouverte (options généralement collées, espacement quasi-constant) — reclassifiant automatiquement en conséquence, avec un message explicite si le résultat reste incertain.

## 3. Éléments non détectables par UIA (canvas custom, rendus non standards)

**Problématique** : certains contrôles (canvas HTML5, composants Flutter/Skia, widgets propriétaires) ne sont tout simplement pas exposés dans l'arbre d'accessibilité, ou sont fusionnés en un unique bloc opaque.

**Solution** : le **mode "✏ Draw Element"** permet de créer un `UIElement` de type `Manual`, purement défini par ses coordonnées, sans dépendre d'une correspondance UIA. Ces éléments sont explicitement préservés d'un scan à l'autre (le scan ne pouvant, par définition, jamais les redétecter automatiquement).

## 4. Fiabilité du scan selon le framework de l'application cible

**Problématique** : certaines applications legacy (MFC, Win32 pur) exposent un arbre UIA très pauvre, alors que le backend `win32` de `pywinauto` (basé sur les messages Win32 natifs) y est parfois bien plus complet — et inversement pour des applications modernes (WPF, Electron, pages web).

**Solution** : `UIAScanner.scan()` tente d'abord le backend `uia`. Si moins de 3 éléments sont retournés, un second scan est automatiquement effectué avec le backend `win32`, et le résultat le plus riche des deux est conservé (`self.backend` reflète le backend finalement retenu, propagé jusque dans `meta.backend` de l'export).

## 5. Cohérence du mapping entre deux sessions de travail

**Problématique** : relancer un scan sur un écran déjà mappé auparavant ne doit pas faire perdre le travail humain déjà réalisé (`logical_key`, `notes`, `expected_value`...), même si les coordonnées ont légèrement changé entre deux sessions.

**Solution** : `MappingStore.merge_with_scanned_elements()` réconcilie chaque élément fraîchement scanné avec le mapping précédemment sauvegardé, par priorité décroissante : correspondance sur `automation_id` (la plus stable), puis à défaut sur le couple `(name, control_type)`. Les métadonnées humaines sont recopiées ; les propriétés techniques (rectangle, patterns) restent celles du scan courant, garantissant que les coordonnées ne se figent jamais sur d'anciennes valeurs obsolètes.

## 6. Indépendance vis-à-vis de la résolution d'écran

**Problématique** : un mapping réalisé à une résolution donnée doit pouvoir être rejoué par l'agent d'automatisation même si l'écran d'exécution a une résolution légèrement différente.

**Solution** : chaque rectangle est converti en `bbox_relative` (0.0 à 1.0), calculé relativement à `ref_resolution` (résolution de l'écran principal au moment du scan, stockée dans `meta.resolution`). L'agent peut ainsi reconvertir ces coordonnées relatives en pixels à l'exécution, quelle que soit sa propre résolution.

> ⚠️ **Limite actuelle** : `ref_resolution` est calculée via `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`, qui renvoie la résolution de l'écran **principal**, alors que la capture d'écran elle-même (`ImageGrab.grab(..., all_screens=True)`) supporte le multi-écrans. Sur une configuration multi-écrans hétérogène où la fenêtre cible se trouve sur un écran secondaire de résolution différente, un léger décalage de `bbox_relative` peut apparaître. Voir la Roadmap du README pour la correction envisagée (résolution de l'écran réellement occupé par la fenêtre, via `MonitorFromWindow`).

## 7. Suppression rapide d'éléments non pertinents

**Problématique** : un scan `Show All` peut renvoyer plusieurs dizaines d'éléments, dont beaucoup ne sont pas pertinents pour l'automatisation (labels décoratifs, conteneurs vides) — les supprimer un par un serait fastidieux.

**Solution** : un mode de suppression par glisser avec le clic droit permet de sélectionner une zone entière ; les éléments concernés sont surlignés en rouge en temps réel avant confirmation (relâchement du clic), avec sauvegarde automatique immédiate après suppression.
