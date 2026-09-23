# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- `pytapo` yerine, Home Assistant'ın resmi **TP-Link Smart Home** entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır.
- Kameraya resmi TP-Link entegrasyonunun bağlandığı gibi bağlanır.
- Resmi entegrasyonda olmayan otomatik alarm ve bildirim anahtarlarını ekler.

C520WS ve C510W için yazıldı. `msg_alarm` destekleyen diğer Tapo kameralarda da çalışmalı.

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki "Alarm" anahtarı) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |

- Ses veya ışıktan en az biri açık kalmalıdır; kamera bunu zorunlu tutar.
- Varlık kimlikleri Home Assistant'ın diline göre oluşur. Örneğin İngilizce kurulumda `switch.<kamera>_alarm_sound` olur.
- Kamera bildirim ayarını bildirmiyorsa Bildirimler anahtarı eklenmez.

## Kurulum (HACS)
1. HACS → Integrations → sağ üst menü → **Custom repositories**
2. Depo: `https://github.com/ibrahimdoqn/TapoKamera`, kategori: **Integration**
3. **Kasa Camera Control** kurun ve Home Assistant'ı yeniden başlatın.
4. Ayarlar → Cihazlar ve Hizmetler → **Entegrasyon ekle** → *Kasa Camera Control*
5. Kameranın IP adresi ile **TP-Link bulut hesabınızın e-posta ve şifresini** girin. Tapo uygulamasında ve resmi TP-Link entegrasyonunda kullandığınız hesap budur, kamera hesabı (RTSP kullanıcı adı) değil.
6. Her kamera için 4. ve 5. adımları tekrarlayın.

> Kameralara sabit IP (DHCP rezervasyonu) vermeniz önerilir. IP değişirse entegrasyon kamerayı yine bulur, ama bu birkaç dakika sürebilir.
>
> Eski `tapo_control` kurulumunu kaldırın. Aynı kameraya iki entegrasyonun birlikte bağlanması kameraya yük bindirir.

## Güncelleme
1. HACS'ta **Kasa Camera Control** sayfasından yeni sürümü indirin.
2. Home Assistant'ı yeniden başlatın.

Kameraları yeniden eklemeniz gerekmez. Artık kullanılmayan varlıklar (eski Siren ve Zengin bildirimler) ilk açılışta otomatik silinir.

## Seçenekler
Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera → **Yapılandır**

- **Sorgulama aralığı (saniye):** Varsayılan 60, en az 15. Değişiklik kameraya yeniden bağlanmadan uygulanır.

## Otomasyon örneği
```yaml
automation:
  - alias: Evden çıkınca alarmı aç
    triggers:
      - trigger: state
        entity_id: group.aile
        to: not_home
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.bahce_alarm
```

## Nasıl çalışıyor

### Kamerayı yormamak için
- Kamera başına **tek oturum** açık tutulur. Her sorguda yeniden giriş yapılmaz.
- İstekler sırayla gönderilir, kameraya aynı anda asla iki istek gitmez.
- Her sorgulamada yalnızca alarm ve bildirim ayarı, tek bir istekte okunur.
- Görüntü akışı, ONVIF, anlık görüntü, olay dinleme ve güncelleme kontrolü **yoktur**.

### Sorgulama
- Varsayılan olarak 60 saniyede bir sorgu yapılır.
- Her sorguda kameraya tek bir HTTPS isteği gider. Alarm ayarı ve bildirim ayarı bu isteğin içinde birlikte okunur.
- İki sorgu arasında kameraya hiçbir istek gitmez.

### Sıralama ve bekleme
- Her kamera için bir kilit vardır. Bir istek bitmeden aynı kameraya ikinci istek başlamaz.
- Sorgulama sürerken bir anahtara basılırsa, yazma isteği sorgulamanın bitmesini bekler, sonra gider.
- Home Assistant bir sorgu bitmeden yenisini başlatmaz.
- Normal çalışmada yapay bir bekleme yoktur.
- Her kameranın kendi zamanlayıcısı ve kilidi vardır. Kameralar birbirini beklemez, ama her biri kendi içinde sıralı çalışır.

### Anahtara basınca
- Tek bir yazma isteği gider.
- Yazmadan sonra ayrıca okuma yapılmaz. Yeni durum doğrudan yazılan değerden yansır ve sıradaki sorgu zamanı baştan sayılır.

### İlk açılışta
- Kamera modeline ve yazılımına göre alarm ayarı farklı komutlarla okunur (`getLastAlarmInfo`, `getAlertConfig`, `getAlarmConfig`).
- Hangisinin desteklendiği bilinmiyorsa bu üç komut sırayla, birer istek olarak denenir. Çalışan komut hatırlanır, sonraki sorgular yalnızca onu kullanır.
- Bu deneme Home Assistant her açıldığında veya entegrasyon yeniden yüklendiğinde bir kez olur.

### Oturum
- Kameraya bir kez giriş yapılır ve oturum açık tutulur.
- Kamera oturumu yaklaşık 12 dakikada bir kendisi kapatır ve sonraki isteğe `401` ile cevap verir. Bu durumda istek yeni bir girişle hemen bir kez daha denenir. Sorgu başarısız sayılmaz, anahtarlar "kullanılamıyor" olmaz.

### Hata olursa
- Her istek için 10 saniyelik zaman aşımı vardır.
- python-kasa bağlantı hatası veya zaman aşımında aynı isteği en fazla 3 kez daha dener. Zaman aşımından sonra denemeler arasında 1 saniye bekler.
- Kimlik doğrulama hatasında ve kameranın hata koduyla cevap verdiği durumlarda tekrar denenmez.
- Sorgu yine de başarısız olursa anahtarlar "kullanılamıyor" görünür ve bir sonraki sorgu zamanı beklenir. Hızlı art arda deneme yoktur.
- Kötü durumda tek bir sorgu kameraya en fazla 4 deneme olarak gidebilir. Bu denemeler de sıralıdır.

### Kamera IP değiştirirse
- Üst üste 3 sorgu cevapsız kalırsa kamera ağda MAC adresiyle aranır. Yeni IP'de bulunursa kaydedilir ve entegrasyon yeni adresle yeniden bağlanır.
- Bu arama en fazla 15 dakikada bir yapılır. Kamera hata koduyla cevap veriyorsa ulaşılabilir demektir, arama yapılmaz.
- Açılışta kameraya bağlanılamazsa veya o IP'de başka bir cihaz çıkarsa da aynı arama yapılır.
- Arama yalnızca ağa bir yayın gönderir, hiçbir cihaza giriş yapmaz.

## python-kasa ve resmi TP-Link entegrasyonu
- **python-kasa** kütüphanesi Home Assistant ile birlikte kurulu gelir, ayrıca bir şey indirilmez.
- Entegrasyon resmi TP-Link entegrasyonunun kendisini kullanmaz ve onun kurulu olmasını gerektirmez. Ama kameraya **TP-Link entegrasyonunun bağlandığı gibi** bağlanır:
  - **HTTP oturumu:** Home Assistant'ın yönettiği HTTP oturumu, TP-Link entegrasyonundaki ayarlarla kullanılır.
  - **Kaydedilmiş bağlantı ayarları:** İlk başarılı bağlantıda kameranın bağlantı türü kaydedilir. Sonraki açılışlarda kamera doğrudan bu ayarlarla bağlanır, tahmin veya keşif yapılmaz.
  - **MAC kontrolü:** Bağlanılan cihazın MAC adresi kayıtlı kamerayla karşılaştırılır. IP adresinde başka bir cihaz varsa kullanılmaz, kameralar karışmaz.
  - **IP değişikliği:** Kamera ağda, TP-Link entegrasyonunun keşfiyle aynı yöntemle MAC adresinden bulunur.
- Bilerek farklı bırakılanlar:
  - TP-Link kamerayı 5 saniyede bir tüm bilgileriyle sorgular. Bu entegrasyon dakikada bir yalnızca alarm ve bildirim ayarını okur.
  - Kameranın oturumu kapattığı `401` cevabında istek yeni girişle bir kez daha denenir. TP-Link bunu yapmaz ve o sorguyu başarısız sayar.
- Aynı kamera hem TP-Link entegrasyonuna hem bu entegrasyona ekliyse kameraya iki ayrı oturum açılır.

## Sorun giderme
- **Anahtarlar sık sık "kullanılamıyor" oluyor:** Log'da `Connect call failed` veya `TimeoutError` varsa kamera o anda ağda değildir (Wi-Fi kopması veya yeniden başlama). Home Assistant'ın **Ping** entegrasyonuyla kameranın IP'si için bir sensör ekleyin; ping de düşüyorsa sorun Wi-Fi'da veya kameradadır. Tapo uygulamasından kameranın sinyal gücüne bakın.
- **Kamera zorlanıyor gibi:** Sorgulama aralığını 120 veya 300 saniyeye çıkarın. Bunun tek bedeli, alarm Tapo uygulamasından değiştirildiğinde Home Assistant'ın bunu daha geç görmesidir. Home Assistant'tan yapılan değişiklikler anında yansır.
- **Ayrıntılı log:** `configuration.yaml` dosyasına ekleyip Home Assistant'ı yeniden başlatın:
  ```yaml
  logger:
    logs:
      custom_components.tapo_kasa_alarm: debug
  ```
  python-kasa'nın kameraya giden istekleri de görmek için `kasa: debug` satırını ekleyin. Bu satır çok log üretir, sorunu bulduktan sonra kaldırın.

## Logo
Logo, Tapo Control entegrasyonunun logosudur. Home Assistant 2026.3 ve sonrası logoyu `brand/` klasöründen gösterir. Daha eski sürümlerde logo yerine boş simge görünür.

## Geliştirme
```bash
pip install pytest-homeassistant-custom-component python-kasa
pytest
```
