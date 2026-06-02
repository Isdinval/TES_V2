# Défis Techniques et Solutions — TES v2

Le développement de TES v2 a fait face à plusieurs problématiques liées à l'automatisation d'interfaces graphiques.

## 1. Précision du Clic vs Jitter de Détection

**Problématique** : Les modèles YOLO peuvent avoir une légère variation (quelques pixels) d'une capture à l'autre, ce qui peut faire rater un clic sur un petit bouton.
**Solution** :
- TES v2 utilise des **coordonnées relatives** (0.0 à 1.0) plutôt que des pixels fixes.
- Le système de "Stable ID" quantifie les coordonnées pour ignorer le bruit de détection et retrouver le même élément même s'il a bougé de 1 ou 2 pixels.
- Le mapping manuel des cibles de clic permet à l'humain de placer le point exactement au centre du contrôle, indépendamment de la taille de la bounding box.

## 2. Éléments UI à Choix Multiples

**Problématique** : Un groupe de boutons radio est souvent détecté comme une seule unité par l'IA. Comment cliquer sur "Homme" plutôt que "Femme" ?
**Solution** : Introduction du concept de **Choices**. Un seul élément logique peut posséder plusieurs points de clic nommés. L'agent pourra ainsi chercher l'élément `genre_radio` et cliquer sur la cible associée au label `Homme`.

## 3. Navigation Dynamique

**Problématique** : Un agent ne sait pas comment passer d'un écran A à un écran B sans aide.
**Solution** : Identification explicite des boutons de navigation. En stockant la destination dans le JSON, nous construisons implicitement un **graphe de navigation** que l'agent peut parcourir pour atteindre son objectif.

## 4. Performance de l'IA

**Problématique** : Faire tourner Florence-2 et YOLO à chaque clic serait trop lent.
**Solution** :
- La détection est asynchrone (`DetectionWorker`) pour ne pas geler l'interface.
- Les résultats sont mis en cache localement et restaurés instantanément au chargement d'un écran déjà connu.
