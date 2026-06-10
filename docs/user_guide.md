# Guide d'Utilisation — TES v2

Ce guide détaille les procédures pour effectuer un mapping complet et précis.

## 1. Démarrage et Contexte

Avant de capturer l'écran, vous **devez** définir le contexte :
- **App** : Identifiant unique de l'application métier (ex: `orthokis`).
- **Écran** : Nom de la vue actuelle (ex: `fiche_patient`).
*Note : Le store de corrections utilise cette paire pour restaurer vos travaux précédents.*

## 2. Capture et Détection

1. Cliquez sur **📸 Capturer**. L'image du moniteur sélectionné apparaît.
2. Si des éléments ont déjà été mappés pour cet écran, ils apparaissent avec des contours **verts**.
3. Cliquez sur **🔍 Détecter** pour lancer l'IA. Les suggestions apparaissent avec un contour jaune.

## 3. Création d'un Élément

### Méthode A : Utiliser une suggestion
Cliquez sur une boîte jaune. Le formulaire se remplit avec les coordonnées et une description automatique.

### Méthode B : Dessin manuel
Si l'IA a manqué un élément, cliquez et faites glisser sur le canvas pour dessiner votre propre boîte (en orange pendant le dessin).

## 4. Configuration avancée

### Éléments Scrollables (Multi-choix complexes)
Pour mapper une liste de checkboxes ou radios contenue dans une zone scrollable :
1. **Initialisation** : Sélectionnez le type (ex: `checkbox`) et cochez **"Cet élément nécessite un scroll"**.
2. **Zone de scroll** : Cliquez sur **📁 Zone de scroll** et dessinez une boîte englobant toute la zone de défilement sur le screenshot. Elle apparaîtra en bleu/pointillés.
3. **Scrollbar (Optionnel)** : Cliquez sur **🖱 Scrollbar** et cliquez sur le point central de la barre de défilement (ou la flèche bas).
4. **Mapping des labels** : Ajoutez tous les labels de votre liste (visibles ET invisibles) avec le bouton `+`.
5. **Sampling des cibles** :
   - Activez **🎯 Enregistrer les points de clic**.
   - **Pour les items visibles** : Cliquez directement sur leur cible. Le `Scroll Step` reste à 0.
   - **Pour les items invisibles** :
     1. Dans l'application réelle, scrollez pour faire apparaître l'item.
     2. Dans TES_V2, ajustez le compteur avec le bouton **+1** (indiquant qu'un scroll a eu lieu).
     3. Cliquez sur la position de l'item sur le screenshot (même si l'image TES n'a pas bougé, l'agent saura qu'il doit scroller avant de cliquer à cet endroit).
     4. Répétez pour chaque niveau de scroll nécessaire.

### Boutons de Navigation
Si le bouton permet de changer de page :
1. Sélectionnez le bouton.
2. Cochez **"Bouton de changement de fiche"**.
3. Choisissez ou saisissez la fiche de destination.

## 5. Vérification et Export

- **Visualisation** : Les petits cercles jaunes indiquent les cibles. Si un chiffre blanc est à côté du point, il représente le nombre de scrolls nécessaires.
- **Tooltip** : Passez la souris sur un élément vert pour voir sa `logical_key`.
- **Export** : Une fois terminé, cliquez sur **💾 Exporter JSON**.
