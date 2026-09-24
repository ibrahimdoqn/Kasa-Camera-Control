# Teknik mimari

Bu belge Kasa Camera Control'ün içini anlatır: hangi dosya ne yapar, kameraya hangi istekler gider, hatalar nasıl ele alınır. Kurulum ve kullanım için [README](README.md)'ye bakın.

## Genel bakış

```
Home Assistant
 ├─ config_flow.py   Kamera ekleme, şifre yenileme, yeniden yapılandırma, seçenekler
 ├─ __init__.py      Kurulum: giriş, MAC kontrolü, KLAP kaydı, koordinatörü başlatma
 ├─ coordinator.py   Düzenli sorgu, komutlar, giriş reddi sayacı
 ├─ api.py           pytapo sarmalayıcısı: giriş, okuma, yazma, hata sınıflandırma
 ├─ switch.py        Alarm, Alarm sesi, Alarm ışığı, Bildirimler anahtarları
 ├─ port_check.py    443 portu kontrolü, bağlantı durumu
 ├─ binary_sensor.py Bağlantı (bağlı mı, son kopma)
 ├─ sensor.py        Uptime (kesintisiz çalışmanın başlangıcı)
 ├─ button.py        Yeniden başlat düğmesi
 ├─ entity.py        Ortak cihaz bilgisi (model, yazılım sürümü, MAC)
 └─ const.py         Sabitler
        │
        ▼
pytapo 3.4.19 (Tapo Control'ün kütüphanesi)
        │  HTTPS, AES şifreli securePassthrough
        ▼
Tapo kamera (ev ağında, port 443)
```

Her kamera ayrı bir config entry'dir. Her birinin kendi pytapo bağlantısı (`Tapo` nesnesi), kendi koordinatörü ve kendi sorgu zamanlayıcısı vardır; kameralar birbirini beklemez.

## Bağlantı

### Giriş
`api.connect()` kameraya Tapo Control'ün `registerController`'ındaki ayarlarla bağlanır:

```python
Tapo(
    host,
    "admin",          # kullanıcı
    cloud_password,   # şifre: TP-Link bulut şifresi
    cloud_password,   # cloudPassword
    reuseSession=False,
    retryStok=False,
    isKLAP=is_klap,   # kayıtlıysa kayıtlı değer, yoksa None (pytapo bulur)
    hass=hass,
    printDebugInformation=...,  # pytapo logları → custom_components.tapo_kasa_alarm.api.pytapo
    printWarnInformation=...,
)
```

- **Kullanıcı ve şifre:** Tapo kameralar yerel girişte `admin` kullanıcısı için TP-Link hesabının şifresini kabul eder. Tapo Control'e bulut şifresi girildiğinde de böyle girilir.
- **Giriş adımları:** pytapo `cnonce` gönderir, kameradan `nonce` ve `device_confirm` alır, şifreyi doğrular (MD5 veya SHA256), `stok` belirtecini alır. Sonraki istekler `securePassthrough` ile AES şifreli gider. Her istekte artan `seq` ve `tapo_tag` başlıkları vardır.
- **`reuseSession=False`:** Her istek yeni bir HTTPS bağlantısıyla gider. Kamera oturumu (`stok`) korunur, her istekte yeniden giriş yapılmaz.
- **Bloklayan kütüphane:** pytapo senkron çalışır. Tüm çağrılar `hass.async_add_executor_job` ile arka plan iş parçacıklarında yapılır. pytapo'ya `hass` verildiği için kendi eşzamansız işlerini Home Assistant'ın döngüsünde çalıştırır ve istekleri kendi kilidiyle sırayla gönderir. Bir kameraya aynı anda iki istek gitmez.
- **Zaman aşımı:** pytapo'nun varsayılanı, 10 saniye.

### Kurulum sırası (`__init__.async_setup_entry`)
1. Bulut şifresi kayıtlı değilse Home Assistant hemen şifre ister.
2. `connect()` çalışır. Giriş reddedilirse [giriş reddi sayacı](#giriş-reddi) işler; bağlantı hatasında kurulum sonra tekrar denenir.
3. Giriş kabul edildi: giriş reddi sayacı sıfırlanır.
4. **MAC kontrolü:** Kameranın bildirdiği MAC, kayıtlı kamerayla (`unique_id`) karşılaştırılır. Farklıysa o IP'de başka bir cihaz vardır; bağlantı kapatılır ve kurulum sonra tekrar denenir. Kameralar karışmaz.
5. **KLAP kaydı:** Kameranın giriş türü (KLAP mı değil mi) kayıtlı değilse pytapo'nun bulduğu değer kaydedilir. Sonraki açılışlarda 2 saniyelik kontrol yapılmaz. Kayıt MAC kontrolünden sonra yapılır; başka bir cihaz bu değeri belirleyemez.
6. Koordinatör ilk sorguyu yapar. Başarısız olursa bağlantı kapatılır ve kurulum sonra tekrar denenir.
7. Anahtar, düğme ve sensörler eklenir.

### Oturum
Kameralar oturumu girişten yaklaşık 10 dakika sonra, trafik olsa da olmasa da kapatır. pytapo bunu `-40401` (oturum doldu) cevabından veya okunamayan cevaptan anlar, oturumu temizler, 1 saniye bekler, yeniden giriş yapar ve isteği bir kez tekrarlar. Anahtarlar "kullanılamıyor" olmaz. Tapo uygulaması da oturumu süreyle yenilemez, aynı şekilde çalışır.

Tapo kameralarda "çıkış yap" komutu yoktur. `api.close()` (kaldırmada) pytapo'nun oturum bilgisini siler; kamera eski oturumu kendi süresi dolunca unutur.

## Sorgulama

Koordinatör varsayılan olarak 5 saniyede bir (seçeneklerden en az 5) tek bir istek gönderir:

```json
{"method": "multipleRequest", "params": {"requests": [
  {"method": "getAlertConfig",
   "params": {"msg_alarm": {"name": ["chn1_msg_alarm_info"], "table": ["usr_def_audio"]}}},
  {"method": "getMsgPushConfig",
   "params": {"msg_push": {"name": ["chn1_msg_push_info"]}}}
]}}
```

Koordinatörün verisi:

```python
{
  "alarm": {                       # chn1_msg_alarm_info
    "enabled": "on",
    "alarm_mode": ["sound", "light"],
    "alarm_type": "3", "alarm_volume": "high", "alarm_duration": "0", "light_type": "1",
    "sound_alarm_enabled": "on", "light_alarm_enabled": "on",   # manuel alarmın ayarları
  },
  "push": {"notification_enabled": "on", "rich_notification_enabled": "off"},  # yoksa None
}
```

- `getAlertConfig` cevap vermezse veya `enabled` alanı yoksa sorgu başarısız sayılır. Böyle bir kamera hiç yüklenmez; log'a "does not answer getAlertConfig" yazılır.
- `getMsgPushConfig` hata dönerse `push` `None` olur. Kamera ilk sorguda bildirim ayarını bildirmiyorsa Bildirimler anahtarı hiç eklenmez.
- Tapo Control her sorguda `getMost` ile yaklaşık 90 komut okur (varsayılan 30 saniyede bir). Bu entegrasyon yalnızca kullandığını okur.

### Ses ve ışık
Ses ve ışık anahtarları yalnızca `alarm_mode` listesini okur. Tapo uygulaması da otomatik alarm için yalnızca bunu okur. `sound_alarm_enabled` / `light_alarm_enabled` alanları **manuel alarmın** (kameradan elle çalınan alarm) ayarlarıdır. Uygulama onları yalnızca manuel alarm için kullanır ve kamera onları `alarm_mode` değişince güncellemez. Bu entegrasyon onlara dokunmaz.

## Komutlar

### Akış (`coordinator._read_then_write`)
1. Kameranın o anki ayarı okunur (sorgudaki istekle aynı). Bilinen durum bir sorgu kadar eski olabilir; örneğin arada Tapo uygulamasından değişmiş olabilir.
2. İstenen durumla karşılaştırılır. **Değişen alan yoksa kameraya hiçbir şey yazılmaz.**
3. Değişen alan varsa yalnızca o gönderilir.
4. Yazılan alanlar bilinen duruma işlenir ve anahtar hemen yeni durumu gösterir. Kamera hemen yeniden okunmaz; sorgu zamanlayıcısı sıfırlanır ve sonraki normal sorgu durumu kameradan doğrular.

Alarm yazmak nadiren kameranın servislerini yeniden başlatır (443 portu bir süre bağlantıyı reddeder veya hiç cevap vermez, RTSP kopar). Bazen kamera yazmayı "tamam" diye kabul ettikten sonra çöker ve yeni ayarı kaydetmeden geri gelir; sonraki sorgu eski değeri okur ve anahtar ona döner. Bu kameranın firmware hatasıdır. Okumak bunu hiç yapmadı. Bu yüzden gereksiz yazma yapılmaz ve kamera yeni ayarı uygularken ona soru sorulmaz.

### Alarm (`api.set_alarm`)
Tapo uygulamasıyla aynı biçimde, `setAlertConfig` ile yalnızca değişen alan gönderilir:

```json
{"method": "setAlertConfig", "params": {"msg_alarm": {"chn1_msg_alarm_info": {"enabled": "on"}}}}
{"method": "setAlertConfig", "params": {"msg_alarm": {"chn1_msg_alarm_info": {"alarm_mode": ["light"]}}}}
```

(pytapo her ikisini de `multipleRequest` içinde gönderir; Tapo uygulaması da öyle.)

- Ses seviyesi, süre, alarm sesi türü, ışık türü yeniden yazılmaz.
- Ses ve ışığın ikisi birden kapatılamaz; kamera en az birini zorunlu tutar. Denenirse ekranda hata gösterilir, kameraya bir şey gitmez.
- Eski komutlar (`getLastAlarmInfo` + ham `set`, `getAlarmConfig` / `setAlarmConfig`) kullanılmaz. Tapo Control bunları `getAlertConfig`'ten önce dener. pytapo'nun eski `setAlarm` komutu ayrıca her seferinde alarm sesi ve ışık türünü `"0"` yapar.

### Bildirim (`api.set_notifications`)
pytapo'nun `setNotificationsEnabled` komutu kullanılır; yalnızca `notification_enabled` gönderilir:

```json
{"method": "setMsgPushConfig", "params": {"msg_push": {"chn1_msg_push_info": {"notification_enabled": "off"}}}}
```

### Yeniden başlatma (`api.reboot`)
pytapo'nun `reboot` komutu: `rebootDevice` + `{"system": {"reboot": "null"}}`, Tapo Control'deki gibi. Komuttan sonra ayrıca sorgu yapılmaz; normal sorgular devam eder, kamera açılana kadar anahtarlar "kullanılamıyor" görünür.

## Hata yönetimi

`api.py` pytapo'nun düz `Exception`'larını iki türe çevirir:

| Tür | Ne zaman |
|---|---|
| `AuthenticationError` | Mesajda "Invalid authentication" geçiyorsa (giriş reddedildi) |
| `CameraError` | Diğer her şey: bağlantı hatası, zaman aşımı, kameranın hata cevabı, "Temporary Suspension" |

Orijinal hata `__cause__` olarak saklanır ve log'da görünür.

| Nerede | `CameraError` | `AuthenticationError` |
|---|---|---|
| Kurulum | sonra tekrar denenir | [giriş reddi sayacı](#giriş-reddi) |
| Sorgu | anahtarlar "kullanılamıyor", sonraki sorgu beklenir | [giriş reddi sayacı](#giriş-reddi) |
| Komut | ekranda hata | ekranda hata (şifre sorulmaz) |

pytapo kendi içinde bağlantı hatasında ve oturum dolduğunda isteği bir kez tekrarlar; bu tekrarla kurtarılan hatalar entegrasyona hiç ulaşmaz.

### Giriş reddi
Kameralar geçerli bir girişi de kısa süre reddedebilir, örneğin yeniden başlarken. Tapo Control'deki gibi art arda 3 red tolere edilir (`AUTH_RETRIES = 3`):

- Sayaç `hass.data[DOMAIN][entry_id]`'de tutulur; kurulum denemeleri arasında da korunur.
- Kurulumda red: 1–3. red "sonra tekrar dene", 4. red "şifreyi iste".
- Sorguda red: 1–3. red anahtarları "kullanılamıyor" yapar, 4. red şifreyi ister.
- Kabul edilen bir giriş veya başarılı bir sorgu sayacı sıfırlar.
- Komutlardaki red sayılmaz ve şifre sordurmaz.
- Kamera çok sayıda başarısız girişten sonra kendini geçici olarak kilitlerse ("Temporary Suspension") bu `CameraError` sayılır: şifre sorulmaz, kilit açılınca tekrar denenir.

## Bağlantı durumu (port kontrolü)

`port_check.PortCheckCoordinator` her kamera için ayrı çalışır. Kamera sorgularından tamamen bağımsızdır.

- **Kontrol:** Kameranın 443 portuna TCP bağlantısı açılır ve hemen kapatılır (`asyncio.open_connection`, 2 saniye zaman aşımı). TLS el sıkışması, giriş ve veri yoktur.
- **Aralık:** Seçeneklerdeki *Bağlantı kontrol aralığı*, varsayılan 1 saniye (1–60). Değişiklik yeniden bağlanmadan uygulanır.
- **Sonuçlar:**

  | Sonuç | Anlamı | Sebep |
  |---|---|---|
  | Bağlantı kabul edildi | Kameranın ana programı (API, RTSP, alarm) çalışıyor | — |
  | `ConnectionRefusedError` | Kamera ağda, ana program çökmüş veya yeniden başlıyor | `restarting` |
  | Zaman aşımı veya diğer `OSError` | Kamera ağda değil | `unreachable` |

- **Kopma:** Tek başarısız kontrol takılma sayılır; art arda 2 başarısız kontrolde (`FAILURES_TO_DISCONNECT`) bağlantı kesik olur. Kesinti başlangıcı, son kopma ve sebep ilk başarısız kontrolden alınır. İlk kontrol başarısızsa bağlantı hemen kesik gösterilir.
- **Geri geliş:** İlk başarılı kontrolde bağlı olur, kesinti süresi hesaplanır, **Uptime** şimdiye ayarlanır.
- **Kayıt yükü:** Durum yalnızca bağlanma ve kopma anlarında değişir (`always_update=False`); saniyede bir kontrol kayıt defterine her saniye yeni durum yazmaz. **Uptime** bir zaman damgasıdır, Home Assistant'ın Uptime entegrasyonu gibi.
- **Sınırlar:** Kontrol aralığından kısa kopmalar görünmeyebilir. Home Assistant yeniden başladığında Uptime ölçümü baştan başlar; kameranın kendi açık kalma süresi okunmaz.

## Yapılandırma

- **Config entry verisi:** `host`, `cloud_password`, `is_klap`.
- **Seçenekler:** `scan_interval` (saniye, en az 5, varsayılan 5) ve `port_check_interval` (saniye, 1–60, varsayılan 1). Değişiklikler yeniden bağlanmadan uygulanır.
- **Benzersiz kimlik:** Kameranın MAC adresi (`aa:bb:cc:dd:ee:ff`). MAC yoksa `dev_id`, o da yoksa IP.
- **Kamera ekleme:** Bir kez giriş yapılır, MAC, ad ve KLAP türü alınır, bağlantı kapatılır. Aynı kamera zaten ekliyse yalnızca IP'si güncellenir.
- **Şifre yenileme:** Yeni şifreyle giriş denenir; başarılıysa kaydedilir ve entegrasyon yeniden yüklenir.
- **Yeniden yapılandırma:** IP ve şifre değiştirilebilir. Yeni IP'de başka bir kamera (farklı MAC) cevap verirse değişiklik kaydedilmez.

## Tapo uygulamasıyla karşılaştırma

Tapo Android uygulaması 3.21.112 incelenerek karşılaştırıldı.

| Konu | Tapo uygulaması | Bu entegrasyon |
|---|---|---|
| Giriş ve şifreleme | `admin` + şifre, AES `securePassthrough`, `seq`, `tapo_tag` | aynı (pytapo) |
| İstek biçimi | `multipleRequest` | aynı |
| Alarm aç/kapat | yalnızca `{"enabled": ...}` | aynı |
| Ses/ışık yazma | yalnızca `{"alarm_mode": [...]}` | aynı |
| Ses/ışık okuma | yalnızca `alarm_mode` | aynı |
| Yazmadan sonra | kamerayı okumaz | aynı |
| Oturum | `-40401` gelince yeniden giriş | aynı |
| Alarm okuma isteği | `{"name": ["chn1_msg_alarm_info"]}` | ek olarak `"table": ["usr_def_audio"]` |
| Bildirim yazma | `notification_enabled` + `rich_notification_enabled` | yalnızca `notification_enabled` |
| Yeniden başlatma | `{"system": {"reboot": {}}}` | `{"system": {"reboot": "null"}}` (pytapo) |
| Zaman aşımı | 30 saniye | 10 saniye (pytapo) |
| Okuma zamanı | ayar ekranı açıldığında | düzenli sorgu |

## Tapo Control ile karşılaştırma

| Konu | Tapo Control | Bu entegrasyon |
|---|---|---|
| Kütüphane ve bağlantı ayarları | pytapo, `reuseSession=False`, `retryStok=False` | aynı |
| Giriş (bulut şifresiyle) | `admin` + bulut şifresi | aynı (kamera hesabı yok) |
| KLAP türü | eklerken bulunur, kaydedilir | aynı |
| Giriş reddi | 3 red tolere edilir | aynı |
| Sorgu | `getMost`, ~90 komut, 30 saniye | 1 istek, 5 saniye (ayarlanabilir) |
| Alarm komutu | önce eski komutlar; `setAlertConfig`'te tüm ayar | yalnızca `setAlertConfig`, yalnızca değişen alan |
| Yazmadan önce/sonra | önce okumaz; sonra `getMost` ile yeniler | önce okur, gerekmiyorsa yazmaz; sonra okumaz |
| Özellikler | görüntü, hareket, PTZ, ... | yalnızca alarm, bildirim, yeniden başlatma, bağlantı tanılama |

## Testler

`tests/test_alarm.py` gerçek kamera yerine `FakeTapo` kullanır. `FakeTapo` pytapo'nun `Tapo` nesnesini taklit eder ve gerçek kameralar gibi davranır; örneğin `setAlertConfig` ile gelen alanları mevcut ayara ekler, `sound_alarm_enabled` / `light_alarm_enabled` alanlarını değiştirmez.

Testlerin kapsadıkları:
- **Kurulum ve komutlar:** kurulum, anahtarlar, gönderilen paketler, yazmadan önce okuma ve gereksiz yazma yapılmaması.
- **Bağlantı ayarları:** Tapo Control'le aynı pytapo ayarları, KLAP kaydı ve başka cihazın KLAP türünün kaydedilmemesi.
- **Formlar:** kamera ekleme, hatalar, şifre yenileme, yeniden yapılandırma ve seçenekler.
- **Hata yönetimi:** kurulumda ve sorguda giriş reddi toleransı.
- **Kamera ulaşılamazken:** anahtarların "kullanılamıyor" olması ve geri gelmesi; eski bağlantı sensörlerinin kaldırılması.
- **Bağlantı kontrolü:** port sonuçlarının sınıflandırılması, tek takılmanın kopma sayılmaması, art arda iki hatada kopma, geri geliş ve Uptime, başlangıçta kopuk kamera, kontrol aralığı seçeneği.

```bash
pip install pytest-homeassistant-custom-component pytapo==3.4.19
pytest
```
