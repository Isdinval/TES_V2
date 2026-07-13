# Modèle de Données — UIA Mapper

Un seul format JSON est produit par l'outil : le **fichier d'export** `mappings/<App>_<Écran>.json`, directement consommé par `tes_v2_local_agent`.

## 1. Structure globale

```json
{
  "meta": {
    "app": "MyApp",
    "screen": "MainScreen",
    "backend": "uia",
    "window_title": "Demo UX Interactive - 2 Pages - Google Chrome",
    "created_at": "2026-07-13T11:24:02",
    "resolution": [1920, 1080]
  },
  "elements": [ /* liste de UIElement sérialisés */ ]
}
```

- **`meta.backend`** : `"uia"` ou `"win32"`, selon le backend `pywinauto` qui a effectivement produit le meilleur scan.
- **`meta.resolution`** : résolution de référence (écran principal) utilisée pour convertir les rectangles absolus en coordonnées relatives. **Doit être identique** à la résolution utilisée lors de la ré-exécution par l'agent, sauf si celui-ci recalcule via `bbox_relative`.
- **`meta.created_at`** : horodatage ISO 8601, régénéré à chaque export (dernier export = dernière vérité).

## 2. Élément standard (`UIElement.to_dict()`)

```json
{
  "logical_key": "nom",
  "ui_type": "text_input",
  "action": "click_then_type",
  "name": "Nom complet",
  "automation_id": "nom",
  "control_type": "Edit",
  "class_name": "w-full px-4 py-3 border ...",
  "framework_id": "Chrome",
  "rectangle": [622, 373, 676, 63],
  "is_enabled": true,
  "is_visible": true,
  "value": "",
  "supported_patterns": ["Value", "Text"],
  "execution_hint": "uia_native",
  "notes": "",
  "path": "Document[@auto_id='RootWebArea'] > Edit[@auto_id='nom']",
  "expected_value": "",
  "value_pattern": true,
  "stable_id": "nom_Edit",
  "bbox_relative": { "x": 0.323958, "y": 0.345370, "w": 0.352083, "h": 0.058333 },
  "source": "human"
}
```

| Champ | Type | Description |
|---|---|---|
| `logical_key` | str | Identifiant métier unique utilisé par l'agent d'automatisation. **Obligatoire** pour qu'un élément soit inclus dans l'export. |
| `ui_type` | str | Catégorie fonctionnelle (`button`, `text_input`, `checkbox`, `radio`, `dropdown`, `radio_group`, `tab_bar`, `dropdown_group`, `scroll_area`...). |
| `action` | str | Action à exécuter (`click`, `click_then_type`, `check`, `select_by_label`...), dépendante de `ui_type`. |
| `rectangle` | [x, y, w, h] | Coordonnées **absolues en pixels**, dans le référentiel de l'écran au moment du scan. |
| `bbox_relative` | {x, y, w, h} | Coordonnées **normalisées** (0.0–1.0) par rapport à `meta.resolution`. Permet à l'agent de recalculer la position en pixels quelle que soit la résolution d'exécution. |
| `supported_patterns` | list[str] | Patterns UIA effectivement confirmés (`Invoke`, `Toggle`, `Value`, `SelectionItem`, `RangeValue`, `ExpandCollapse`, `Grid`, `Scroll`...). |
| `execution_hint` | str | `"uia_native"` si l'agent peut invoquer directement le pattern UIA (plus fiable), `"pyautogui_fallback"` s'il doit simuler un clic physique. |
| `path` | str | Chemin hiérarchique reconstruit (utile pour le diagnostic et la ré-identification en cas de changement mineur de layout). |
| `stable_id` | str | `automation_id` si disponible, sinon `f"{name}_{control_type}"` — clé de fusion utilisée par `merge_with_scanned_elements`. |
| `source` | str | Toujours `"human"` — présent uniquement si `ref_resolution` a été renseignée (compatibilité avec `tes_v2_local_agent`). |

## 3. Élément groupé (radio/tab/checkbox/dropdown)

Les groupes (`radio_group`, `tab_bar`, `checkbox_group`, `dropdown_group`) n'ont pas de `rectangle` d'un contrôle unique mais une **bounding box englobante** et une liste `choices` :

```json
{
  "logical_key": "genre",
  "ui_type": "radio_group",
  "action": "select_by_label",
  "control_type": "RadioGroup",
  "rectangle": [622, 500, 300, 40],
  "choices": [
    { "label": "Homme", "x": 0.331, "y": 0.481, "stable_id": "genre_h_RadioButton" },
    { "label": "Femme", "x": 0.401, "y": 0.481, "stable_id": "genre_f_RadioButton" }
  ],
  "trigger": null
}
```

- **`choices[].x/y`** : coordonnées **relatives du centre** de l'option, prêtes à être cliquées directement par l'agent.
- **`trigger`** : objet optionnel `{x, y, w, h}` (relatif) indiquant l'élément à cliquer pour rendre les options visibles — utilisé notamment pour les `dropdown_group` dont les options ne sont visibles qu'après un clic d'ouverture. `null`/absent si les options sont toujours visibles (cas typique des radios).

## 4. Élément manuel (dessiné à la main)

Un élément créé via le mode **✏ Draw Element** a `control_type: "Manual"` et aucune métadonnée UIA (patterns vides, `automation_id` vide) :

```json
{
  "logical_key": "zone_signature",
  "ui_type": "button",
  "action": "click",
  "control_type": "Manual",
  "automation_id": "",
  "supported_patterns": [],
  "execution_hint": "pyautogui_fallback"
}
```

Ces éléments sont **préservés d'une session à l'autre** : lors d'un nouveau scan, `main_window._run_scan()` réinjecte explicitement les éléments `Manual` de la session précédente, car ils ne peuvent pas être retrouvés par un nouveau scan UIA.

## 5. Règles de fusion (`merge_with_scanned_elements`)

Lorsqu'un mapping existant est chargé pour le même couple App/Écran, chaque élément fraîchement scanné est réconcilié avec l'ancien mapping selon cette priorité :

1. **`automation_id`** identique (le plus fiable).
2. À défaut, couple **`(name, control_type)`** identique.

Si une correspondance est trouvée, les champs `logical_key`, `ui_type`, `action`, `notes`, `path`, `expected_value`, `value_pattern` sont recopiés depuis l'ancien mapping — les propriétés techniques (rectangle, patterns...) restent, elles, celles du scan le plus récent.
