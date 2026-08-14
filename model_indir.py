"""
model_indir.py
--------------
Qwen 2.5 0.5B modelini bilgisayara indirir ve ardından yükler.
"""
from foundry_local_sdk import Configuration, FoundryLocalManager

print("Foundry Local başlatılıyor...")
config = Configuration(app_name="local-rag-assistant")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

modeller = manager.catalog.list_models()

hedef_model = None
for m in modeller:
    deger = getattr(m, "alias", getattr(m, "id", getattr(m, "name", "")))
    if "qwen2.5-0.5b" in str(deger).lower():
        hedef_model = m
        break

if hedef_model:
    model_adi = getattr(hedef_model, "alias", getattr(hedef_model, "id", "qwen2.5"))
    print(f"'{model_adi}' bulundu!")
    
    # Önce indirme (download) fonksiyonunu deniyoruz
    try:
        print("Model sunucudan indiriliyor (Lütfen birkaç saniye bekleyin)...")
        if hasattr(hedef_model, "download"):
            hedef_model.download()
        elif hasattr(manager.catalog, "download_model"):
            manager.catalog.download_model(hedef_model)
        print("İndirme tamamlandı! Şimdi belleğe yükleniyor...")
    except Exception as e:
        print(f"İndirme metodunda uyarı (zaten inmiş olabilir): {e}")

    # Şimdi yükleme adımına geçiyoruz
    hedef_model.load()
    print("TEBRİKLER! Model hem indirildi hem başarıyla yüklendi.")
else:
    print("HATA: Qwen 2.5 0.5B modeli katalogda bulunamadı.")