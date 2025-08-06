from modules.language import Language

# Create an instance of the Language class
lang = Language()

# Call the load_language_file method
language_data = lang.load_language_file()

# Print the loaded language data
print("Loaded language data:")
print(language_data)

# Verify that the title is correctly loaded
if "title" in language_data:
    print(f"\nTitle: {language_data['title']}")
else:
    print("\nTitle not found in language data")