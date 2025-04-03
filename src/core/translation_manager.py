#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Author: Thomas Fischer
# Version: 0.1.0
# License: MIT
# Filename: translation_manager.py
# Pathname: /path/to/tfitpican/src/core/
# Description: Translation and localization for TFITPICAN application
# -----------------------------------------------------------------------------

import os
import json
import logging
import locale
from typing import Dict, List, Any, Optional, Set, Union

class TranslationManager:
    """Manages translations and localization for the TFITPICAN application"""
    
    def __init__(self, config_path: str = "config/config.json", sqlite_db=None):
        self.logger = logging.getLogger("TranslationManager")
        self.config = self._load_config(config_path)
        self.sqlite_db = sqlite_db
        
        # Default language
        self.default_language = "en"
        
        # Current language
        self.current_language = self._get_system_language()
        
        # Available languages
        self.available_languages = {"en"}
        
        # Translations
        self.translations = {
            "en": {}  # English is the base language
        }
        
        # Load translations from files
        self._load_translations_from_files()
        
        # Load translations from database if available
        if self.sqlite_db:
            self._load_translations_from_db()
            
        # Set the current language from config
        language_config = self.config.get("language", {})
        if "current" in language_config:
            self.set_language(language_config["current"])
            
        self.logger.info(f"Translation manager initialized with language: {self.current_language}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def _get_system_language(self) -> str:
        """Get the system language
        
        Returns:
            str: Language code (e.g., 'en', 'de')
        """
        try:
            # Try to get system locale
            lang, _ = locale.getdefaultlocale()
            if lang:
                # Extract language code (first 2 characters)
                return lang[:2].lower()
        except Exception as e:
            self.logger.warning(f"Error getting system language: {e}")
            
        # Default to English
        return "en"
    
    def _load_translations_from_files(self) -> None:
        """Load translations from JSON files in the translations directory"""
        translations_dir = "config/translations"
        
        # Ensure directory exists
        os.makedirs(translations_dir, exist_ok=True)
        
        try:
            # Look for translation files
            for filename in os.listdir(translations_dir):
                if filename.endswith(".json"):
                    language_code = os.path.splitext(filename)[0].lower()
                    
                    file_path = os.path.join(translations_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        translations = json.load(f)
                        
                    # Add to available languages
                    self.available_languages.add(language_code)
                    
                    # Store translations
                    self.translations[language_code] = translations
                    
                    self.logger.info(f"Loaded translations for language: {language_code}")
        except Exception as e:
            self.logger.error(f"Error loading translations from files: {e}")
    
    def _load_translations_from_db(self) -> None:
        """Load translations from database"""
        try:
            if self.sqlite_db:
                # Query for available languages
                languages = self.sqlite_db.query(
                    "SELECT DISTINCT language FROM translations"
                ) or []
                
                for lang_entry in languages:
                    language = lang_entry.get("language", "").lower()
                    if language:
                        # Add to available languages
                        self.available_languages.add(language)
                        
                        # Initialize translations dictionary if needed
                        if language not in self.translations:
                            self.translations[language] = {}
                        
                        # Query for translations for this language
                        translations = self.sqlite_db.query(
                            "SELECT key, value FROM translations WHERE language = ?",
                            (language,)
                        ) or []
                        
                        # Add to translations dictionary
                        for entry in translations:
                            key = entry.get("key", "")
                            value = entry.get("value", "")
                            if key:
                                self.translations[language][key] = value
                                
                        self.logger.info(f"Loaded {len(translations)} translations for language {language} from database")
        except Exception as e:
            self.logger.error(f"Error loading translations from database: {e}")
    
    def set_language(self, language: str) -> bool:
        """Set the current language
        
        Args:
            language: Language code (e.g., 'en', 'de')
            
        Returns:
            bool: True if language was set successfully
        """
        language = language.lower()
        
        # Check if language is available
        if language not in self.available_languages:
            if language.split('-')[0] in self.available_languages:
                # Try fallback to main language (e.g., 'en-US' -> 'en')
                language = language.split('-')[0]
            else:
                self.logger.warning(f"Language not available: {language}, falling back to default")
                language = self.default_language
                
        # Set current language
        self.current_language = language
        self.logger.info(f"Set current language to: {language}")
        
        return language in self.available_languages
    
    def get_string(self, key: str, default: Optional[str] = None) -> str:
        """Get a translated string
        
        Args:
            key: Translation key
            default: Default value if key not found
            
        Returns:
            str: Translated string
        """
        # Check if key exists in current language
        if self.current_language in self.translations and key in self.translations[self.current_language]:
            return self.translations[self.current_language][key]
            
        # Try default language
        if self.default_language in self.translations and key in self.translations[self.default_language]:
            return self.translations[self.default_language][key]
            
        # Use default or key as fallback
        return default if default is not None else key
    
    def add_translation(self, language: str, key: str, value: str) -> bool:
        """Add or update a translation
        
        Args:
            language: Language code
            key: Translation key
            value: Translated string
            
        Returns:
            bool: True if successful
        """
        language = language.lower()
        
        # Initialize language dictionary if needed
        if language not in self.translations:
            self.translations[language] = {}
            self.available_languages.add(language)
            
        # Update translation
        self.translations[language][key] = value
        
        # Save to database if available
        if self.sqlite_db:
            try:
                # Check if translation exists
                existing = self.sqlite_db.query(
                    "SELECT id FROM translations WHERE language = ? AND key = ?",
                    (language, key),
                    fetch_all=False
                )
                
                if existing:
                    # Update existing translation
                    self.sqlite_db.update(
                        "translations",
                        {"value": value},
                        "language = ? AND key = ?",
                        (language, key)
                    )
                else:
                    # Insert new translation
                    self.sqlite_db.insert(
                        "translations",
                        {
                            "language": language,
                            "key": key,
                            "value": value
                        }
                    )
                    
                return True
            except Exception as e:
                self.logger.error(f"Error saving translation to database: {e}")
                return False
        
        return True
    
    def delete_translation(self, language: str, key: str) -> bool:
        """Delete a translation
        
        Args:
            language: Language code
            key: Translation key
            
        Returns:
            bool: True if successful
        """
        language = language.lower()
        
        # Check if language exists
        if language not in self.translations:
            return False
            
        # Check if key exists
        if key not in self.translations[language]:
            return False
            
        # Delete translation
        del self.translations[language][key]
        
        # Delete from database if available
        if self.sqlite_db:
            try:
                self.sqlite_db.delete(
                    "translations",
                    "language = ? AND key = ?",
                    (language, key)
                )
                
                return True
            except Exception as e:
                self.logger.error(f"Error deleting translation from database: {e}")
                return False
        
        return True
    
    def save_translations_to_file(self, language: str) -> bool:
        """Save translations for a language to a JSON file
        
        Args:
            language: Language code
            
        Returns:
            bool: True if successful
        """
        language = language.lower()
        
        # Check if language exists
        if language not in self.translations:
            self.logger.warning(f"Language not available: {language}")
            return False
            
        translations_dir = "config/translations"
        
        # Ensure directory exists
        os.makedirs(translations_dir, exist_ok=True)
        
        try:
            # Save to file
            file_path = os.path.join(translations_dir, f"{language}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.translations[language], f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Saved translations for language {language} to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving translations to file: {e}")
            return False
    
    def get_available_languages(self) -> List[Dict]:
        """Get list of available languages
        
        Returns:
            List of language dictionaries with code and name
        """
        # Language codes to names mapping
        language_names = {
            "en": "English",
            "de": "Deutsch",
            "fr": "Français",
            "es": "Español",
            "it": "Italiano",
            "pt": "Português",
            "nl": "Nederlands",
            "ru": "Русский",
            "ja": "日本語",
            "zh": "中文",
            "ko": "한국어"
        }
        
        return [
            {
                "code": lang,
                "name": language_names.get(lang, lang)
            }
            for lang in sorted(self.available_languages)
        ]
    
    def get_translation_coverage(self, language: str) -> Dict:
        """Get translation coverage statistics
        
        Args:
            language: Language code
            
        Returns:
            Dictionary with coverage statistics
        """
        language = language.lower()
        
        # Check if language exists
        if language not in self.translations:
            return {
                "language": language,
                "available": False,
                "coverage": 0,
                "total": 0,
                "translated": 0
            }
            
        # Get English keys as reference
        if "en" in self.translations:
            reference_keys = set(self.translations["en"].keys())
        else:
            # If English not available, use all keys from all languages
            reference_keys = set()
            for lang, trans in self.translations.items():
                reference_keys.update(trans.keys())
                
        # Get translated keys
        translated_keys = set(self.translations[language].keys())
        
        # Calculate coverage
        total_keys = len(reference_keys)
        translated_count = len(translated_keys)
        coverage = (translated_count / total_keys) * 100 if total_keys > 0 else 0
        
        return {
            "language": language,
            "available": True,
            "coverage": coverage,
            "total": total_keys,
            "translated": translated_count,
            "missing": total_keys - translated_count
        }
    
    def create_template(self) -> Dict:
        """Create a translation template with all keys
        
        Returns:
            Dictionary with all translation keys and empty values
        """
        template = {}
        
        # Collect all keys from all languages
        all_keys = set()
        for lang, trans in self.translations.items():
            all_keys.update(trans.keys())
            
        # Create template with empty values
        for key in sorted(all_keys):
            # Use English value as template if available
            if "en" in self.translations and key in self.translations["en"]:
                template[key] = self.translations["en"][key]
            else:
                template[key] = ""
                
        return template
    
    def import_translations(self, language: str, translations: Dict[str, str]) -> int:
        """Import translations from a dictionary
        
        Args:
            language: Language code
            translations: Dictionary of translations
            
        Returns:
            int: Number of imported translations
        """
        language = language.lower()
        
        # Initialize language dictionary if needed
        if language not in self.translations:
            self.translations[language] = {}
            self.available_languages.add(language)
            
        # Count imported translations
        imported_count = 0
        
        # Import translations
        for key, value in translations.items():
            if value:  # Only import non-empty values
                self.translations[language][key] = value
                imported_count += 1
                
                # Save to database if available
                if self.sqlite_db:
                    try:
                        # Check if translation exists
                        existing = self.sqlite_db.query(
                            "SELECT id FROM translations WHERE language = ? AND key = ?",
                            (language, key),
                            fetch_all=False
                        )
                        
                        if existing:
                            # Update existing translation
                            self.sqlite_db.update(
                                "translations",
                                {"value": value},
                                "language = ? AND key = ?",
                                (language, key)
                            )
                        else:
                            # Insert new translation
                            self.sqlite_db.insert(
                                "translations",
                                {
                                    "language": language,
                                    "key": key,
                                    "value": value
                                }
                            )
                    except Exception as e:
                        self.logger.error(f"Error saving translation to database: {e}")
                        
        self.logger.info(f"Imported {imported_count} translations for language {language}")
        
        # Save to file
        self.save_translations_to_file(language)
        
        return imported_count
