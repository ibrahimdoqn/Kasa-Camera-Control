# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- Kameraya [Tapo Control](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control) entegrasyonunun kütüphanesi **pytapo** ile, onun bağlandığı gibi bağlanır.
- Alarmı Tapo uygulamasının gönderdiği biçimde yazar: yalnızca değişen ayar gider.
- Kameraya az yük bindirir: her sorguda tek istek, gereksiz yazma yok.
- Tamamen **yerel** çalışır, TP-Link bulutuna istek göndermez.

C520WS ve C510W için yazıldı. `getAlertConfig` / `setAlertConfig` destekleyen diğer Tapo kameralarda da çalışmalı.

Nasıl çalıştığının ayrıntıları: [ARCHITECTURE.md](ARCHITECTURE.md)

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki "Alarm" anahtarı) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |
| `button.<kamera>_yeniden_baslat` | Kamerayı yeniden başlatır (Tanılama bölümünde) |
| `binary_sensor.<kamera>_baglanti` | Kamera bağlı mı; son kopmanın ayrıntıları (Tanılama bölümünde) |
| `sensor.<kamera>_uptime` | Kameranın ne zamandır kesintisiz çalıştığı (Tanılama bölümünde) |

- Ses veya ışıktan en az biri açık kalmalıdır; kamera bunu zorunlu tutar.
- Varlık kimlikleri Home Assistant'ın diline göre oluşur. Örneğin İngilizce kurulumda `switch.<kamera>_alarm_sound` olur.
- Kamera bildirim ayarını bildirmiyorsa Bildirimler anahtarı eklenmez.

## Kurulum
1. HACS → sağ üst menü (⋮) → **Custom repositories**
2. Depo: `https://github.com/ibrahimdoqn/Kasa-Camera-Control`, tür: **Integration**
3. **Kasa Camera Control**'ü kurun ve Home Assistant'ı yeniden başlatın.
4. Ayarlar → Cihazlar ve Hizmetler → **Entegrasyon ekle** → *Kasa Camera Control*
5. Formu doldurun:
   - **IP adresi:** Kameranın ev ağındaki adresi, örneğin `192.168.1.50`. Tapo uygulamasında kamera → Ayarlar → Cihaz bilgisi bölümünde görünür.
   - **Bulut şifresi:** Tapo uygulamasına giriş yaptığınız TP-Link hesabının şifresi.
6. Her kamera için 4. ve 5. adımları tekrarlayın.

> Kameralara modeminizden sabit IP (DHCP rezervasyonu) verin. IP değişirse kameranın **Yeniden yapılandır** menüsünden yeni IP'yi girin.
>
> Aynı kamerayı Tapo Control'e de eklemeyin; iki entegrasyonun birlikte bağlanması kameraya yük bindirir.

## Güncelleme
1. HACS'ta **Kasa Camera Control** sayfasından yeni sürümü indirin.
2. Home Assistant'ı yeniden başlatın.
3. Tarayıcıda sayfayı tamamen yenileyin (Ctrl+F5) veya mobil uygulamayı kapatıp açın.

## Ayarlar
Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera:

- **Yapılandır:**
  - **Sorgulama aralığı (saniye):** Alarm ve bildirim ayarlarının kaç saniyede bir okunacağı. Varsayılan 5, en az 5.
  - **Bağlantı kontrol aralığı (saniye):** Bağlantı ve Uptime için kameranın kaç saniyede bir kontrol edileceği. Varsayılan 1, en az 1, en fazla 60.
  - Değişiklikler hemen uygulanır.
- **⋮ → Yeniden yapılandır:** IP adresini veya bulut şifresini değiştirir. Yeni IP'de başka bir kamera cevap verirse değişiklik kaydedilmez.

## Yerel çalışma
Home Assistant kameraya doğrudan ev ağı içinden, HTTPS ile bağlanır. Alarm, bildirim ve yeniden başlatma bu bağlantıyla gider; TP-Link sunucularına hiçbir istek gönderilmez.

- **Bulut şifresi neden gerekiyor?** Tapo kameralar yerel girişte `admin` kullanıcısı için TP-Link hesabının şifresini kabul eder. Kamera bu şifrenin bir kopyasını kendi içinde saklar; giriş kameranın kendisine yapılır.
- **İnternet kesilirse:** Anahtarlar çalışmaya devam eder. TP-Link hesabınızın şifresini değiştirirseniz kamera yeni şifreyi internet üzerinden öğrenir; sonra Home Assistant sizden yeni şifreyi ister.
- **Bildirimler:** Anahtar kameranın bildirim gönderip göndermeyeceğini yerel olarak ayarlar. Bildirimlerin telefona ulaşması Tapo'nun kendi bulutu üzerinden olur.

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

Alarm zaten açıksa kameraya bir şey yazılmaz; otomasyonu gönül rahatlığıyla sık çalıştırabilirsiniz.

## Bağlantı tanılama
Entegrasyon kameranın **443 portuna saniyede bir** (ayarlanabilir) bağlanıp hemen kapatır. Giriş yapmaz, kameranın ayarlarına dokunmaz. Sonuç, cihaz sayfasının **Tanılama** bölümünde iki sensörde görünür:

- **Bağlantı:** *Bağlı* veya *Bağlantı kesildi*. Tek bir başarısız kontrol takılma sayılır; art arda iki kontrol başarısız olursa bağlantı kesik sayılır (kesinti ilk başarısız kontrolden başlar).
- **Uptime:** Kameranın kesintisiz çalışmaya başladığı an; "3 saat önce" gibi görünür. Bağlantı yokken *Bilinmiyor*. Home Assistant yeniden başladığında ölçüm baştan başlar.

**Bağlantı** sensörünün öznitelikleri:

| Öznitelik | Anlamı |
|---|---|
| Son kopma | Zamanı |
| Son kopma sebebi | *Kamera ağda, servisleri yeniden başlıyor* (port bağlantıyı reddetti; alarm yazmasından sonraki çökmeler böyle görünür) veya *Kamera ağda değil* (cevap yok: Wi-Fi, elektrik, tamamen yeniden başlama) |
| Son kesinti süresi (sn) | Kesintinin kaç saniye sürdüğü (bağlantı geri gelince yazılır) |
| Kesinti başlangıcı | Şu an kesinti varsa başladığı zaman |

Bağlantı kontrolü alarm sorgularından bağımsızdır: sorgu hataları bu sensörleri değiştirmez, bu sensörler de anahtarları etkilemez.

## Sorun giderme
- **Anahtarlar sık sık "kullanılamıyor" oluyor:** Kamera o anda ağda değildir veya servislerini yeniden başlatıyordur. Tanılama'daki **Bağlantı** sensörünün **Son kopma sebebi** hangisi olduğunu gösterir. **Ping** entegrasyonuyla kameranın IP'si için bir sensör ekleyin; ping de düşüyorsa sorun Wi-Fi'da veya kameradadır.
- **Alarm anahtarı kısa süre sonra eski değerine dönüyor:** Kamera yazmayı kabul edip hemen ardından çökmüş ve yeni ayarı kaydetmeden yeniden başlamıştır (RTSP de kopar). Bu kameranın firmware hatasıdır; anahtar kameranın gerçek durumunu gösterir. Tapo uygulamasından firmware güncellemesine bakın.
- **Şifre soruluyor:** Kamera girişi art arda 4 kez reddetmiştir. Tapo uygulamasına giriş yaptığınız TP-Link hesabının şifresini girin. Art arda yanlış denemeden sonra kamera girişi bir süre kilitler; birkaç dakika bekleyin.
- **Formda `host`, `cloud_password` gibi ham alan adları görünüyor:** Arayüz çevirileri yüklenmemiştir. Tarayıcıda Ctrl+F5 ile yenileyin veya mobil uygulamayı kapatıp açın.
- **Otomasyon "kullanılamıyor"dan dönünce tetikleniyor:** Tetikleyiciye `not_from: unavailable` ekleyin:
  ```yaml
  triggers:
    - trigger: state
      entity_id: switch.bahce_alarm
      to: "on"
      not_from: unavailable
  ```
- **Kamera zorlanıyor gibi:** Sorgulama aralığını 30 veya 60 saniyeye çıkarın. Tapo uygulamasından yapılan değişiklikler Home Assistant'ta daha geç görünür.
- **Ayrıntılı log:** `configuration.yaml` dosyasına ekleyip Home Assistant'ı yeniden başlatın:
  ```yaml
  logger:
    logs:
      custom_components.tapo_kasa_alarm: debug
      custom_components.tapo_kasa_alarm.api.pytapo: warning  # pytapo'nun ayrıntılı loglarını görmek için bu satırı silin
  ```
  Sorunu bulduktan sonra bu satırları kaldırın.

## Logo
Logo, Tapo Control entegrasyonunun logosudur. Home Assistant 2026.3 ve sonrası logoyu `brand/` klasöründen gösterir.
