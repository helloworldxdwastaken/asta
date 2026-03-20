#!/bin/bash

# Read all notes
memo notes > all_notes.txt

# Extract Shopping list note content
sed -n '/^99\. Shopping - Shopping list$/,/^100\./p' all_notes.txt | sed '1d;$d' > shopping_content.txt

# Read current shopping list
shopping_list=$(cat shopping_content.txt)

# Add new items to shopping list
updated_shopping="""
$shopping_list

--- New Items ---
- Fix old fridge
- Buy new fridge
- Pay Baal bait
- Pay water
""

# Update the note (this would need a proper memo CLI command)
echo "Updated Shopping List:"
echo "$updated_shopping"
