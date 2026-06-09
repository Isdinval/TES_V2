# Guide d'Utilisation — TES v2

Ce guide détaille les procédures pour effectuer un mapping complet et précis.

## 1. Démarrage et Contexte

Avant de capturer l'écran, vous **devez** définir le contexte :
- **App** : Identifiant unique de l'application métier (ex: `orthokis`).
- **Écran** : Nom de la vue actuelle (ex: `fiche_patient`).
*Note : Le store de corrections utilise cette paire pour restaurer vos travaux précédents.*

## 2. Capture et Détection

1. Cliquez sur **📸 Capturer**. L'image du moniteur sélectionné apparaît.
2. Si des éléments ont déjà été mappés pour cet écran, ils apparaissent avec des contours **verts** (standard) ou **oranges** (navigation).
3. Cliquez sur **🔍 Détecter** pour lancer l'IA. Les suggestions apparaissent en **bleu**.

## 3. Création d'un Élément

### Méthode A : Utiliser une suggestion
Cliquez sur une boîte bleue. Le formulaire se remplit avec les coordonnées et une description automatique.

### Méthode B : Dessin manuel
Si l'IA a manqué un élément, cliquez et faites glisser sur le canvas pour dessiner votre propre boîte (en rouge pendant le dessin).

## 4. Configuration avancée

### Boutons de Navigation
Si le bouton permet de changer de page :
1. Sélectionnez le bouton.
2. Cochez **"Bouton de changement de fiche"**.
3. Choisissez ou saisissez la fiche de destination.

### Groupes de Choix (Radios / Checkboxes)
Pour mapper un groupe d'options dans une seule boîte :
1. Saisissez les labels des options dans le champ dédié et cliquez sur `+`.
2. Activez le mode **🎯 Enregistrer les points de clic**.
3. Cliquez sur chaque option physique sur le screenshot dans l'ordre de votre liste. Des points jaunes apparaîtront.

## 5. Vérification et Export

- **Visualisation** : Les petits cercles jaunes indiquent où l'agent cliquera. Vérifiez qu'ils tombent bien sur les contrôles.
- **Tooltip** : Passez la souris sur un élément vert pour voir sa `logical_key`.
- **Suppression** : Utilisez la croix rouge dans le tableau en bas pour retirer un élément.
- **Export** : Une fois terminé, cliquez sur **💾 Exporter JSON**.
