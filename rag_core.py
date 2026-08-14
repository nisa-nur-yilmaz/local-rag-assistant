"""
rag_core.py - Microsoft Roadmap Uyumlu Genel Amaçlı RAG Pipeline
"""
import json
import sqlite3
import numpy as np
import pymupdf as fitz  # AGPL lisanslı, bellek sızıntısını önlemek için 'with' kullanılacak
import re
from foundry_local_sdk import Configuration, FoundryLocalManager

DB_YOLU = "bilgi_bankasi.db"
UYGULAMA_ADI = "local-rag-assistant"

# ==============================================================================
# CACHE (ÖNBELLEK) YÖNETİMİ
# ==============================================================================
_vektor_onbellek = {}

def _cache_temizle():
    global _vektor_onbellek
    _vektor_onbellek.clear()

# ==============================================================================
# MODEL YÜKLEME
# ==============================================================================
def _model_bul(modeller, anahtar_kelime):
    anahtar_kelime = anahtar_kelime.lower()
    for m in modeller:
        for ozellik in ("alias", "id", "name"):
            deger = getattr(m, ozellik, None)
            if deger and anahtar_kelime in str(deger).lower():
                return m
    return None

def modelleri_yukle(_ilerleme_cubugu):
    try:
        config = Configuration(app_name=UYGULAMA_ADI)
        FoundryLocalManager.initialize(config)
        manager = FoundryLocalManager.instance
        modeller = manager.catalog.list_models()
    except Exception as e:
        return None, None, None, None, f"Foundry Local servisine bağlanılamadı: {e}"

    emb_model = _model_bul(modeller, "qwen3-embedding")
    chat_model = _model_bul(modeller, "phi-3.5-mini")

    eksikler = []
    if not emb_model: eksikler.append("embedding modeli (qwen3-embedding)")
    if not chat_model: eksikler.append("sohbet modeli (phi-3.5-mini)")
    if eksikler:
        return None, None, None, None, "Eksik modeller: " + ", ".join(eksikler)

    emb_alias = str(getattr(emb_model, "alias", getattr(emb_model, "id", "embedding")))
    chat_alias = str(getattr(chat_model, "alias", getattr(chat_model, "id", "chat")))

    try:
        _ilerleme_cubugu.progress(0.10, text=f"'{emb_alias}' hazırlanıyor...")
        emb_model.load()
        
        _ilerleme_cubugu.progress(0.50, text=f"'{chat_alias}' hazırlanıyor...")
        chat_model.load()
        
        _ilerleme_cubugu.progress(1.0, text="Modeller hazır!")
    except Exception as e:
        return None, None, None, None, f"Model yükleme hatası: {e}"

    return emb_model.get_embedding_client(), chat_model.get_chat_client(), emb_alias, chat_alias, None

def cevabi_uret(chat_client, mesajlar):
    try:
        secenekler = {
            "temperature": 0.3,
            "repetition_penalty": 1.15,
            "max_tokens": 512
        }
        try:
            yanit = chat_client.complete_chat(mesajlar, **secenekler)
        except TypeError:
            yanit = chat_client.complete_chat(mesajlar)
            
        return yanit.choices[0].message.content, yanit
    except Exception as e:
        raise RuntimeError(f"Model yanıt üretirken hata oluştu: {e}")

# ==============================================================================
# VERİTABANI VE DOSYA YÖNETİMİ
# ==============================================================================
def veritabani_baglan():
    return sqlite3.connect(DB_YOLU, check_same_thread=False)

def veritabani_hazirla():
    with veritabani_baglan() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parcalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dosya_adi TEXT NOT NULL,
                sayfa_no INTEGER,
                metin TEXT NOT NULL,
                vektor TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sayfalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dosya_adi TEXT NOT NULL,
                sayfa_no INTEGER NOT NULL,
                metin TEXT NOT NULL
            )
        """)
        conn.commit()

def veritabanini_temizle():
    _cache_temizle()
    with veritabani_baglan() as conn:
        conn.execute("DELETE FROM parcalar")
        conn.execute("DELETE FROM sayfalar")
        conn.commit()

def dosyayi_sil(dosya_adi):
    _cache_temizle()
    with veritabani_baglan() as conn:
        conn.execute("DELETE FROM parcalar WHERE dosya_adi = ?", (dosya_adi,))
        conn.execute("DELETE FROM sayfalar WHERE dosya_adi = ?", (dosya_adi,))
        conn.commit()

def yuklu_dosyalari_getir():
    with veritabani_baglan() as conn:
        satirlar = conn.execute("SELECT dosya_adi, COUNT(*) FROM parcalar GROUP BY dosya_adi ORDER BY dosya_adi").fetchall()
    return satirlar

def veritabani_sayfalari_getir(dosya_adi):
    with veritabani_baglan() as conn:
        satirlar = conn.execute("SELECT sayfa_no, metin FROM sayfalar WHERE dosya_adi = ? ORDER BY sayfa_no", (dosya_adi,)).fetchall()
    return satirlar

# ==============================================================================
# PDF OKUMA VE PARÇALAMA (Akıllı Regex ve Cümle Bazlı)
# ==============================================================================
def metni_parcala(metin, chunk_size=800, overlap_sentences=1):
    # Kullanıcı testinden geçmiş, noktaları da lookbehind'a dahil eden kusursuz regex:
    cumleler = re.split(r'(?<!\bDr\.)(?<!\bProf\.)(?<!\bAssoc\.)(?<!\bSay\.)(?<!\bNo\.)(?<=[.?!])\s+(?=[A-ZÇÖŞİĞÜ])', metin)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for cumle in cumleler:
        cumle = cumle.strip()
        if not cumle: continue
        
        if current_length + len(cumle) <= chunk_size:
            current_chunk.append(cumle)
            current_length += len(cumle) + 1
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            
            if overlap_sentences > 0 and len(current_chunk) >= overlap_sentences:
                current_chunk = current_chunk[-overlap_sentences:] + [cumle]
            else:
                current_chunk = [cumle]
            current_length = sum(len(c) + 1 for c in current_chunk)
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks if chunks else [metin]

def pdf_metinlerini_cikar(yuklenen_pdf):
    pdf_bytes = yuklenen_pdf.read()
    sayfa_kayitlari, parca_kayitlari = [], []
    
    # 'with' context manager kullanılarak C seviyesinde memory leak (bellek sızıntısı) önlendi.
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, sayfa in enumerate(doc, start=1):
            try:
                metin = sayfa.get_text("text").strip()
            except Exception as e:
                print(f"Uyarı: {i}. sayfa okunamadı. Hata: {e}")
                continue # Hatalı sayfayı atla, dokümanın geri kalanını kurtar
                
            if not metin: continue
            sayfa_kayitlari.append((i, metin))
            for parca in metni_parcala(metin):
                parca_kayitlari.append((i, parca))
            
    return sayfa_kayitlari, parca_kayitlari

def parcalari_vektorlestir_ve_kaydet(emb_client, dosya_adi, sayfa_kayitlari, parca_kayitlari, ilerleme_cubugu):
    _cache_temizle()
    with veritabani_baglan() as conn:
        for sn, metin in sayfa_kayitlari:
            conn.execute("INSERT INTO sayfalar (dosya_adi, sayfa_no, metin) VALUES (?, ?, ?)", (dosya_adi, sn, metin))
        conn.commit()

        toplam = len(parca_kayitlari)
        if toplam == 0: return

        batch_size = 16
        for basi in range(0, toplam, batch_size):
            grup = parca_kayitlari[basi: basi + batch_size]
            metinler = [m for _, m in grup]

            try:
                yanit = emb_client.generate_embeddings(metinler)
                vektorler = [d.embedding for d in yanit.data]
            except AttributeError:
                vektorler = []
                for m in metinler:
                    v = emb_client.generate_embedding(m)
                    vektorler.append(v if isinstance(v, list) else v.data[0].embedding)

            for (sn, metin), vektor in zip(grup, vektorler):
                conn.execute(
                    "INSERT INTO parcalar (dosya_adi, sayfa_no, metin, vektor) VALUES (?, ?, ?, ?)",
                    (dosya_adi, sn, metin, json.dumps(vektor)),
                )
            conn.commit()
            islenen = min(basi + batch_size, toplam)
            ilerleme_cubugu.progress(islenen / toplam, text=f"Vektörleştirilen parça: {islenen}/{toplam}")

# ==============================================================================
# ARAMA MOTORU (Önbellekleme)
# ==============================================================================
def veritabanindan_ara(soru, emb_client, top_k=4, esik=0.0, dosya_filtresi=None):
    global _vektor_onbellek
    
    q_vec = emb_client.generate_embedding(soru)
    q_vec = q_vec if isinstance(q_vec, list) else q_vec.data[0].embedding
    q_vec_np = np.array(q_vec)

    cache_key = dosya_filtresi or "TUM_DOSYALAR"
    
    if cache_key not in _vektor_onbellek:
        with veritabani_baglan() as conn:
            if dosya_filtresi:
                satirlar = conn.execute("SELECT dosya_adi, sayfa_no, metin, vektor FROM parcalar WHERE dosya_adi = ?", (dosya_filtresi,)).fetchall()
            else:
                satirlar = conn.execute("SELECT dosya_adi, sayfa_no, metin, vektor FROM parcalar").fetchall()
                
        if not satirlar: return []
        
        dosyalar = [s[0] for s in satirlar]
        sayfalar = [s[1] for s in satirlar]
        metinler = [s[2] for s in satirlar]
        matris = np.array([json.loads(s[3]) for s in satirlar]) 
        _vektor_onbellek[cache_key] = (dosyalar, sayfalar, metinler, matris)

    dosyalar, sayfalar, metinler, matris = _vektor_onbellek[cache_key]

    dot = np.dot(matris, q_vec_np)
    normlar = np.linalg.norm(matris, axis=1) * np.linalg.norm(q_vec_np)
    benzerlikler = dot / np.maximum(normlar, 1e-10)

    sirali_indeksler = np.argsort(benzerlikler)[::-1]
    
    sonuclar = []
    for idx in sirali_indeksler:
        if len(sonuclar) >= top_k: break
        if benzerlikler[idx] < esik: continue
        sonuclar.append({
            "dosya": dosyalar[idx], "sayfa": sayfalar[idx], "metin": metinler[idx], "skor": float(benzerlikler[idx])
        })
    return sonuclar

def baglam_metnini_olustur(sonuclar):
    return "\n\n---\n\n".join([f"[Kaynak: {s['dosya']} - Sayfa {s['sayfa']}]\n{s['metin']}" for s in sonuclar])