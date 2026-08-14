import sqlite3

def main():
    print("SQLite Veritabani Kurulumu Basliyor...")
    
    # 'bilgi_bankasi.db' adında yerel bir dosya oluşturur (dosya yoksa sıfırdan yaratır)
    conn = sqlite3.connect("bilgi_bankasi.db")
    cursor = conn.cursor()
    
    # Dokümanları ve onların matematiksel vektörlerini tutacağımız tabloyu oluşturuyoruz
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dokumanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metin TEXT NOT NULL,
            vektor TEXT NOT NULL
        )
    ''')
    
    # Değişiklikleri kaydedip veritabanını kapatıyoruz
    conn.commit()
    conn.close()
    
    print("Harika! 'bilgi_bankasi.db' basariyla olusturuldu ve 'dokumanlar' tablosu hazir!")

if __name__ == "__main__":
    main()