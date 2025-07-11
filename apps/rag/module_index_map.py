# Ce fichier est maintenant obsolète - remplacé par module_loader.py
# Gardé pour compatibilité temporaire

from .module_loader import module_loader

# Compatibilité avec l'ancien système
MODULE_INDEX_MAP = {
    module_key: index_file 
    for module_key, index_file in module_loader.module_index_map.items()
}
