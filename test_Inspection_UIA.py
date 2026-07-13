from pywinauto import Desktop
from pywinauto.timings import Timings
import win32api
import time
import sys

# Configuration
Timings.window_find_timeout = 15
Timings.exists_timeout = 5

print("=== Inspecteur UIA Interactif - pywinauto ===\n")
print("Instructions :")
print("   1. Survole un élément avec la souris")
print("   2. Appuie sur **Entrée** pour l'inspecter")
print("   3. Tape 'q' + Entrée pour quitter\n")

def inspect_element():
    try:
        x, y = win32api.GetCursorPos()
        print(f"\n📍 Position souris : ({x}, {y})")
        
        for backend in ["uia", "win32"]:
            try:
                desktop = Desktop(backend=backend)
                ctrl = desktop.from_point(x, y)
                
                print(f"\n{'='*80}")
                print(f"✅ RÉSULTAT - Backend: {backend.upper()}")
                print(f"{'='*80}")
                
                # Informations de base
                print(f"Name              : {ctrl.window_text()}")
                print(f"ControlType       : {ctrl.element_info.control_type}")
                print(f"ClassName         : {ctrl.class_name()}")
                print(f"FrameworkId       : {getattr(ctrl.element_info, 'framework_id', 'N/A')}")
                print(f"AutomationId      : {getattr(ctrl, 'automation_id', 'N/A')}")
                print(f"Rectangle         : {ctrl.rectangle()}")
                print(f"IsEnabled         : {ctrl.is_enabled()}")
                print(f"IsVisible         : {getattr(ctrl, 'is_visible', lambda: 'N/A')()}")
                
                # Valeur / Texte
                try:
                    print(f"Value / Text      : {ctrl.get_value() if hasattr(ctrl, 'get_value') else ctrl.window_text()}")
                except:
                    pass
                
                # Patterns supportés (très important !)
                try:
                    patterns = ctrl.supported_patterns()
                    if patterns:
                        print(f"Patterns          : {patterns}")
                    else:
                        print("Patterns          : Aucun")
                except:
                    print("Patterns          : Non disponibles")
                
                # Quelques patterns courants
                try:
                    if ctrl.has_value_pattern():
                        print(f"Value Pattern     : {ctrl.get_value()}")
                except:
                    pass
                
                print(f"{'-'*60}")
                break  # On a réussi avec un backend
                
            except Exception as e_inner:
                continue  # Essayer l'autre backend
                
    except Exception as e:
        print(f"❌ Erreur générale : {e}")

# ====================== BOUCLE PRINCIPALE ======================
while True:
    user_input = input("\nAppuie sur Entrée pour inspecter (ou 'q' pour quitter) : ").strip().lower()
    
    if user_input == 'q':
        print("Au revoir !")
        sys.exit(0)
    
    inspect_element()