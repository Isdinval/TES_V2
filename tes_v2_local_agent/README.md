# TES_V2 Local Agent (RPA) 🤖

L'Agent Local de TES_V2 est un exécuteur de processus RPA (Robotic Process Automation) intelligent. Il utilise les fichiers de mapping générés par le module **TES_V2 GUI Mapper** pour automatiser la saisie de données dans n'importe quel logiciel métier.

## 🌟 Fonctionnalités

- **Navigation Intelligente** : Suit un scénario prédéfini tout en utilisant les liens de navigation entre écrans.
- **Détection Visuelle** : Vérifie l'écran actuel via hash perceptuel (ImageHash) et template matching (OpenCV).
- **Remplissage Humain** : Mouvements de souris fluides, délais aléatoires et saisie clavier réaliste.
- **Reporting Détaillé** : Génère un rapport JSON complet de l'exécution (succès/échecs par champ).
- **Sécurité & Contrôle** :
    - **Mode Dry-Run** : Simule l'exécution sans interaction réelle.
    - **Arrêt d'Urgence** : Appuyez sur `ESC` à tout moment pour stopper l'agent.
- **Gestion des Popups** : Détecte et ferme automatiquement les popups connus.

## 🚀 Installation

### 1. Prérequis
- Python 3.11+
- Résolution d'écran identique à celle utilisée lors du mapping.

### 2. Installation des dépendances
```bash
pip install -r requirements.txt
pip install pyautogui opencv-python pydantic pandas openpyxl loguru rich imagehash mss pynput
```

## 📖 Utilisation

### Sur Windows (CMD) :
Utilisez le caractère `^` pour le retour à la ligne ou mettez tout sur une seule ligne :

```cmd
python -m tes_v2_local_agent.main ^
  --data data/source.xlsx ^
  --scenario Login,Dashboard,FicheClient ^
  --mappings mappings/ ^
  --refs reference_screenshots/ ^
  --dry-run
```

### Sur Linux / Mac / PowerShell / Git Bash :
Utilisez le caractère `\` :

```bash
python -m tes_v2_local_agent.main \
  --data data/source.xlsx \
  --scenario Login,Dashboard,FicheClient \
  --mappings mappings/ \
  --refs reference_screenshots/ \
  --dry-run
```

### Arguments principaux :
- `--data` : Chemin vers le fichier Excel ou JSON contenant les données à saisir.
- `--scenario` : Liste ordonnée des écrans à parcourir (séparés par des virgules).
- `--mappings` : Dossier contenant les fichiers JSON exportés par TES_V2.
- `--refs` : Dossier contenant les captures d'écran de référence pour la détection.
- `--dry-run` : (Recommandé pour les tests) Loggue les actions sans bouger la souris.
- `--start-from` : Nom de l'écran par lequel commencer dans le scénario.

## 📂 Structure du Projet

- `agents/` : Orchestrateur central (`LocalAgent`).
- `core/` : Moteurs d'exécution (Détection, Action, Navigation, Mapping de données).
- `models/` : Validation des données via Pydantic.
- `utils/` : Utilitaires (Arrêt d'urgence, Retries, Images).

## ⚠️ Conseils de Sécurité

1. **Testez toujours en mode `--dry-run`** avant une exécution réelle.
2. **Ne touchez pas à la souris** pendant que l'agent travaille en mode réel.
3. Gardez un œil sur la console pour voir les logs en temps réel.
4. L'agent peut être stoppé instantanément en appuyant sur la touche **Echap (ESC)**.

---
*Développé pour l'automatisation métier haute fidélité.*
