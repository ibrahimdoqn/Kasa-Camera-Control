# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

- `pytapo` yerine, Home Assistant'ın resmi **TP-Link Smart Home** entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır.
- Kameraya resmi TP-Link entegrasyonunun bağlandığı gibi bağlanır. Her sorguda yalnızca alarm ve bildirim ayarını, tek bir istekle okur.
- Resmi entegrasyonda olmayan otomatik alarm ve bildirim anahtarlarını ekler.

C520WS ve C510W için yazıldı. `msg_alarm` destekleyen diğer Tapo kameralarda da çalışmalı.

Tamamen **yerel** çalışır: kameralarla ev ağı içinden konuşur, TP-Link bulutuna istek göndermez. Ayrıntılar için [Yerel çalışma](#yerel-çalışma) bölümüne bakın.

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

### Anahtara basınca: yazma kuyruğu
Anahtar değişiklikleri bir kuyruktan geçer. İstenen değer, kamera onu okuyup doğrulayana kadar kuyrukta tutulur.

- **Hemen yazılır:** Anahtara basınca istenen değer kuyruğa alınır ve hemen kameraya gönderilir. TP-Link'teki gibi 0,35 saniye sonra kamera yeniden sorgulanır.
- **Aynı değer yazılmaz:**
  - Kamerada zaten o değer varsa hiç yazılmaz.
  - Aynı ayar için aynı değer zaten kuyruktaysa tekrar gönderilmez.
- **Doğrulama:** Her sorguda kameradan okunan değer istenenle karşılaştırılır. Aynıysa ayar kuyruktan çıkar.
  - Doğrulama yalnızca yazmadan **sonra** okunan veriyle yapılır. Yazma sırasında zaten okunmakta olan eski veri yüzünden tekrar yazılmaz.
- **Düzeltme:** Kamera yazmayı kabul edip değeri uygulamadıysa ayar sonraki sorgularda yeniden yazılır. En fazla 3 kez denenir; kamera yine de tutmazsa vazgeçilir ve log'a hata yazılır.
- **Geçici hata:** Oturum kapanması (`401`), zaman aşımı ve bağlantı hatalarında kullanıcıya hata gösterilmez. Ayar kuyrukta kalır, log'a uyarı yazılır ve bir sonraki sorguda (5 saniye sonra) tekrar denenir. Kamera ağdan düşmüşse, geri geldiğinde yazılır.
- **Kalıcı hata:** Kamera komutu reddederse (örneğin `PROTOCOL_FORMAT_ERROR`) veya istek geçersizse (ses ve ışığın ikisi birden kapatılırsa) ekranda hata gösterilir ve ayar kuyruktan çıkarılır.
- **Son değer geçerli:** Aynı ayara art arda basılırsa yalnızca son değer yazılır. Alarm, alarm sesi ve alarm ışığı tek bir yazmada birlikte gönderilir.
- **Görünüm:** Bekleyen bir yazma varken anahtar istenen değeri gösterir. `pending_write` özniteliği `true` olur; kamera doğrulayınca `false` olur.
- **Kimlik doğrulama hatası:** Ayar kuyrukta kalır ve Home Assistant yeniden giriş bilgisi ister.
- Kuyruk bellekte tutulur. Home Assistant yeniden başlarsa bekleyen yazmalar silinir.

### Yeniden başlatma düğmesine basınca
- Kuyruktan geçmez, tek seferlik bir komuttur.
- Yeniden başlatmadan sonra sorgu yapılmaz. Kamera bir süre "kullanılamıyor" görünür ve açılınca kendiliğinden geri gelir.

### Alarm ayarını okuma
- Kamera modeline ve yazılımına göre alarm ayarı farklı komutlarla okunur (`getLastAlarmInfo`, `getAlertConfig`, `getAlarmConfig`).
- Hangisinin desteklendiği bilinmiyorsa bu üç komut sırayla denenir. Çalışan komut hatırlanır, sonraki sorgular yalnızca onu kullanır.

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

### Yeniden başlatma
- python-kasa'nın yeniden başlatma komutu kameralarda çalışmadığı için TP-Link kameralarda bu düğmeyi göstermez.
- Bu entegrasyon Tapo Control'ün kameralar için kullandığı `rebootDevice` komutunu gönderir. Düğme TP-Link'in "Yeniden başlat" düğmesiyle aynı türde ve aynı "Tanılama" bölümündedir.
- TP-Link bu düğmeyi varsayılan olarak kapalı getirir; burada açık gelir.

### TP-Link'ten farkları
- Alarm, alarm sesi/ışığı ve bildirim anahtarları ile kameralar için yeniden başlatma düğmesi. TP-Link'te bunlar yok.
- Her sorguda tam güncelleme yerine yalnızca alarm ve bildirim ayarı okunur (1 istek; TP-Link'te genelde 2–3).
- Anahtar değişiklikleri kuyruktan geçer, doğrulanır ve başarısız olursa tekrar denenir. TP-Link'te komut bir kez gönderilir, hata olursa ekranda gösterilir.
- Oturum süre dolmadan yenilenir (varsayılan 8 dakika). TP-Link oturumun dolmasını bekler; o sorgu önce başarısız olur, log'a hata yazılır ve sorular yeniden sorulur.
- Kamera hiç cevap vermediğinde sorular tek tek tekrar sorulmaz. TP-Link her soruyu tek tek tekrar dener, bu da ulaşılamayan bir kamerada sorguyu uzatır.
- Sorgulama aralığı, oturum yenileme ve MAC ile arama seçenekten değiştirilebilir. TP-Link'te bu ayarlar sabittir; sorgulama ve arama varsayılanları TP-Link'inkilerle aynıdır.
- Aynı kamera hem TP-Link entegrasyonuna hem bu entegrasyona ekliyse kameraya iki ayrı oturum açılır.

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
- **Anahtar istenen değeri gösteriyor ama `pending_write: true` kalıyor:** Yazma henüz kamera tarafından doğrulanmadı. Log'da `writing ... failed, will retry` uyarısı varsa kameraya o an ulaşılamıyordur; ulaşılınca yazılır. `does not keep ... giving up` hatası varsa kamera ayarı kabul edip uygulamamıştır.
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
