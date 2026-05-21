from pathlib import Path
p = Path("D:/laragon/www/PythonDesktopDatabasemanage/apps/seeding/apps.py")
p.write_text("import uuid\n\nfrom django.apps import AppConfig\n\n\nclass SeedingConfig(AppConfig):\n    default_auto_field = \"django.db.models.BigAutoField\"\n    name = \"apps.seeding\"\n", encoding="utf-8")
print("Written")
