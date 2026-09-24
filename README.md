# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- `pytapo` yerine, Home Assistant'ın resmi **TP-Link Smart Home** entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır.
- Kameraya resmi TP-Link entegrasyonunun bağlandığı gibi bağlanır. Her sorguda yalnızca alarm ve bildirim ayarını, tek bir istekle okur.
- Resmi entegrasyonda olmayan otomatik alarm ve bildirim anahtarlarını ekler.

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

> v1.7.0 (yazma kuyruğu) geri çekildi. 1.6.4, 1.6.3'ün davranışına tanılama sensörlerini ekler.

> 1.5.0'dan önce sorgulama aralığını seçeneklerden değiştirdiyseniz o değer korunur. TP-Link'teki 5 saniyeye geçmek için seçeneklerden 5 yapın.

## Seçenekler
Ayarlar → Cihazlar ve Hizmetler → **Kasa Camera Control** → kamera → **Yapılandır**

- **Sorgulama aralığı (saniye):** Varsayılan 5, TP-Link entegrasyonuyla aynı. En az 5. Değişiklik kameraya yeniden bağlanmadan uygulanır.
- **Oturumu yenileme aralığı (dakika):** Varsayılan 8, en fazla 60, 0 kapatır. Kameralar oturumu girişten yaklaşık 10 dakika sonra kapatır; entegrasyon bundan önce yeniden giriş yapar. Log'da sık sık `401` uyarısı görüyorsanız değeri düşürün.
- **IP değişirse kamerayı bul (MAC ile arama):** Varsayılan açık, TP-Link entegrasyonundaki gibi. Kamera açılışta ve 15 dakikada bir ağda MAC adresiyle aranır; IP'si değişmişse yeni adres kaydedilir. Sabit IP kullanıyorsanız kapatın; kapalıyken ağa hiç arama yayını gönderilmez.

## Yerel çalışma
Entegrasyon kameralarla doğrudan ev ağınızın içinde konuşur ve TP-Link bulutuna hiçbir istek göndermez (`local_polling`).

- **Kamera bağlantısı:** Home Assistant kameraya doğrudan IP adresinden, ev ağı içinde HTTPS ile bağlanır.
- **Alarm, bildirim ve yeniden başlatma:** Hepsi bu yerel bağlantı üzerinden gider.
- **MAC ile IP arama:** Yalnızca ev ağına bir yayın gönderir, internete çıkmaz.

**TP-Link hesabı neden isteniyor?** Tapo kameralar yerel girişte de TP-Link hesabının e-posta ve şifresini kullanır. Kamera, Tapo uygulamasıyla kurulurken bu bilgilerin şifrelenmiş bir kopyasını kendi içinde saklar. Entegrasyon girişi kameranın kendisine yapar, TP-Link sunucularına değil.

**İnternet kesilirse:** Alarm ve bildirim anahtarları çalışmaya devam eder.
- İstisna: TP-Link hesabınızın şifresini değiştirirseniz kamera yeni şifreyi internet üzerinden öğrenir. Sonra Home Assistant sizden yeni şifreyi ister.

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
Entegrasyon, Home Assistant'ın resmi TP-Link entegrasyonunun kodu örnek alınarak yazıldı. Kameraya onunla aynı şekilde bağlanır ve onunla aynı sıklıkta (5 saniye) sorgular. Ama yalnızca kendi kullandığı bilgiyi okur.

### Bağlantı
- **python-kasa:** Home Assistant ile birlikte kurulu gelir, ayrıca bir şey indirilmez.
- **HTTP oturumu:** Home Assistant'ın yönettiği HTTP oturumu, TP-Link entegrasyonundaki ayarlarla kullanılır.
- **Kaydedilmiş bağlantı ayarları:** İlk başarılı bağlantıda kameranın bağlantı türü kaydedilir. Sonraki açılışlarda kamera doğrudan bu ayarlarla bağlanır.
- **MAC kontrolü:** Bağlanılan cihazın MAC adresi kayıtlı kamerayla karşılaştırılır. O IP'de başka bir cihaz varsa kullanılmaz, kameralar karışmaz.
- **Zaman aşımı:** 5 saniye, TP-Link'le aynı.
- Kamera başına **tek oturum** açık tutulur.

### Oturum yenileme
- Kameralar oturumu girişten yaklaşık **10 dakika** sonra, trafik olsa da olmasa da kapatır ve sonraki isteğe `401` ile cevap verir. python-kasa bunu ancak bir istek başarısız olunca fark eder.
- Resmi TP-Link entegrasyonunda bu durumda hiçbir şey "kullanılamıyor" olmaz: python-kasa'nın tam güncellemesi başarısız olan soruları yeni girişle tek tek tekrar sorar (bkz. [Hata olursa](#hata-olursa)). Bu entegrasyon da aynısını yapar. Ama o sorgu önce başarısız olur ve log'a bir kayıt düşer (TP-Link'te hata, burada uyarı).
- Bunu hiç yaşamamak için entegrasyon oturumu süre dolmadan, varsayılan olarak **8 dakikada bir** kendisi yeniler: eski oturumu bırakır ve hemen yeniden giriş yapar.
- Tapo kameralarda "çıkış yap" komutu yoktur; bırakılan oturumu kamera kendi süresi dolunca siler. Eski oturumla bir daha istek gönderilmez.
- Yenileme yalnızca kamera oturumunu sıfırlar; Home Assistant'ın ortak HTTP bağlantısı açık kalır.
- Aralık seçeneklerden değiştirilebilir; 0 yenilemeyi kapatır. TP-Link'te bu özellik yoktur.

**Ne zaman ve nasıl oluyor:**
- Son girişin üzerinden 8 dakika geçtikten sonraki **ilk sorguda** olur. Sorgulama 5 saniyede bir olduğu için pratikte 8 dakika ile 8 dakika 5 saniye arasıdır.
- Yenileme o sorgunun içinde yapılır: eski oturum bırakılır, yeniden giriş yapılır (kameraya 2 kısa istek) ve asıl sorgu yeni oturumla gider. Home Assistant bunu normal bir sorgu olarak görür; geçiş sırasında hiçbir şey "kullanılamıyor" olmaz. Sorgu yalnızca saniyenin bir kesri kadar uzar.
- Yenileme, istekleri sıraya koyan kilidin içinde yapılır. Tam o sırada bir anahtara basılırsa komut girişin bitmesini bekler ve yeni oturumla gider; eski oturumla hiçbir istek gitmez.
- Kameralar yalnızca art arda **başarısız** girişlerde hesabı geçici olarak kilitler. 8 dakikada bir yapılan başarılı giriş sorun değildir.

**Kurtarma ile birlikte:**
- Kamera oturumu yine de erken kapatırsa (`401`), sorular yeni girişle tekrar sorulur ve anahtarlar kullanılabilir kalır (bkz. [Hata olursa](#hata-olursa)).
- Böyle bir kurtarmadan sonra yenileme sayacı sıfırlanmaz; bir sonraki yenileme gereğinden biraz erken olabilir. Zararı yoktur: oturum hiçbir zaman entegrasyonun sandığından eski olmaz.
- Yeniden giriş tam o anda başarısız olursa (örneğin kamera o saniye ağdan düşmüşse) o sorgu başarısız olur ve anahtarlar bir sonraki sorguya kadar "kullanılamıyor" görünür. Bu, yenilemeden değil o anki bağlantı sorunundan kaynaklanır.

### Sorgulama
- 5 saniyede bir, TP-Link'teki gibi sorgulanır.
- Her sorguda kameraya **tek bir istek** gider: alarm ayarı ve bildirim ayarı birlikte okunur.
- TP-Link her sorguda kameranın tam güncellemesini yapar: hareket algılama, LED, gizlilik modu, saat gibi kendi varlıklarının bilgilerini okur. python-kasa bunları en fazla 5 soruluk paketlere böldüğü için bu genelde 2–3 istek demektir. Bu entegrasyon o bilgileri kullanmadığı için tam güncellemeyi yapmaz; kameraya TP-Link'ten daha az istek gider.
- Her kamera için bir kilit vardır. İstekler sırayla gider, kameraya aynı anda asla iki istek gitmez.
- Her kameranın kendi zamanlayıcısı vardır. Kameralar birbirini beklemez.

### Anahtara basınca
- Tek bir yazma isteği gider. Yazma başarısız olursa ekranda hata gösterilir, tekrar denenmez (TP-Link'teki gibi).
- Yazma başarılı olunca yeni durum hemen gösterilir; kamera hemen yeniden sorgulanmaz. Tapo uygulaması da böyle yapar: yazdıktan sonra kamerayı okumaz, bildiği durumu günceller. Böylece kamera yeni alarm ayarını uygularken ona soru sorulmaz. Sonraki normal sorgu (yazmadan 5 saniye sonra) durumu kameradan doğrular.

### Yeniden başlatma düğmesine basınca
- Yeniden başlatmadan sonra sorgu yapılmaz. Kamera bir süre "kullanılamıyor" görünür ve açılınca kendiliğinden geri gelir.

### Alarm ayarını okuma ve yazma
- Alarm ayarı yalnızca `getAlertConfig` ile okunur ve `setAlertConfig` ile yazılır. Bu, kameranın güncel alarm komutudur.
- Yazarken Tapo uygulaması gibi **yalnızca değişen alan** gönderilir: alarm açıp kapatınca sadece `{"enabled": "on"/"off"}`, ses/ışık değişince sadece `{"alarm_mode": [...]}`. Ses seviyesi, süre, ışık türü gibi diğer ayarlar yeniden yazılmaz. (1.6.6; Tapo uygulaması 3.21.112 incelenerek doğrulandı. Önceden ayarın tamamı geri gönderiliyordu.)
- Ses ve ışık anahtarları, kamera bildiriyorsa `sound_alarm_enabled` / `light_alarm_enabled` alanlarını okur.
- **1.6.5'te kaldırılan eski yöntemler:** `getLastAlarmInfo` + ham `set` ve `getAlarmConfig` / `setAlarmConfig` (pytapo ve Tapo Control'ün kullandığı yöntemler). Alarm bu eski yöntemle yazılırken kameranın servislerini yeniden başlattığı (RTSP'nin koptuğu) görüldü; `setAlertConfig` kullanan kamerada bu görülmedi.
- `getAlertConfig`'i desteklemeyen bir kamera yüklenmez. Log'a "does not answer getAlertConfig" hatası yazılır ve Home Assistant kurulumu tekrar tekrar dener.

### Hata olursa
TP-Link entegrasyonundaki gibi:
- python-kasa bağlantı hatası veya zaman aşımında aynı isteği en fazla 3 kez daha dener.
- Kamera cevap verip isteği reddederse (örneğin oturum kapandığı için `401`), sorular yeni girişle **tek tek tekrar sorulur**. Bu python-kasa'nın tam güncellemesinin (`device.update()`) yaptığının aynısıdır ve TP-Link'te hiçbir şeyin "kullanılamıyor" olmamasının sebebidir. Log'a bir uyarı yazılır, anahtarlar kullanılabilir kalır.
- Kamera hiç cevap vermezse (bağlantı hatası, zaman aşımı) tek tek tekrar yapılmaz; python-kasa zaten 3 kez denemiştir. Anahtarlar "kullanılamıyor" görünür ve bir sonraki sorgu zamanı beklenir.
- Kimlik doğrulama hatasında Home Assistant yeniden giriş bilgisi ister.

### IP değişikliği (MAC ile arama)
- TP-Link'teki gibi, Home Assistant açılışında ve 15 dakikada bir ağa bir arama yayını gönderilir. Yayın hiçbir cihaza giriş yapmaz.
- Kamera MAC adresiyle bulunur. IP'si değişmişse yeni adres kaydedilir ve entegrasyon yeni adresle yeniden bağlanır.
- Seçeneklerden kapatılabilir. Kapalı kameralar için arama yapılmaz; hiçbir kamerada açık değilse yayın da gönderilmez.

### Bağlantı tanılama
Her kameranın cihaz sayfasındaki **Tanılama** bölümünde iki sensör vardır. Kameraya ek istek göndermezler; entegrasyonun zaten gördüğünü gösterirler.

- **Bağlantı kuruldu:** Mevcut bağlantının kurulduğu an. Home Assistant bunu hem saat olarak hem de "x dakika önce" olarak gösterir; bu da bağlantının ne zamandır sürdüğüdür. Bağlantı koptuğunda "Bilinmiyor" olur, geri gelince yeni zamanı gösterir.
- **Kopma sayısı:** Home Assistant başladığından beri bağlantının kaç kez koptuğu. Art arda başarısız sorgular tek kopma sayılır. Home Assistant yeniden başlatıldığında (veya entegrasyon yeniden yüklendiğinde) 0'dan başlar; son kopmanın ayrıntıları da sıfırlanır.
  - `last_disconnect`: son kopmanın zamanı.
  - `last_disconnect_reason`: son kopmanın sebebi:
    - `reboot`: kamera ağda ama bağlantıyı reddediyor. Genellikle kamera yeniden başlıyordur.
    - `unreachable`: kamera ağda görünmüyor (Wi-Fi kopması, kapanma).
    - `timeout`: kamera zamanında cevap vermedi.
    - `auth`: giriş reddedildi.
    - `error`: kameranın hata cevabı gibi diğer durumlar.
  - `last_outage_seconds`: son kesintinin kaç saniye sürdüğü.
  - `down_since`: şu an kesinti varsa başladığı zaman.
- Sensörler kamera ulaşılamazken de görünür kalır, böylece kesinti anında da okunabilir.
- `401` gibi kurtarılan hatalar kopma sayılmaz; yalnızca anahtarların "kullanılamıyor" olduğu kesintiler sayılır.

**Kullanım:** Kopma zamanlarını alarm geçmişi, RTSP kaydı yapan sistemin log'u veya modemin log'u ile karşılaştırarak kameranın ne zaman ve neden koptuğunu görebilirsiniz.

### Yeniden başlatma
- python-kasa'nın yeniden başlatma komutu kameralarda çalışmadığı için TP-Link kameralarda bu düğmeyi göstermez.
- Bu entegrasyon Tapo Control'ün kameralar için kullandığı `rebootDevice` komutunu gönderir. Düğme TP-Link'in "Yeniden başlat" düğmesiyle aynı türde ve aynı "Tanılama" bölümündedir.
- TP-Link bu düğmeyi varsayılan olarak kapalı getirir; burada açık gelir.

### TP-Link'ten farkları
- Alarm, alarm sesi/ışığı ve bildirim anahtarları ile kameralar için yeniden başlatma düğmesi. TP-Link'te bunlar yok.
- Her sorguda tam güncelleme yerine yalnızca alarm ve bildirim ayarı okunur (1 istek; TP-Link'te genelde 2–3).
- Oturum süre dolmadan yenilenir (varsayılan 8 dakika). TP-Link oturumun dolmasını bekler; o sorgu önce başarısız olur, log'a hata yazılır ve sorular yeniden sorulur.
- Kamera hiç cevap vermediğinde sorular tek tek tekrar sorulmaz. TP-Link her soruyu tek tek tekrar dener, bu da ulaşılamayan bir kamerada sorguyu uzatır.
- Sorgulama aralığı, oturum yenileme ve MAC ile arama seçenekten değiştirilebilir. TP-Link'te bu ayarlar sabittir; sorgulama ve arama varsayılanları TP-Link'inkilerle aynıdır.
- Aynı kamera hem TP-Link entegrasyonuna hem bu entegrasyona ekliyse kameraya iki ayrı oturum açılır.

### Tapo uygulamasıyla karşılaştırma
Tapo uygulaması (Android 3.21.112) incelenerek karşılaştırıldı:
- **Giriş ve şifreleme:** Uygulama da python-kasa ile aynı yöntemi kullanır: `cnonce`/`nonce` ile giriş, `stok` belirteci, AES şifreli `securePassthrough`, her istekte artan `seq` ve `tapo_tag` başlıkları. Fark yok.
- **İstek biçimi:** Uygulama `setAlertConfig`'i de `multipleRequest` içinde gönderir, python-kasa da öyle. Fark yok.
- **Alarm yazma:** Uygulama yalnızca değişen alanı gönderir. 1.6.6'dan beri bu entegrasyon da öyle yapar.
- **Yazmadan sonra:** Uygulama kamerayı hemen okumaz, bildiği durumu günceller. Bu entegrasyon da artık öyle yapar (1.6.6'ya kadar 0,35 saniye sonra okuyordu).
- **Oturum:** Uygulama oturumu süre ile yenilemez; kamera `-40401` (oturum doldu) dediğinde yeniden giriş yapar. Bu entegrasyon bunu da yapar, ek olarak oturumu 8 dakikada bir önceden yeniler.
- **Zaman aşımı:** Uygulama 30 saniye bekler. Bu entegrasyon TP-Link gibi 5 saniye bekler.

## Sorun giderme
- **Anahtarlar sık sık "kullanılamıyor" oluyor:** Log'da `Connect call failed` veya `TimeoutError` varsa kamera o anda ağda değildir (Wi-Fi kopması veya yeniden başlama). Home Assistant'ın **Ping** entegrasyonuyla kameranın IP'si için bir sensör ekleyin; ping de düşüyorsa sorun Wi-Fi'da veya kameradadır. Tapo uygulamasından kameranın sinyal gücüne bakın.
- **Log'da `401` uyarısı var:** Kamera oturumu yenilemeden önce kapatmış demektir. Anahtarlar kullanılabilir kalır, çünkü sorular yeni girişle tekrar sorulur. Uyarılar sık geliyorsa seçeneklerden **oturumu yenileme aralığını** düşürün (örneğin 5 dakika). Yenileme kapalıysa (0) bu uyarı her 10 dakikada bir beklenir.
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
  python-kasa'nın kameraya giden istekleri de görmek için `kasa: debug` satırını ekleyin. Bu satır çok log üretir, sorunu bulduktan sonra kaldırın.

## Logo
Logo, Tapo Control entegrasyonunun logosudur. Home Assistant 2026.3 ve sonrası logoyu `brand/` klasöründen gösterir. Daha eski sürümlerde logo yerine boş simge görünür.

## Geliştirme
```bash
pip install pytest-homeassistant-custom-component python-kasa
pytest
```
