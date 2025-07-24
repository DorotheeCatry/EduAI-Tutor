import json
import os
from pathlib import Path
from typing import Dict, List, Optional

class ModuleLoader:
    """
    Dynamic module loader based on JSON index files
    """
    
    def __init__(self):
        self.index_folder = Path("data/contents/index")
        self.module_index_map = self._load_module_index_map()
        self._modules_cache = {}
    
    def _load_module_index_map(self) -> Dict[str, str]:
        """
        Automatically loads all available index files
        """
        module_map = {}
        
        if not self.index_folder.exists():
            print(f"⚠️ Index folder not found: {self.index_folder}")
            return module_map
        
        # Scan all JSON files in index folder
        for json_file in self.index_folder.glob("*_index.json"):
            # Check that file is not empty and is valid
            try:
                if json_file.stat().st_size == 0:
                    print(f"⚠️ Empty file ignored: {json_file.name}")
                    continue
                    
                # Read test to verify JSON validity
                with open(json_file, 'r', encoding='utf-8') as f:
                    test_data = json.load(f)
                    if not test_data:  # Fichier JSON vide ou null
                        print(f"⚠️ Empty JSON file ignored: {json_file.name}")
                        continue
                        
            except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
                print(f"❌ Invalid JSON file ignored {json_file.name}: {e}")
                continue
            except Exception as e:
                print(f"❌ Error checking {json_file.name}: {e}")
                continue
                
            module_name = json_file.stem.replace("_index", "")
            module_map[module_name] = json_file.name
            print(f"📚 Module detected: {module_name} → {json_file.name}")
        
        return module_map
    
    def get_available_modules(self) -> List[Dict[str, str]]:
        """
        Returns list of available modules with their metadata
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
        
        # Add "general" module first
        modules.insert(0, {
            'id': 'general',
            'name': 'General',
            'description': 'General questions on all topics',
            'sections_count': 0,
            'files_count': 0
        })
        
        return modules
    
    def _load_module_data(self, module_key: str) -> Optional[Dict]:
        """
        Loads module data from its JSON file
        """
        if module_key in self._modules_cache:
            return self._modules_cache[module_key]
        
        if module_key not in self.module_index_map:
            return None
        
        index_file = self.index_folder / self.module_index_map[module_key]
        
        try:
            # Check that file exists and is not empty
            if not index_file.exists():
                print(f"❌ Index file not found: {index_file}")
                return None
                
            if index_file.stat().st_size == 0:
                print(f"❌ Empty index file: {index_file}")
                return None
                
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data:
                    print(f"❌ Empty JSON data in: {index_file}")
                    return None
                self._modules_cache[module_key] = data
                return data
        except Exception as e:
            print(f"❌ Error loading {index_file}: {e}")
            return None
    
    def _format_module_name(self, module_key: str) -> str:
        """
        Formats module name for display
        """
        name_mapping = {
            'python': 'Python - Complete',
            'javascript': 'JavaScript - Complete',
            'react': 'React - Framework',
            'django': 'Django - Framework',
            'fastapi': 'FastAPI - Framework',
            'sql': 'SQL - Databases',
            'docker': 'Docker - Containerization',
            'git': 'Git - Version Control'
        }
        
        return name_mapping.get(module_key, module_key.replace('_', ' ').title())
    
    def _generate_module_description(self, module_data: Dict) -> str:
        """
        Generates description based on module sections
        """
        sections = list(module_data.keys())
        
        if not sections:
            return "Empty module"
        
        # Take first 3 sections for description
        main_sections = []
        for section in sections[:3]:
            # Clean section name
            clean_name = section.replace('_', ' ').replace(str(section.split('_')[0]) + '_', '').title()
            main_sections.append(clean_name)
        
        description = ", ".join(main_sections)
        if len(sections) > 3:
            description += f" and {len(sections) - 3} other sections"
        
        return description
    
    def get_module_sections(self, module_key: str) -> Dict[str, List[str]]:
        """
        Returns sections of a specific module
        """
        return self._load_module_data(module_key) or {}
    
    def get_section_files(self, module_key: str, section_key: str) -> List[str]:
        """
        Returns files of a specific section
        """
        module_data = self._load_module_data(module_key)
        if not module_data:
            return []
        
        return module_data.get(section_key, [])
    
    def search_in_module(self, module_key: str, query: str) -> List[Dict]:
        """
        Search in a specific module
        """
        module_data = self._load_module_data(module_key)
        if not module_data:
            return []
        
        results = []
        query_lower = query.lower()
        
        for section_key, files in module_data.items():
            # Search in section name
            if query_lower in section_key.lower():
                results.append({
                    'type': 'section',
                    'module': module_key,
                    'section': section_key,
                    'files': files,
                    'relevance': 'high' if query_lower == section_key.lower() else 'medium'
                })
            
            # Search in file names
            for file in files:
                if query_lower in file.lower():
                    results.append({
                        'type': 'file',
                        'module': module_key,
                        'section': section_key,
                        'file': file,
                        'relevance': 'high' if query_lower in file.lower() else 'low'
                    })
        
        # Sort by relevance
        results.sort(key=lambda x: {'high': 3, 'medium': 2, 'low': 1}[x['relevance']], reverse=True)
        return results
    
    def reload_modules(self):
        """
        Reload all modules (useful for development)
        """
        self._modules_cache.clear()
        self.module_index_map = self._load_module_index_map()
        print("🔄 Modules reloaded")

# Global instance
module_loader = ModuleLoader()