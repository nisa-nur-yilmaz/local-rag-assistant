import sqlite3
import json
from foundry_local_sdk import Configuration, FoundryLocalManager

def main():
    print("1. SDK ve Veritabani Baglantisi Kuruluyor...")
    config = Configuration(app_name="local-rag-assistant")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    
    embedding_model_id = "qwen3-embedding-0.6b-generic-cpu:1"
    
    conn = sqlite3.connect("bilgi_bankasi.db")
    cursor = conn.cursor()
    
    try:
        print(f"2. {embedding_model_id} modeli bellege yukleniyor...")
        emb_model = None
        for m in manager.catalog.list_models():
            if m.id == embedding_model_id:
                emb_model = m
                break
                
        emb_model.load()
        emb_client = emb_model.get_embedding_client()
        
        ornek_metin = "Yapay zeka ve uretim optimizasyonu, verimliligi artirmak icin temel araclardir."
        print(f"\n3. Metin vektorlere cevriliyor:\n'{ornek_metin}'")
        
        # Bulduğumuz doğru fonksiyonu kullanıyoruz!
        response = emb_client.generate_embedding(ornek_metin)
        
        # Gelen yanıtın yapısına göre vektör listesini güvenli bir şekilde çekiyoruz
        if isinstance(response, list):
            vektor_listesi = response
        elif hasattr(response, 'data'):
            vektor_listesi = response.data[0].embedding
        elif hasattr(response, 'embedding'):
            vektor_listesi = response.embedding
        else:
            vektor_listesi = list(response) # Son çare dönüştürme
            
        vektor_metni = json.dumps(vektor_listesi)
        
        print(f"Islem basarili! {len(vektor_listesi)} boyutlu bir matematiksel vektor elde edildi.")
        
        print("\n4. Vektorler SQLite veritabanina kaydediliyor...")
        cursor.execute("INSERT INTO dokumanlar (metin, vektor) VALUES (?, ?)", (ornek_metin, vektor_metni))
        conn.commit()
        
        print("\n--- TEBRIKLER! ---")
        print("Kayit tamamlandi! Proje planindaki Faz 1 (Temeller) resmi olarak bitti.")
        
    except Exception as e:
        print(f"\nBir hata olustu: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()