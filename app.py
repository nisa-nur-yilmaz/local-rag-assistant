import streamlit as st
import gc
import time
from rag_core import (
    veritabani_hazirla, veritabanini_temizle, dosyayi_sil, yuklu_dosyalari_getir,
    veritabani_sayfalari_getir, pdf_metinlerini_cikar, parcalari_vektorlestir_ve_kaydet,
    veritabanindan_ara, baglam_metnini_olustur, modelleri_yukle, cevabi_uret
)

# --- AYARLAR ---
SAYFA_OZET_KARAKTER_LIMIT = 2000
FINAL_OZET_KARAKTER_LIMIT = 8000
# Öğrenci laptoplarında (entegre GPU/CPU) thermal throttling'i (aşırı ısınmayı) ve 
# bellek baskısını önlemek için art arda gelen yerel LLM çağrıları arasına nefes payı konuldu.
SAYFA_ARASI_BEKLEME_SN = 1.5 

st.set_page_config(page_title="Akıllı Doküman Asistanı", page_icon="🤖", layout="wide")

@st.cache_resource(show_spinner=False)
def modelleri_yukle_cached():
    yer_tutucu = st.empty()
    ilerleme_cubugu = yer_tutucu.progress(0.0, text="Yerel yapay zeka motoru hazırlanıyor...")
    sonuclar = modelleri_yukle(ilerleme_cubugu)
    yer_tutucu.empty()
    return sonuclar

# Başlangıç
st.title("🤖 Akıllı Doküman Asistanı")
st.caption("🔒 Gizlilik Odaklı & Yerel RAG Mimarisi | Katı Belge Analiz Sistemi")

veritabani_hazirla()
emb_client, chat_client, emb_alias, chat_alias, yukleme_hatasi = modelleri_yukle_cached()

if yukleme_hatasi:
    st.error(f"⚠️ Modeller yüklenemedi: {yukleme_hatasi}")
    st.stop()

# Oturum Durumu
if "mesajlar" not in st.session_state: st.session_state.mesajlar = []
if "gecmis_hafiza" not in st.session_state: st.session_state.gecmis_hafiza = []

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.header("📂 Dosya Yükleme Merkezi")
    yuklenen_pdfler = st.file_uploader("PDF ekleyin:", type="pdf", accept_multiple_files=True)
    eskyi_sil = st.checkbox("Yüklerken tüm eski hafızayı sil", value=False)

    if yuklenen_pdfler and st.button("🚀 Veritabanına İşle", use_container_width=True):
        if eskyi_sil:
            veritabanini_temizle()
            st.session_state.mesajlar = []
            st.session_state.gecmis_hafiza = []

        for yuklenen_pdf in yuklenen_pdfler:
            with st.spinner(f"📄 '{yuklenen_pdf.name}' işleniyor..."):
                dosyayi_sil(yuklenen_pdf.name)
                try:
                    sayfa_kayitlari, parca_kayitlari = pdf_metinlerini_cikar(yuklenen_pdf)
                except Exception as e:
                    st.error(f"Okuma hatası: {e}")
                    continue

                if not parca_kayitlari:
                    st.warning("Metin bulunamadı.")
                    continue

                ilerleme_cubugu = st.progress(0, text="Vektör motoru çalışıyor...")
                try:
                    parcalari_vektorlestir_ve_kaydet(emb_client, yuklenen_pdf.name, sayfa_kayitlari, parca_kayitlari, ilerleme_cubugu)
                except Exception as e:
                    st.error(f"Vektörleştirme hatası: {e}")
                finally:
                    ilerleme_cubugu.empty()

                st.session_state.aktif_dosya = yuklenen_pdf.name
                st.success(f"✅ '{yuklenen_pdf.name}' hafızaya alındı.")
        st.rerun()

    st.markdown("---")
    dosya_listesi = yuklu_dosyalari_getir()
    st.header("📚 Hafızadaki Dokümanlar")
    
    if not dosya_listesi:
        st.info("Henüz işlenmiş bir doküman yok.")
        arama_kapsami = None
    else:
        for dosya_adi, parca_sayisi in dosya_listesi:
            c1, c2 = st.columns([4, 1])
            c1.write(f"📄 {dosya_adi}\n`{parca_sayisi} parça`")
            if c2.button("🗑️", key=f"sil_{dosya_adi}"):
                dosyayi_sil(dosya_adi)
                st.rerun()

        st.markdown("---")
        secenekler = ["Tüm Dokümanlar"] + [d[0] for d in dosya_listesi]
        arama_kapsami = st.selectbox("🔎 Arama Kapsamı", secenekler)
        if arama_kapsami == "Tüm Dokümanlar": arama_kapsami = None

    with st.expander("⚙️ Gelişmiş Ayarlar"):
        top_k = st.slider("Getirilecek parça sayısı (top-k)", 1, 8, 4)
        esik = st.slider("Benzerlik eşiği", 0.0, 0.9, 0.0, 0.05)

    st.markdown("---")
    if st.button("🧹 Sohbeti Temizle", use_container_width=True):
        st.session_state.mesajlar = []
        st.session_state.gecmis_hafiza = []
        st.rerun()

    st.markdown("---")
    st.success(f"✅ Yerel LLM: {chat_alias}")
    st.success(f"✅ Vektör Motoru: {emb_alias}")

# --- ANA EKRAN SOHBET ---
for mesaj in st.session_state.mesajlar:
    with st.chat_message(mesaj["role"]):
        st.markdown(mesaj["content"])

hizli_soru = None

if len(st.session_state.mesajlar) == 0 and dosya_listesi:
    st.markdown("### 💡 Hızlı Başlangıç")
    dosya_adlari = [d[0] for d in dosya_listesi]
    varsayilan_dosya = st.session_state.get("aktif_dosya", dosya_adlari[-1])
    if varsayilan_dosya not in dosya_adlari: varsayilan_dosya = dosya_adlari[-1]

    ozet_hedefi = st.selectbox("📄 Kapsamlı özet için doküman seçin:", dosya_adlari, index=dosya_adlari.index(varsayilan_dosya)) if len(dosya_adlari) > 1 else dosya_adlari[0]

    col1, col2 = st.columns(2)
    if col1.button("📄 Kapsamlı Özet Çıkar", use_container_width=True):
        sayfalar = veritabani_sayfalari_getir(ozet_hedefi)
        sayfa_ozetleri = []
        ilerleme_cubugu = st.progress(0, text="Sayfalar özetleniyor, lütfen bekleyin...")
        toplam_sayfa = max(len(sayfalar), 1)

        for i, (sn, metin) in enumerate(sayfalar):
            if len(metin.strip()) < 50: continue
            prompt = f"Aşağıdaki metin '{ozet_hedefi}' adlı dokümanın {sn}. sayfasıdır. Bu sayfadaki ana fikirleri ve teknik kavramları özetle:\n\n{metin[:SAYFA_OZET_KARAKTER_LIMIT]}"
            try:
                ozet, _ = cevabi_uret(chat_client, [{"role": "user", "content": prompt}])
                sayfa_ozetleri.append(f"Sayfa {sn} Özeti: {ozet}")
            except Exception as e:
                print(f"Uyarı: Sayfa {sn} atlandı. Hata: {e}")

            ilerleme_cubugu.progress((i + 1) / toplam_sayfa, text=f"{sn}. sayfa özetlendi ({i + 1}/{toplam_sayfa})")
            
            # Yerel makinenin sağlığı için bellek temizliği ve nefes payı
            gc.collect()
            time.sleep(SAYFA_ARASI_BEKLEME_SN)

        ilerleme_cubugu.progress(1.0, text="Final özet oluşturuluyor...")
        birlestirilmis = "\n\n".join(sayfa_ozetleri)
        
        if len(birlestirilmis) > FINAL_OZET_KARAKTER_LIMIT:
            birlestirilmis = birlestirilmis[:FINAL_OZET_KARAKTER_LIMIT].rsplit('.', 1)[0] + "."

        final_prompt = f"Aşağıda bir belgenin sayfa sayfa özetleri var. Bunları birleştirerek tüm belgeyi kapsayan, bütünsel bir özet çıkar:\n\n{birlestirilmis}"
        
        try:
            final_ozet, _ = cevabi_uret(chat_client, [{"role": "user", "content": final_prompt}])
        except Exception:
            final_ozet = f"Model kapasitesi aşıldı. Çıkarılabilen özetler:\n\n{birlestirilmis[:3000]}..."

        ilerleme_cubugu.empty()
        kullanici_sorusu = f"Lütfen '{ozet_hedefi}' dokümanının kapsamlı bir özetini çıkar."
        st.session_state.mesajlar.extend([{"role": "user", "content": kullanici_sorusu}, {"role": "assistant", "content": final_ozet}])
        st.session_state.gecmis_hafiza.extend([{"role": "user", "content": kullanici_sorusu}, {"role": "assistant", "content": final_ozet}])
        st.rerun()

    if col2.button("🔑 Temel Kavramları Açıkla", use_container_width=True):
        hizli_soru = "Bu belgede geçen en kritik kavramları kısaca açıklar mısın?"

    col3, col4 = st.columns(2)
    if col3.button("🎯 Çalışma Soruları Üret", use_container_width=True):
        hizli_soru = "Konuyu ne kadar anladığımı test edecek 3 zorlayıcı soru hazırlar mısın?"
    if col4.button("⚙️ Süreç ve Adımları Listele", use_container_width=True):
        hizli_soru = "Bu belgedeki çözüm adımlarını, süreçleri veya algoritmaları maddeler halinde listeler misin?"

elif len(st.session_state.mesajlar) == 0:
    st.info("👋 Başlamak için soldaki panelden bir PDF yükleyin.")

# Soru-Cevap Akışı
soru = st.chat_input("Dokümanla ilgili sorunuzu buraya yazın...")
aktif_soru = soru if soru else hizli_soru

if aktif_soru:
    st.session_state.mesajlar.append({"role": "user", "content": aktif_soru})
    with st.chat_message("user"): st.markdown(aktif_soru)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Yanıt hazırlanıyor..."):
            sonuclar = veritabanindan_ara(aktif_soru, emb_client, top_k=top_k, esik=esik, dosya_filtresi=arama_kapsami)
            baglam_metni = baglam_metnini_olustur(sonuclar)

            if sonuclar:
                with st.expander("🔍 Kullanılan Kaynaklar", expanded=False):
                    for s in sonuclar:
                        st.markdown(f"**{s['dosya']} — Sayfa {s['sayfa']}** _(benzerlik: {s['skor']:.2f})_")

            sistem_talimati = (
                "Sen, yalnızca sana sağlanan [KAYNAK DOKÜMANLAR] metnini kullanarak soruları yanıtlayan, "
                "son derece kesin, mantıklı ve profesyonel bir yapay zeka asistanısın. Asla dış dünya bilgini "
                "veya genel geçer kuralları kullanma.\n\n"
                
                "GÖREVİN:\n"
                "Kullanıcının sorusunu okuduktan sonra şu KARAR AĞACINI uygula:\n\n"
                
                "1. Adım (Kontrol): Sorunun cevabı [KAYNAK DOKÜMANLAR] içinde eksiksiz ve net olarak var mı?\n\n"
                
                "2. Adım (Uygulama):\n"
                "- EĞER CEVAP VARSA: Sadece kaynak metindeki bilgileri, sayıları, formülleri ve maddeleri kullanarak net, "
                "kısa ve anlaşılır bir cevap üret. Sayısal verileri (örneğin 25.000 TL, x1 <= 40) asla değiştirme ve uydurma.\n"
                "- EĞER CEVAP YOKSA (veya yetersizse): Sadece ve tam olarak şunu yaz: 'Bu bilgi sağlanan dokümanlarda yer almıyor.' "
                "Bunun dışında hiçbir açıklama yapma, tahmin yürütme.\n\n"
                
                "KESİN KURALLAR:\n"
                "- İki durumu ('Cevap var' ve 'Cevap yok') asla aynı yanıtta karıştırma.\n"
                "- Cümlelerini kısa tut ve asla aynı kelimeyi veya cümleyi üst üste tekrar etme (Döngüye girme).\n"
                "- Yanıtlarını maddeler halinde (Bullet points) vermeye özen göster."
            )

            kullanici_mesaji = f"KAYNAK DOKÜMANLAR:\n{baglam_metni}\n\nSORU: {aktif_soru}"

            gonderilecek = [
                {"role": "system", "content": sistem_talimati},
                {"role": "user", "content": kullanici_mesaji}
            ]

            try:
                cevap, _ = cevabi_uret(chat_client, gonderilecek)
            except Exception as e:
                cevap = f"⚠️ Yanıt üretilirken hata oluştu: {e}"

            st.markdown(cevap)
            st.session_state.mesajlar.append({"role": "assistant", "content": cevap})
            st.session_state.gecmis_hafiza.extend([
                {"role": "user", "content": aktif_soru}, 
                {"role": "assistant", "content": cevap}
            ])

            if hizli_soru: 
                st.rerun()