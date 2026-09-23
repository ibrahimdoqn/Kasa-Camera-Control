# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- `pytapo` yerine, Home Assistant'ın resmi **TP-Link Smart Home** entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır.
- Kameraya resmi TP-Link entegrasyonunun bağlandığı ve sorguladığı gibi bağlanır ve sorgular.
- Resmi entegrasyonda olmayan otomatik alarm ve bildirim anahtarlarını ekler.

C520WS ve C510W için yazıldı. `msg_alarm` destekleyen diğer Tapo kameralarda da çalışmalı.

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki "Alarm" anahtarı) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |
| `button.<kamera>_yeniden_baslat` | Kamerayı yeniden başlatır (Tanılama bölümünde) |

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

> Kameralara sabit IP (DHCP rezervasyonu) vermeniz önerilir. Sabit IP kullanıyorsanız seçeneklerden **MAC ile arama**yı kapatabilirsiniz.
>
> Eski `tapo_control` kurulumunu kaldırın. Aynı kameraya iki entegrasyonun birlikte bağlanması kameraya yük bindirir.

## Güncelleme
1. HACS'ta **Kasa Camera Control** sayfasından yeni sürümü indirin.
2. Home Assistant'ı yeniden başlatın.

Kameraları yeniden eklemeniz gerekmez. Artık kullanılmayan varlıklar (eski Siren ve Zengin bildirimler) ilk açılışta otomatik silinir.

> 1.5.0'dan önce sorgulama aralığını seçeneklerden değiştirdiyseniz o değer korunur. TP-Link'teki 5 saniyeye geçmek için seçeneklerden 5 yapın.

## Seçenekler
Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera → **Yapılandır**

- **Sorgulama aralığı (saniye):** Varsayılan 5, TP-Link entegrasyonuyla aynı. En az 5. Değişiklik kameraya yeniden bağlanmadan uygulanır.
- **IP değişirse kamerayı bul (MAC ile arama):** Varsayılan açık, TP-Link entegrasyonundaki gibi. Kamera açılışta ve 15 dakikada bir ağda MAC adresiyle aranır; IP'si değişmişse yeni adres kaydedilir. Sabit IP kullanıyorsanız kapatın; kapalıyken ağa hiç arama yayını gönderilmez.

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
Entegrasyon, Home Assistant'ın resmi TP-Link entegrasyonunun kodu örnek alınarak yazıldı. Kameraya onunla aynı şekilde bağlanır ve onunla aynı sıklıkta sorgular.

### Bağlantı
- **python-kasa:** Home Assistant ile birlikte kurulu gelir, ayrıca bir şey indirilmez.
- **HTTP oturumu:** Home Assistant'ın yönettiği HTTP oturumu, TP-Link entegrasyonundaki ayarlarla kullanılır.
- **Kaydedilmiş bağlantı ayarları:** İlk başarılı bağlantıda kameranın bağlantı türü kaydedilir. Sonraki açılışlarda kamera doğrudan bu ayarlarla bağlanır.
- **MAC kontrolü:** Bağlanılan cihazın MAC adresi kayıtlı kamerayla karşılaştırılır. O IP'de başka bir cihaz varsa kullanılmaz, kameralar karışmaz.
- **Zaman aşımı:** 5 saniye, TP-Link'le aynı.
- Kamera başına **tek oturum** açık tutulur. Kamera oturumu kapatırsa python-kasa bir sonraki sorguda yeniden giriş yapar.

### Sorgulama
- 5 saniyede bir, TP-Link'teki gibi kameranın tam güncellemesi (`device.update()`) yapılır.
- Ardından alarm ve bildirim ayarı tek bir istekte okunur. TP-Link bu ayarları okumadığı için bu istek ek olarak gider.
- Her kamera için bir kilit vardır. İstekler sırayla gider, kameraya aynı anda asla iki istek gitmez.
- Her kameranın kendi zamanlayıcısı vardır. Kameralar birbirini beklemez.

### Anahtara veya düğmeye basınca
- Tek bir yazma isteği gider.
- TP-Link'teki gibi, 0,35 saniye sonra kamera yeniden sorgulanır ve yeni durum oradan okunur.
- Yeniden başlatmadan sonra sorgu yapılmaz. Kamera bir süre "kullanılamıyor" görünür ve açılınca kendiliğinden geri gelir.

### Alarm ayarını okuma
- Kamera modeline ve yazılımına göre alarm ayarı farklı komutlarla okunur (`getLastAlarmInfo`, `getAlertConfig`, `getAlarmConfig`).
- Hangisinin desteklendiği bilinmiyorsa bu üç komut sırayla denenir. Çalışan komut hatırlanır, sonraki sorgular yalnızca onu kullanır.

### Hata olursa
TP-Link entegrasyonundaki gibi:
- python-kasa bağlantı hatası veya zaman aşımında aynı isteği en fazla 3 kez daha dener.
- Sorgu yine de başarısız olursa anahtarlar "kullanılamıyor" görünür ve bir sonraki sorgu zamanı beklenir.
- Kimlik doğrulama hatasında Home Assistant yeniden giriş bilgisi ister.

### IP değişikliği (MAC ile arama)
- TP-Link'teki gibi, Home Assistant açılışında ve 15 dakikada bir ağa bir arama yayını gönderilir. Yayın hiçbir cihaza giriş yapmaz.
- Kamera MAC adresiyle bulunur. IP'si değişmişse yeni adres kaydedilir ve entegrasyon yeni adresle yeniden bağlanır.
- Seçeneklerden kapatılabilir. Kapalı kameralar için arama yapılmaz; hiçbir kamerada açık değilse yayın da gönderilmez.

### Yeniden başlatma
- python-kasa'nın yeniden başlatma komutu kameralarda çalışmadığı için TP-Link kameralarda bu düğmeyi göstermez.
- Bu entegrasyon Tapo Control'ün kameralar için kullandığı `rebootDevice` komutunu gönderir. Düğme TP-Link'in "Yeniden başlat" düğmesiyle aynı türde ve aynı "Tanılama" bölümündedir.
- TP-Link bu düğmeyi varsayılan olarak kapalı getirir; burada açık gelir.

### TP-Link'ten farkları
- Alarm, alarm sesi/ışığı ve bildirim anahtarları ile kameralar için yeniden başlatma düğmesi. TP-Link'te bunlar yok.
- Sorgulama aralığı ve MAC ile arama seçenekten değiştirilebilir. TP-Link'te bu ayarlar sabittir; varsayılanlar TP-Link'inkilerle aynıdır.
- Aynı kamera hem TP-Link entegrasyonuna hem bu entegrasyona ekliyse kameraya iki ayrı oturum açılır.

## Sorun giderme
- **Anahtarlar sık sık "kullanılamıyor" oluyor:** Log'da `Connect call failed` veya `TimeoutError` varsa kamera o anda ağda değildir (Wi-Fi kopması veya yeniden başlama). Home Assistant'ın **Ping** entegrasyonuyla kameranın IP'si için bir sensör ekleyin; ping de düşüyorsa sorun Wi-Fi'da veya kameradadır. Tapo uygulamasından kameranın sinyal gücüne bakın.
- **Kamera zorlanıyor gibi:** Sorgulama aralığını 30 veya 60 saniyeye çıkarın. Bunun tek bedeli, kamerada yapılan değişikliklerin (örneğin Tapo uygulamasından) Home Assistant'ta daha geç görünmesidir.
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
