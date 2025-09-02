import json

class Language:

    def __init__(self):
        self.language_data: dict = {}
        self.load_language_file()

    def get_translation(self, key: str):
        try:
            return self.language_data.get(key)
        except KeyError as e:
            print(f"Key {key} not found: {e}")
            return f"ERROR: translation key (\"{key}\") not found!"

    def load_language_file(self):
        """
        load the language file from settings/language/hu.json and create a new language object in 
        dict format.
        :return: dictionary containing the language data
        """

        try:
            with open('settings/language/hu.json', 'r', encoding='utf-8') as file:
                self.language_data = json.load(file)
            print("Language file loaded")
            print(self.language_data.get('data_of_entry'))
            return self.language_data
        except Exception as e:
            print(f"Error loading language file: {e}")
            return {}

    def save_language_file(self):
        """
        save the language dict obj into settings/language/hu.json
        :return:
        """
        with open('settings/language/hu.json', 'w', encoding='utf-8') as file:
            json.dump(self.language_data, file, ensure_ascii=False, indent=4)