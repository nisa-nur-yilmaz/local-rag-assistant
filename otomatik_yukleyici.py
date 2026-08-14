import os
import sqlite3
import json
from pypdf import PdfReader
from foundry_local_sdk import Configuration, FoundryLocalManager

def veritabani_hazirla():
    conn = sqlite3.connect("bilgi_bankasi.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dokumanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metin TEXT,
            vektor TEXT
        )
    """)
    conn.commit()
    return conn

def pdf_metin_oku(dosya_yolu):
    reader = PdfReader(dosya_yolu)
    tam_metin = ""
    for sayfa in reader.pages:
        metin = sayfa.extract_text()
        if metin:
            tam_metin += metin + " "
    return tam_metin

def metni_parcalara_bol(metin, parca_boyutu=800):
    kelimeler = metin.split()
    parcalar = []
    mevcut_parca = []
    mevcut_uzunluk = 0
    
    for kelime in kelimeler:
        mevcut_uzunluk += len(kelime) + 1
        if mevcut_uzunluk > parca_boyutu:
            parcalar.append(" ".join(mevcut_parca))
            mevcut_parca = [kelime]
            mevcut_uzunluk = len(kelime)
        else:
            mevcut_parca.append(kelime)
            
    if mevcut_parca:
        parcalar.append(" ".join(mevcut_parca))
    return parcalar

def main():
    pdf_klasoru = "pdf_havuzu"
    
    if not os.path.exists(pdf_klasoru):
        os.makedirs(pdf_klasoru)
        print(f"'{pdf_klasoru}' klasörü oluşturuldu. Lütfen içine PDF ekleyip tekrar çalıştır.")
        return

    pdf_dosyalari = [f for f in os.listdir(pdf_klasoru) if f.endswith(".pdf")]
    
    if not pdf_dosyalari:
        print(f"'{pdf_klasoru}' klasöründe hiç PDF bulunamadı!")
        return

    print("Model başlatılıyor...")
    config = Configuration(app_name="local-rag-assistant")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    
    emb_id = "qwen3-embedding-0.6b-generic-cpu:4"
    
    models = manager.catalog.list_models()
    emb_model = next((m for m in models if "qwen3-embedding" in m.id), None)
    
    if not emb_model:
        print("HATA:Embedding modeli bulunamadı!")
        return

    emb_model.load()
    emb_client = emb_model.get_embedding_client()
    
    conn = veritabani_hazirla()
    cursor = conn.cursor()
    
    toplam_parca = 0
    print(f"\nToplam {len(pdf_dosyalari)} adet PDF işlenecek...\n")
    
    for dosya_adi in pdf_dosyalari:
        dosya_yolu = os.path.join(pdf_klasoru, dosya_adi)
        print(f"-> Okunuyor: {dosya_adi}")
        
        metin = pdf_metin_oku(dosya_yolu)
        parcalar = metni_parcalara_bol(metin)
        
        print(f"   {len(parcalar)} bilgi parçasına bölündü. Vektörler hesaplanıyor...")
        
        for parca in parcalar:
            vec = emb_client.generate_embedding(parca)
            vec_data = vec if isinstance(vec, list) else vec.data[0].embedding
            
            cursor.execute("INSERT INTO dokumanlar (metin, vektor) VALUES (?, ?)", 
                           (parca, json.dumps(vec_data)))
            toplam_parca += 1
            
    conn.commit()
    conn.close()
    print(f"\n İŞLEM TAMAMLANDI! Toplam {toplam_parca} yeni bilgi parçası veritabanına başarıyla eklendi.")

if __name__ == "__main__":
    main()