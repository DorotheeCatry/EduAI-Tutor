# This file is now obsolete - replaced by module_loader.py
# Kept for temporary compatibility

from .module_loader import module_loader

# Compatibility with old system
MODULE_INDEX_MAP = {
    module_key: index_file 
    for module_key, index_file in module_loader.module_index_map.items()
}
