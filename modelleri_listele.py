from foundry_local_sdk import Configuration, FoundryLocalManager

# SDK'yı başlat
config = Configuration(app_name="local-rag-assistant")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

print("\n--- KULLANILABİLECEK MODELLER ---")
for m in manager.catalog.list_models():
    print(f"Model ID: {m.id}")
print("---------------------------------\n")