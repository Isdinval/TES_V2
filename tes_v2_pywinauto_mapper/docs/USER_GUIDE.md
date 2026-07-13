# Guide d'Utilisation — UIA Mapper

Ce guide détaille la procédure complète pour produire un mapping propre et exploitable par `tes_v2_local_agent`.

## 1. Démarrage et contexte

Avant toute chose, renseignez en haut à gauche de la fenêtre :
- **App** : identifiant de l'application métier (ex. `CRM_Pro`).
- **Screen** : nom de l'écran actuellement affiché (ex. `Fiche_Client`).

*Ce couple détermine le nom du fichier d'export (`mappings/CRM_Pro_Fiche_Client.json`) et sert de clé pour restaurer un mapping déjà réalisé sur cet écran.*

## 2. Sélection de la fenêtre et scan

1. Cliquez sur **Select Window** — le curseur devient une croix.
2. Cliquez sur la fenêtre cible n'importe où à l'écran (y compris une autre application, un navigateur...).
3. Le scan démarre automatiquement : le screenshot apparaît, et les éléments détectés sont dessinés en couleur :

| Couleur du contour | Signification |
|---|---|
| 🟩 Vert | Élément détecté, pas encore mappé (`logical_key` vide) |
| 🟦 Bleu | Élément déjà mappé (`logical_key` renseigné) |
| 🟧 Orange | Groupe (radio_group, tab_bar, checkbox_group, dropdown_group) |
| 🟨 Jaune | Élément actuellement survolé par la souris |
| 🟥 Rouge | Élément actuellement sélectionné |
| 🟦 Turquoise (pointillés) | Élément dessiné manuellement, non mappé |
| 🟦 Turquoise (plein) | Élément dessiné manuellement, mappé |

> Astuce : la case **Show All** affiche également les éléments non interactifs (labels, conteneurs) — utile pour retrouver un texte servant de repère visuel, mais rend le canvas plus dense.

## 3. Mapper un élément détecté

1. Cliquez sur le contour de l'élément à mapper — le formulaire à droite se pré-remplit :
   - **Logical Key** est suggérée automatiquement (par ordre de priorité : `AutomationId` → nom normalisé sans accents/ponctuation → hash du rectangle).
   - **UI Type** est présélectionné si l'outil a pu l'inférer depuis les patterns UIA confirmés (badge affiché : *"Invoke, Value [uia_native]"*).
2. Ajustez si nécessaire la **Logical Key** (obligatoire — le champ est bordé de rouge tant qu'il est vide, le bouton "Update Element" reste désactivé).
3. Choisissez l'**Action** appropriée dans la liste, dépendante du **UI Type** sélectionné.
4. Cliquez sur **Update Element** — la sauvegarde est automatique (aucun bouton "Export" séparé n'est requis à cette étape).

## 4. Mapper un élément manquant (mode Dessin)

Si `pywinauto` n'a pas détecté un contrôle (canvas custom, widget non standard...) :

1. Cliquez sur **✏ Draw Element**.
2. Cliquez-glissez sur le screenshot pour dessiner le rectangle de l'élément.
3. Un nouvel élément `control_type: "Manual"` est créé et sélectionné automatiquement dans le formulaire.
4. Renseignez `Logical Key`, `UI Type` et `Action` comme pour un élément détecté normalement.

*Ces éléments manuels sont conservés automatiquement lors des scans suivants sur le même écran.*

## 5. Mapper un groupe de choix (radios, checkboxes, onglets, listes)

### Cas automatique
Si plusieurs `RadioButton` ou `TabItem` partagent le même parent UIA, l'outil les fusionne **automatiquement** en un seul élément orange (`radio_group` / `tab_bar`) avec la liste des options déjà pré-remplie dans le formulaire (section **Choices**).

### Cas manuel (mode Group)
Si le regroupement automatique n'a pas fonctionné (ex. options d'une liste HTML sans lien de parenté UIA explicite) :

1. Cliquez sur **Map as Group**.
2. Glissez une zone de sélection englobant au moins 2 éléments sur le screenshot.
3. L'outil détermine le type dominant parmi les éléments sélectionnés et propose un `ui_type` de groupe (`radio_group`, `checkbox_group`, `tab_bar`, `dropdown_group`) — un message dans la barre de statut vous informe du choix retenu, avec un avertissement si le type n'a pas pu être déterminé avec certitude ou si les éléments ressemblent davantage à une liste déroulante qu'à des radios (espacement régulier détecté automatiquement).
4. Renseignez la **Logical Key** du groupe et ajustez le `ui_type`/`action` si la proposition automatique ne convient pas.
5. Cliquez sur **Update Element**.

### Ajouter/retirer une option manuellement
Dans la section **Choices** du formulaire :
- **📍 Pick** : cliquez sur ce bouton puis sur le screenshot pour ajouter une option aux coordonnées exactes cliquées (le label est pré-rempli si un élément UIA est détecté sous le curseur).
- **+ Add** : ajoute une ligne vide à compléter manuellement.
- **✕** sur une ligne : supprime cette option.

## 6. Configurer le déclencheur d'un groupe (dropdown)

Pour les options qui ne sont visibles qu'après un clic d'ouverture (ex. `<select>` HTML, ComboBox Windows) :

1. Sélectionnez d'abord sur le canvas l'élément à cliquer pour ouvrir la liste (ex. le `dropdown` lui-même).
2. Sélectionnez ensuite le groupe de choix concerné dans le formulaire.
3. Cliquez sur **📌 Set trigger from selected element on canvas**.
4. Le message *"✅ Trigger set from '...'"* confirme l'association.

*Note : lors de l'export, si un groupe partage la même `logical_key` qu'un élément `ui_type: "dropdown"` et n'a pas de `trigger` explicite, l'outil résout automatiquement le trigger à partir de cet élément dropdown.*

## 7. Vérification et suppression

- **Survol** : passez la souris sur un élément pour afficher une infobulle (type, AutomationId, logical_key).
- **Suppression simple** : clic droit sur un élément pour le supprimer directement.
- **Suppression multiple** : clic droit + glisser pour sélectionner une zone — les éléments concernés sont surlignés en rouge en temps réel, avec un compteur dans la barre de statut ("Release to delete N element(s)"). Relâchez pour confirmer.
- Toute suppression déclenche une **sauvegarde automatique** du mapping.

## 8. Export final

L'export se fait automatiquement à chaque validation/suppression, mais vous pouvez forcer un export explicite à tout moment via **Save All Mappings** dans le panneau inférieur droit. Le fichier est écrit dans `mappings/<App>_<Écran>.json`.

## 9. Reprendre un mapping existant

Cliquez sur **Load Existing** (nécessite d'avoir déjà sélectionné une fenêtre) pour relancer un scan qui fusionnera automatiquement les éléments détectés avec le mapping déjà sauvegardé pour ce couple App/Écran.

## Raccourcis

| Touche | Action |
|---|---|
| `Échap` | Annule le mode actif (Draw ou Group) |
