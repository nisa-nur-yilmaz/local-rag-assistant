from foundry_local_sdk import Configuration, FoundryLocalManager

def main():
    
    config = Configuration(app_name="local-rag-assistant")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    
    hedef_model_id = "Phi-3.5-mini-instruct-generic-cpu:2"
    print(f"Secilen Model: {hedef_model_id} katalogda araniyor...\n")
    
    try:
        chat_model = None
        modeller = manager.catalog.list_models()
        for m in modeller:
            if m.id == hedef_model_id:
                chat_model = m
                break
                
        if chat_model is None:
            print("Hata: Model katalogda bulunamadi!")
            return
            
        print("Model basariyla bulundu!")
        
        print("\n1. Asama: Model indiriliyor...")
      
        
        chat_model.download(
            lambda p: print(f"\rIndirilme Durumu: %{p:.1f}", end="", flush=True)
        )
        
        print("\n\n2. Asama: Model bilgisayarin bellegine (RAM) yukleniyor...")
        chat_model.load()
        
        print("\n3. Asama: Soru modele iletiliyor...")
        chat_client = chat_model.get_chat_client()
        
        soru = [{"role": "user", "content": "Bana sadece tek bir cumleyle merhaba de."}]
        response = chat_client.complete_chat(soru)
        
        print("\n--- Modelin Cevabi ---")
        print(response.choices[0].message.content)
        
        
    except Exception as e:
        print(f"\nBir hata olustu: {e}")

if __name__ == "__main__":
    main()