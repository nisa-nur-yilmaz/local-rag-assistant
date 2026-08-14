import sqlite3
import json
import numpy as np
from foundry_local_sdk import Configuration, FoundryLocalManager

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def main():
    config = Configuration(app_name="local-rag-assistant")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    
    # Modelleri dinamik olarak listeden yakalayalım
    models = manager.catalog.list_models()
    emb_model = next((m for m in models if "qwen3-embedding" in m.id), None)
    chat_model = next((m for m in models if "Phi-3.5-mini" in m.id), None)
    
    if not emb_model or not chat_model:
        print("HATA: Modeller bulunamadı!")
        return

    print("Modeller yükleniyor... Lütfen bekleyin.")
    emb_model.load()
    chat_model.load()
    
    emb_client = emb_model.get_embedding_client()
    chat_client = chat_model.get_chat_client()
    
    # Veritabanından tüm blokları bir kez çekelim
    conn = sqlite3.connect("bilgi_bankasi.db")
    cursor = conn.cursor()
    cursor.execute("SELECT metin, vektor FROM dokumanlar")
    rows = cursor.fetchall()
    conn.close()
    print(f"✅ Veritabanından {len(rows)} adet bilgi bloğu hafızaya alındı.")
    
    # HAFIZA LİSTESİ: Eski konuşmaları burada tutacağız
    sohbet_gecmisi = []
    
    print("\n" + "="*50)
    print("🤖 AKILLI RAG ASİSTANI HAZIR!")
    print("Sürekli sohbet edebilirsiniz. Çıkmak için 'q' veya 'çıkış' yazın.")
    print("="*50 + "\n")
    
    # SOHBET DÖNGÜSÜ (Sürekli çalışmasını sağlar)
    while True:
        soru = input("Sen: ")
        
        # Çıkış kontrolü
        if soru.strip().lower() in ["q", "çıkış", "exit"]:
            print("Asistandan çıkılıyor... İyi çalışmalar!")
            break
            
        if not soru.strip():
            continue
            
        # 1. Soruya en yakın bilgi bloklarını bul (Artık en iyi 2 parçayı alıyoruz)
        q_vec = emb_client.generate_embedding(soru)
        q_vec = q_vec if isinstance(q_vec, list) else q_vec.data[0].embedding
        
        benzerlikler = []
        for metin, vec_json in rows:
            vec = json.loads(vec_json)
            sim = cosine_similarity(np.array(q_vec), np.array(vec))
            benzerlikler.append((sim, metin))
            
        # Benzerliğe göre büyükten küçüğe sırala ve en iyi 2 parçayı birleştir
        benzerlikler.sort(key=lambda x: x[0], reverse=True)
        en_yakin_metin = "\n\n---\n\n".join([m[1] for m in benzerlikler[:2]])
        
        # 2. Modele gönderilecek anlık mesajı hazırla
        anlik_soru = f"Aşağıdaki teknik doküman bilgilerini bağlam olarak kullan ve soruyu yanıtla.\n\n[DOKÜMAN BİLGİSİ]:\n{en_yakin_metin}\n\n[SORU]: {soru}"
        
        # 3. Modelin kafası karışmasın diye geçmişten sadece son 4 mesajı (2 soru-cevap) alıyoruz
        gonderilecek_mesajlar = []
        gonderilecek_mesajlar.extend(sohbet_gecmisi[-4:])
        gonderilecek_mesajlar.append({"role": "user", "content": anlik_soru})
        
        print("🤖 Asistan düşünüyor...")
        response = chat_client.complete_chat(gonderilecek_mesajlar)
        cevap = response.choices[0].message.content
        
        print(f"\nAsistan: {cevap}\n")
        print("-" * 50)
        
        # 4. Bu turdaki konuşmayı (temiz haliyle) hafızaya kaydet
        sohbet_gecmisi.append({"role": "user", "content": soru})
        sohbet_gecmisi.append({"role": "assistant", "content": cevap})

if __name__ == "__main__":
    main()