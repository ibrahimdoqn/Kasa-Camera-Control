# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- 2.0.0'dan beri, [Tapo Control](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control) entegrasyonunun kullandığı **pytapo** kütüphanesini kullanır. Kameraya Tapo Control'ün bağlandığı gibi bağlanır.
- Alarmı kameranın güncel komutlarıyla (`getAlertConfig` / `setAlertConfig`) ve Tapo uygulamasının gönderdiği biçimde yazar.
- Her sorguda yalnızca alarm ve bildirim ayarını, tek bir istekle okur.

C520WS ve C510W için yazıldı. `getAlertConfig` / `setAlertConfig` destekleyen diğer Tapo kameralarda da çalışmalı.

Tamamen **yerel** çalışır: kameralarla ev ağı içinden konuşur, TP-Link bulutuna istek göndermez. Ayrıntılar için [Yerel çalışma](#yerel-çalışma) bölümüne bakın.

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki "Alarm" anahtarı) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |
| `button.<kamera>_yeniden_baslat` | Kamerayı yeniden başlatır (Tanılama bölümünde) |
| `sensor.<kamera>_baglanti_kuruldu` | Bağlantının ne zaman kurulduğu ve ne zamandır sürdüğü (Tanılama bölümünde) |
| `sensor.<kamera>_kopma_sayisi` | Bağlantının kaç kez koptuğu ve son kopmanın ayrıntıları (Tanılama bölümünde) |

- Ses veya ışıktan en az biri açık kalmalıdır; kamera bunu zorunlu tutar.
- Varlık kimlikleri Home Assistant'ın diline göre oluşur. Örneğin İngilizce kurulumda `switch.<kamera>_alarm_sound` olur.
- Kamera bildirim ayarını bildirmiyorsa Bildirimler anahtarı eklenmez.

## Kurulum (HACS)
1. HACS → sağ üst menü (⋮) → **Custom repositories**
2. Depo: `https://github.com/ibrahimdoqn/Kasa-Camera-Control`, tür: **Integration**
3. **Kasa Camera Control** kurun ve Home Assistant'ı yeniden başlatın.
4. Ayarlar → Cihazlar ve Hizmetler → **Entegrasyon ekle** → *Kasa Camera Control*
5. Açılan formu doldurun:
   - **IP adresi:** Kameranın ev ağındaki adresi, örneğin `192.168.1.50`. Tapo uygulamasında kamera → Ayarlar → Cihaz bilgisi bölümünde görünür.
   - **Bulut şifresi:** Tapo uygulamasına giriş yaptığınız TP-Link hesabının şifresi. Kameraya bu şifreyle yerel olarak `admin` kullanıcısıyla girilir; Tapo Control'ün bulut şifresiyle girdiği gibi.
6. Her kamera için 4. ve 5. adımları tekrarlayın.

> Kameralara sabit IP (DHCP rezervasyonu) verin. MAC ile IP arama yoktur; IP değişirse kameranın **Yeniden yapılandır** menüsünden yeni IP'yi girin.
>
> Eski `tapo_control` kurulumunu kaldırın. Aynı kameraya iki entegrasyonun birlikte bağlanması kameraya yük bindirir. İkisini birlikte kullanacaksanız sürüm çakışması olmaz: bu entegrasyon Tapo Control'le aynı pytapo sürümünü (3.4.19) kullanır.

## Güncelleme
1. HACS'ta **Kasa Camera Control** sayfasından yeni sürümü indirin.
2. Home Assistant'ı yeniden başlatın.
3. Tarayıcıda sayfayı tamamen yenileyin (Ctrl+F5) veya mobil uygulamayı kapatıp açın. Yoksa formlar eski çevirilerle ya da `host`, `cloud_password` gibi ham alan adlarıyla görünebilir.

Kameraları yeniden eklemeniz gerekmez.

## Seçenekler
Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera → **Yapılandır**

- **Sorgulama aralığı (saniye):** Varsayılan 5, en az 5. Değişiklik kameraya yeniden bağlanmadan uygulanır.

IP adresini veya bulut şifresini değiştirmek için: Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera → ⋮ → **Yeniden yapılandır**. Yeni IP'de başka bir kamera cevap verirse değişiklik kaydedilmez.

## Yerel çalışma
Entegrasyon kameralarla doğrudan ev ağınızın içinde konuşur ve TP-Link bulutuna hiçbir istek göndermez (`local_polling`).

- **Kamera bağlantısı:** Home Assistant kameraya doğrudan IP adresinden, ev ağı içinde HTTPS ile bağlanır.
- **Alarm, bildirim ve yeniden başlatma:** Hepsi bu yerel bağlantı üzerinden gider.

**Bulut şifresi neden kullanılabiliyor?** Tapo kameralar yerel girişte `admin` kullanıcısı için TP-Link hesabının şifresini kabul eder. Kamera, Tapo uygulamasıyla kurulurken bu şifrenin şifrelenmiş bir kopyasını kendi içinde saklar. Entegrasyon girişi kameranın kendisine yapar, TP-Link sunucularına değil.

**İnternet kesilirse:** Alarm ve bildirim anahtarları çalışmaya devam eder.
- İstisna: TP-Link hesabınızın şifresini değiştirirseniz, kamera yeni şifreyi internet üzerinden öğrenir. Sonra Home Assistant sizden yeni şifreyi ister.

**Bulutla ilişkili tek şey:** Bildirimler anahtarı kameranın bildirim gönderip göndermeyeceğini yerel olarak ayarlar. Bildirimlerin telefona ulaşması ise Tapo'nun kendi bulutu üzerinden olur; bu, Tapo uygulamasının kendi işleyişidir.

HACS'ın entegrasyonu GitHub'dan indirip güncellemesi dışında, günlük çalışmada hiçbir şey internete gitmez.

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

### Bağlantı
Kameraya Tapo Control'ün `registerController`'ındaki ayarlarla bağlanılır:
- **pytapo 3.4.19:** Tapo Control'ün kullandığı sürüm. pytapo bloklayan bir kütüphane olduğu için her çağrı Home Assistant'ın arka plan iş parçacıklarında çalışır; Home Assistant'ın ana döngüsünü bekletmez.
- **Giriş:** `admin` + TP-Link bulut şifresi. Tapo Control'e bulut şifresi girildiğinde de böyle girer.
- **Her istek yeni HTTPS bağlantısıyla** gider (`reuseSession=False`), Tapo Control'deki gibi. Kamera oturumu (`stok`) ise korunur, her istekte yeniden giriş yapılmaz.
- **KLAP:** Kameranın giriş türü (KLAP mı değil mi) ilk bağlantıda bulunur ve kaydedilir; sonraki açılışlarda yeniden aranmaz. Tapo Control de böyle yapar.
- **MAC kontrolü:** Bağlanılan cihazın MAC adresi kayıtlı kamerayla karşılaştırılır. O IP'de başka bir cihaz varsa kullanılmaz, kameralar karışmaz.
- **Zaman aşımı:** 10 saniye (pytapo'nun varsayılanı).
- pytapo kamera başına **tek oturum** tutar ve istekleri sırayla gönderir.

### Oturum
- Kameralar oturumu girişten yaklaşık **10 dakika** sonra, trafik olsa da olmasa da kapatır. pytapo bunu kameranın `-40401` (oturum doldu) cevabından anlar, yeniden giriş yapar ve isteği bir kez tekrarlar. Anahtarlar "kullanılamıyor" olmaz. Tapo uygulaması ve Tapo Control de böyle çalışır.
- Kameralar yalnızca art arda **başarısız** girişlerde hesabı geçici olarak kilitler. Oturum dolunca yapılan başarılı giriş sorun değildir.

### Sorgulama
- Varsayılan 5 saniyede bir sorgulanır.
- Her sorguda kameraya **tek bir istek** gider: alarm ayarı (`getAlertConfig`) ve bildirim ayarı (`getMsgPushConfig`) birlikte okunur.
- Tapo Control her sorguda `getMost` ile yaklaşık 90 komut okur (varsayılan 30 saniyede bir). Bu entegrasyon o bilgileri kullanmadığı için okumaz; kameraya çok daha az yük biner.
- Her kameranın kendi zamanlayıcısı vardır, kameralar birbirini beklemez. pytapo bir kameraya istekleri sırayla gönderir.

### Anahtara basınca
- Önce kameranın o anki ayarı okunur. Kamera zaten istenen durumdaysa (örneğin alarm açıkken "aç" komutu gelirse) kameraya **hiçbir şey yazılmaz**. Alarm yazmak nadiren kameranın servislerini yeniden başlattığı, okumak ise hiç başlatmadığı için gereksiz yazmalar önlenir. Okuma anlık yapıldığı için arada Tapo uygulamasından yapılan bir değişiklik gözden kaçmaz.
- Değişiklik gerekiyorsa tek bir yazma isteği gider. Yazma başarısız olursa ekranda hata gösterilir.
- Yazma başarılı olunca yeni durum hemen gösterilir; kamera hemen yeniden sorgulanmaz. Tapo uygulaması da böyle yapar. Böylece kamera yeni alarm ayarını uygularken ona soru sorulmaz. Sonraki normal sorgu durumu kameradan doğrular.

### Yeniden başlatma düğmesine basınca
- pytapo'nun `reboot` komutu (`rebootDevice`) gönderilir, Tapo Control'deki gibi.
- Komuttan sonra ayrıca sorgu yapılmaz; normal sorgular devam eder. Kamera açılana kadar anahtarlar "kullanılamıyor" görünür, sonra kendiliğinden geri gelir. Bu kesinti **Kopma sayısı** sensörüne de bir kopma olarak yazılır.

### Alarm ayarını okuma ve yazma
- Alarm ayarı yalnızca `getAlertConfig` ile okunur ve `setAlertConfig` ile yazılır. Bu, kameranın güncel alarm komutudur; Tapo uygulaması da bu kameralarda bunu kullanır.
- Yazarken Tapo uygulaması gibi **yalnızca değişen alan** gönderilir: alarm açıp kapatınca sadece `{"enabled": "on"/"off"}`, ses/ışık değişince sadece `{"alarm_mode": [...]}`. Ses seviyesi, süre, ışık türü gibi diğer ayarlar yeniden yazılmaz.
- Ses ve ışık anahtarları, kamera bildiriyorsa `sound_alarm_enabled` / `light_alarm_enabled` alanlarını okur.
- **Kullanılmayan eski komutlar:** `getLastAlarmInfo` + ham `set` ve `getAlarmConfig` / `setAlarmConfig`. Tapo Control bunları `getAlertConfig`'ten önce dener. pytapo'nun eski `setAlarm` komutu ayrıca her seferinde alarm sesi ve ışık türünü `"0"` yapar.
- `getAlertConfig`'i desteklemeyen bir kamera yüklenmez. Log'a "does not answer getAlertConfig" hatası yazılır ve Home Assistant kurulumu tekrar tekrar dener.

### Bildirim
- pytapo'nun `setNotificationsEnabled` komutuyla yazılır, Tapo Control'deki gibi. Yalnızca `notification_enabled` gönderilir.

### Hata olursa
- Bağlantı hatasında pytapo oturumu sıfırlar, 1 saniye bekler ve isteği bir kez daha dener.
- Kamera oturumun dolduğunu söylerse (`-40401`) pytapo yeniden giriş yapıp isteği bir kez tekrarlar.
- Kamera yine cevap vermezse anahtarlar "kullanılamıyor" görünür ve bir sonraki sorgu zamanı beklenir.
- Giriş reddedilirse ("Invalid authentication data") hemen şifre istenmez. Kameralar geçerli bir girişi de kısa süre reddedebilir, örneğin yeniden başlarken. Tapo Control'deki gibi art arda 3 red tolere edilir: kurulumda Home Assistant tekrar dener, sorguda anahtarlar o süre "kullanılamıyor" görünür. **4. red üst üste gelirse** Home Assistant şifreyi yeniden ister. Arada kabul edilen bir giriş veya başarılı bir sorgu sayacı sıfırlar. Komutlar (anahtara basma) şifre istemez; red olursa ekranda hata gösterilir. Kamera çok sayıda başarısız girişten sonra kendini geçici olarak kilitlerse ("Temporary Suspension") yeniden bilgi istenmez, kilit açılınca tekrar denenir.

### Bağlantı tanılama
Her kameranın cihaz sayfasındaki **Tanılama** bölümünde iki sensör vardır. Kameraya ek istek göndermezler; entegrasyonun zaten gördüğünü gösterirler.

- **Bağlantı kuruldu:** Mevcut bağlantının kurulduğu an. Home Assistant bunu hem saat olarak hem de "x dakika önce" olarak gösterir; bu da bağlantının ne zamandır sürdüğüdür. Bağlantı koptuğunda "Bilinmiyor" olur, geri gelince yeni zamanı gösterir.
- **Kopma sayısı:** Home Assistant başladığından beri bağlantının kaç kez koptuğu. Art arda başarısız sorgular tek kopma sayılır. Home Assistant yeniden başlatıldığında (veya entegrasyon yeniden yüklendiğinde) 0'dan başlar; son kopmanın ayrıntıları da sıfırlanır.
  - `last_disconnect`: son kopmanın zamanı.
  - `last_disconnect_reason`: son kopmanın sebebi:
    - `reboot`: kamera ağda ama bağlantıyı reddediyor. Genellikle kamera servislerini yeniden başlatıyordur.
    - `unreachable`: kamera ağda görünmüyor (Wi-Fi kopması, kapanma).
    - `timeout`: kamera zamanında cevap vermedi.
    - `auth`: giriş reddedildi.
    - `error`: kameranın hata cevabı gibi diğer durumlar.
  - `last_outage_seconds`: son kesintinin kaç saniye sürdüğü.
  - `down_since`: şu an kesinti varsa başladığı zaman.
- Sensörler kamera ulaşılamazken de görünür kalır, böylece kesinti anında da okunabilir.
- pytapo'nun kendi tekrarıyla kurtarılan hatalar kopma sayılmaz; yalnızca anahtarların "kullanılamıyor" olduğu kesintiler sayılır.

**Kullanım:** Kopma zamanlarını alarm geçmişi, RTSP kaydı yapan sistemin log'u veya modemin log'u ile karşılaştırarak kameranın ne zaman ve neden koptuğunu görebilirsiniz.

### Tapo Control'den farkları
- Yalnızca alarm, alarm sesi/ışığı, bildirim, yeniden başlatma ve bağlantı tanılama vardır. Görüntü, hareket algılama, PTZ gibi özellikler yoktur.
- Her sorguda `getMost` yerine yalnızca alarm ve bildirim ayarı okunur (1 istek).
- Alarm için her zaman `getAlertConfig` / `setAlertConfig` kullanılır ve yalnızca değişen alan yazılır. Tapo Control eski komutları önce dener ve `setAlertConfig`'te ayarın tamamını gönderir.
- Yazmadan önce okunur, gerekmiyorsa yazılmaz. Yazmadan hemen sonra kamera okunmaz. Tapo Control her yazmadan sonra `getMost` ile yeniler.

### Tapo uygulamasıyla karşılaştırma
Tapo uygulaması (Android 3.21.112) incelenerek karşılaştırıldı:
- **Giriş ve şifreleme:** Uygulama da pytapo ile aynı yöntemi kullanır: `cnonce`/`nonce` ile giriş, `stok` belirteci, AES şifreli `securePassthrough`, her istekte artan `seq` ve `tapo_tag` başlıkları.
- **İstek biçimi:** Uygulama `setAlertConfig`'i de `multipleRequest` içinde gönderir, pytapo da öyle.
- **Alarm yazma:** Uygulama yalnızca değişen alanı gönderir. Bu entegrasyon da öyle yapar.
- **Yazmadan sonra:** Uygulama kamerayı hemen okumaz, bildiği durumu günceller. Bu entegrasyon da öyle yapar.
- **Oturum:** Uygulama oturumu süreyle yenilemez; kamera `-40401` dediğinde yeniden giriş yapar. pytapo da böyle yapar.
- **Zaman aşımı:** Uygulama 30 saniye, pytapo 10 saniye bekler.

## Sorun giderme
- **Anahtarlar sık sık "kullanılamıyor" oluyor:** Log'da `Connection refused`, `Max retries exceeded` veya `timed out` varsa kamera o anda ağda değildir veya servislerini yeniden başlatıyordur. Home Assistant'ın **Ping** entegrasyonuyla kameranın IP'si için bir sensör ekleyin; ping de düşüyorsa sorun Wi-Fi'da veya kameradadır. Tapo uygulamasından kameranın sinyal gücüne bakın.
- **Formda `host`, `cloud_password` gibi ham alan adları görünüyor, açıklama yok:** Arayüz çevirileri yüklenmemiş demektir; genelde sayfa Home Assistant yeniden başlarken açık kaldığında olur. Tarayıcıda Ctrl+F5 ile yenileyin veya mobil uygulamayı kapatıp açın.
- **Giriş hatası:** Tapo uygulamasına girdiğiniz TP-Link hesabının şifresini kullandığınızı kontrol edin. Art arda yanlış denemeden sonra kamera girişi bir süre kilitler; birkaç dakika bekleyin.
- **Otomasyon "kullanılamıyor"dan dönünce tetikleniyor:** Kamera ağdan düştüğünde anahtarlar "kullanılamıyor" olur. Anahtar "kullanılamıyor"dan tekrar "açık"a döndüğünde durum değişikliğine bağlı bir otomasyon tetiklenebilir. Tetikleyiciye `not_from: unavailable` ekleyin:
  ```yaml
  triggers:
    - trigger: state
      entity_id: switch.bahce_alarm
      to: "on"
      not_from: unavailable
  ```
- **Kamera zorlanıyor gibi:** Sorgulama aralığını 30 veya 60 saniyeye çıkarın. Bunun tek bedeli, kamerada yapılan değişikliklerin (örneğin Tapo uygulamasından) Home Assistant'ta daha geç görünmesidir.
- **Ayrıntılı log:** `configuration.yaml` dosyasına ekleyip Home Assistant'ı yeniden başlatın:
  ```yaml
  logger:
    logs:
      custom_components.tapo_kasa_alarm: debug
  ```
  Bu ayar pytapo'nun kameraya giden isteklerini de gösterir ve çok log üretir. Yalnızca entegrasyonun kendi kayıtlarını görmek için pytapo'yu ayrıca kısın:
  ```yaml
  logger:
    logs:
      custom_components.tapo_kasa_alarm: debug
      custom_components.tapo_kasa_alarm.api.pytapo: warning
  ```
  Sorunu bulduktan sonra bu satırları kaldırın.

## Logo
Logo, Tapo Control entegrasyonunun logosudur. Home Assistant 2026.3 ve sonrası logoyu `brand/` klasöründen gösterir. Daha eski sürümlerde logo yerine boş simge görünür.

## Geliştirme
```bash
pip install pytest-homeassistant-custom-component pytapo==3.4.19
pytest
```
