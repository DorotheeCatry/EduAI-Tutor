import json
import os
from pathlib import Path
from typing import Dict, List, Optional

class ModuleLoader:
    """
    Chargeur dynamique de modules basé sur les fichiers d'index JSON
    """
    
    def __init__(self):
        self.index_folder = Path("data/contents/index")
        self.module_index_map = self._load_module_index_map()
        self._modules_cache = {}
    
    def _load_module_index_map(self) -> Dict[str, str]:
        """
        Charge automatiquement tous les fichiers d'index disponibles
        """
        module_map = {}
        
        if not self.index_folder.exists():
            print(f"⚠️ Dossier d'index non trouvé : {self.index_folder}")
            return module_map
        
        # Scanner tous les fichiers JSON dans le dossier index
        for json_file in self.index_folder.glob("*_index.json"):
            module_name = json_file.stem.replace("_index", "")
            module_map[module_name] = json_file.name
            print(f"📚 Module détecté : {module_name} → {json_file.name}")
        
        return module_map
    
    def get_available_modules(self) -> List[Dict[str, str]]:
        """
        Retourne la liste des modules disponibles avec leurs métadonnées
        """
        modules = []
        
        for module_key, index_file in self.module_index_map.items():
            module_data = self._load_module_data(module_key)
            if module_data:
                modules.append({
                    'id': module_key,
                    'name': self._format_module_name(module_key),
                    'description': self._generate_module_description(module_data),
                    'sections_count': len(module_data),
                    'files_count': sum(len(files) for files in module_data.values())
                })
        
        # Ajouter le module "général" en premier
        modules.insert(0, {
            'id': 'general',
            'name': 'Général',
            'description': 'Questions générales tous sujets confondus',
            'sections_count': 0,
            'files_count': 0
        })
        
        return modules
    
    def _load_module_data(self, module_key: str) -> Optional[Dict]:
        """
        Charge les données d'un module depuis son fichier JSON
        """
        if module_key in self._modules_cache:
            return self._modules_cache[module_key]
        
        if module_key not in self.module_index_map:
            return None
        
        index_file = self.index_folder / self.module_index_map[module_key]
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._modules_cache[module_key] = data
                return data
        except Exception as e:
            print(f"❌ Erreur lors du chargement de {index_file}: {e}")
            return None
    
    def _format_module_name(self, module_key: str) -> str:
        """
        Formate le nom du module pour l'affichage
        """
        name_mapping = {
            'python': 'Python - Complet',
            'javascript': 'JavaScript - Complet',
            'react': 'React - Framework',
            'django': 'Django - Framework',
            'fastapi': 'FastAPI - Framework',
            'sql': 'SQL - Bases de données',
            'docker': 'Docker - Conteneurisation',
            'git': 'Git - Contrôle de version'
        }
        
        return name_mapping.get(module_key, module_key.replace('_', ' ').title())
    
    def _generate_module_description(self, module_data: Dict) -> str:
        """
        Génère une description basée sur les sections du module
        """
        sections = list(module_data.keys())
        
        if not sections:
            return "Module vide"
        
        # Prendre les 3 premières sections pour la description
        main_sections = []
        for section in sections[:3]:
            # Nettoyer le nom de section
            clean_name = section.replace('_', ' ').replace(str(section.split('_')[0]) + '_', '').title()
            main_sections.append(clean_name)
        
        description = ", ".join(main_sections)
        if len(sections) > 3:
            description += f" et {len(sections) - 3} autres sections"
        
        return description
    
    def get_module_sections(self, module_key: str) -> Dict[str, List[str]]:
        """
        Retourne les sections d'un module spécifique
        """
        return self._load_module_data(module_key) or {}
    
    def get_section_files(self, module_key: str, section_key: str) -> List[str]:
        """
        Retourne les fichiers d'une section spécifique
        """
        module_data = self._load_module_data(module_key)
        if not module_data:
            return []
        
        return module_data.get(section_key, [])
    
    def search_in_module(self, module_key: str, query: str) -> List[Dict]:
        """
        Recherche dans un module spécifique
        """
        module_data = self._load_module_data(module_key)
        if not module_data:
            return []
        
        results = []
        query_lower = query.lower()
        
        for section_key, files in module_data.items():
            # Recherche dans le nom de section
            if query_lower in section_key.lower():
                results.append({
                    'type': 'section',
                    'module': module_key,
                    'section': section_key,
                    'files': files,
                    'relevance': 'high' if query_lower == section_key.lower() else 'medium'
                })
            
            # Recherche dans les noms de fichiers
            for file in files:
                if query_lower in file.lower():
                    results.append({
                        'type': 'file',
                        'module': module_key,
                        'section': section_key,
                        'file': file,
                        'relevance': 'high' if query_lower in file.lower() else 'low'
                    })
        
        # Trier par pertinence
        results.sort(key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['relevance']], reverse=True)
        return results
    
    def reload_modules(self):
        """
        Recharge tous les modules (utile pour le développement)
        """
        self._modules_cache.clear()
        self.module_index_map = self._load_module_index_map()
        print("🔄 Modules rechargés")

# Instance globale
module_loader = ModuleLoader()