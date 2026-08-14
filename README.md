# Akıllı Doküman Asistanı (Local RAG)

Merhaba! Bu projede, verileri buluta göndermeden tamamen yerel bilgisayar donanımında çalışan, gizlilik odaklı bir RAG (Retrieval-Augmented Generation) masaüstü asistanı geliştirdim. 

Amacım, kurumsal veya kişisel PDF dokümanlarını dışarıdaki yapay zeka servislerine yüklemeden, kendi cihazımızda güvenle sorgulayabileceğimiz bir sistem kurmaktı.

# Neler Yaptım?

- Sıfır Halüsinasyon (Uydurma Koruması): Modelin `temperature` değerini 0.3'te tutarak deterministik çıktılar almasını sağladım. Ayrıca sisteme katı bir prompt vererek, aranan cevap dokümanda yoksa modelin uydurmasını yasakladım; doğrudan "Bu bilgi dokümanda yer almıyor" yanıtını veriyor.
- Hassas Chunking (Regex ile): PDF'leri parçalarken "Dr.", "Prof." gibi noktalı kısaltmaların cümleleri yanlış bölmesini engellemek için özel bir Regex kuralı yazdım. Metinleri bağlamı kopmadan 800 karakterlik parçalara bölüp, aralarında 1 cümlelik örtüşme (overlap) bıraktım.
- Hafif Veritabanı Mimarisi: Ağır vektör veritabanları kurmak yerine, elde ettiğim vektörleri JSON formatına dönüştürüp SQLite tablolarında (`parcalar` ve `sayfalar`) kalıcı olarak sakladım.
- Performans ve Isınma Kontrolü: Uygulamanın standart öğrenci bilgisayarlarında da çökmeden çalışabilmesi için LLM çağrıları arasına 1.5 saniyelik `time.sleep` ekledim ve `gc.collect()` ile düzenli RAM temizliği yaptırdım (Thermal throttling'i önlemek için).
- Arama Optimizasyonu: Numpy matris çarpımları ile kosinüs benzerliği hesaplıyorum. Ayrıca aynı dosyalardaki aramaları hızlandırmak için vektörleri RAM'de önbellekleyen (cache) bir yapı kurdum. Arayüz üzerinden getirilecek parça sayısını (Top-K) ve benzerlik eşiğini ayarlayabiliyorsunuz.

# Kullanılan Teknolojiler

- Dil: Python
- Arayüz: Streamlit
- Veritabanı: SQLite
- Doküman İşleme: PyMuPDF (`fitz`), Numpy, Regex
- Yapay Zeka Modelleri (Microsoft Foundry Local): 
  - Vektörleştirme için: `qwen3-embedding`
  - Soru-Cevap için: `phi-3.5-mini`

# Nasıl Çalıştırılır?

Projeyi kendi bilgisayarınızda çalıştırmak için:

1. Depoyu klonlayın:
   ```bash
   git clone [https://github.com/nisa-nur-yilmaz/local-rag-assistant.git](https://github.com/nisa-nur-yilmaz/local-rag-assistant.git)
   cd local-rag-assistant
Gerekli kütüphaneleri yükleyin:

 ```bash
pip install -r requirements.txt
-Not: Sistemde Microsoft Foundry Local SDK'nın kurulu ve açık olması gerekir.

Uygulamayı başlatın:

 ```bash
streamlit run app.py
Geliştirici: Nisa Nur Yılmaz
