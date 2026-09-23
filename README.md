# Kasa Camera Control

<img src="custom_components/tapo_kasa_alarm/brand/icon.png" width="96" align="right">

Tapo kameraların **otomatik alarm** ve **bildirim** ayarlarını Home Assistant'tan açıp kapatan bir HACS entegrasyonu.

`pytapo` yerine, Home Assistant'ın resmi **TP-Link Smart Home** entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır. Bağlantı resmi entegrasyondaki gibi kurulur (Tapo kamera / AES / HTTPS).
Resmi entegrasyon otomatik alarm anahtarını sunmadığı için bu entegrasyon yalnızca o eksik parçayı ekler.

C520WS ve C510W için yazıldı. `msg_alarm` destekleyen diğer Tapo kameralarda da çalışmalı.

## Kamerayı yormamak için neler yapıyor
- Kamera başına **tek oturum** açık tutulur. Her sorguda yeniden giriş yapmaz.
- İstekler sırayla gönderilir, kameraya aynı anda asla iki istek gitmez.
- Her sorgulamada yalnızca alarm ve bildirim ayarı tek bir istekte okunur. Varsayılan aralık 60 sn, seçeneklerden değiştirilebilir (en az 15 sn).
- Görüntü akışı, ONVIF, anlık görüntü, olay dinleme, güncelleme kontrolü **yoktur**.

## Sorgulama nasıl çalışıyor

**Her sorgulama tek bir istek**
- Varsayılan olarak 60 saniyede bir sorgu yapılır. Süre seçeneklerden değiştirilebilir, en az 15 saniye.
- Her sorguda kameraya tek bir HTTPS isteği gider. Alarm ayarı ve bildirim ayarı bu isteğin içinde birlikte okunur.
- İki sorgu arasında kameraya hiçbir istek gitmez.

**Sıralama ve bekleme**
- Her kamera için bir kilit vardır. Bir istek bitmeden aynı kameraya ikinci istek başlamaz.
- Sorgulama sürerken bir anahtara basılırsa, yazma isteği sorgulamanın bitmesini bekler, sonra gider.
- Home Assistant bir sorgu bitmeden yenisini başlatmaz.
- Normal çalışmada yapay bir bekleme yoktur.

**Anahtara basınca**
- Tek bir yazma isteği gider.
- Yazmadan sonra ayrıca okuma yapılmaz. Yeni durum doğrudan yazılan değerden yansır ve sıradaki sorgu zamanı baştan sayılır.

**İlk açılışta**
- Kamera modeline ve yazılımına göre alarm ayarı farklı komutlarla okunur (`getLastAlarmInfo`, `getAlertConfig`, `getAlarmConfig`).
- Hangisinin desteklendiği bilinmiyorsa bu üç komut sırayla, birer istek olarak denenir. Çalışan komut hatırlanır, sonraki sorgular yalnızca onu kullanır.
- Bu deneme Home Assistant her açıldığında veya entegrasyon yeniden yüklendiğinde bir kez olur.

**Hata olursa**
- Her istek için 10 saniyelik zaman aşımı vardır.
- python-kasa bağlantı hatası veya zaman aşımında aynı isteği en fazla 3 kez daha dener. Zaman aşımından sonra denemeler arasında 1 saniye bekler. Kimlik doğrulama hatasında tekrar denemez.
- Sorgu yine de başarısız olursa anahtarlar "kullanılamıyor" görünür ve bir sonraki sorgu zamanı beklenir. Hızlı art arda deneme yoktur.
- Kötü durumda tek bir sorgu kameraya en fazla 4 deneme olarak gidebilir. Bu denemeler de sıralıdır.

**Oturum**
- Kameraya bir kez giriş yapılır ve oturum açık tutulur. Her sorguda yeniden giriş yapılmaz.
- Oturumun süresi dolarsa python-kasa kendisi yeniden giriş yapar.

**Birden fazla kamera**
- Her kameranın kendi zamanlayıcısı ve kilidi vardır. Kameralar birbirini beklemez, ama her biri kendi içinde sıralı çalışır.

**Kamera zorlanırsa**
- Sorgulama aralığını 120 veya 300 saniyeye çıkarın.
- Bunun tek bedeli, alarm Tapo uygulamasından değiştirildiğinde Home Assistant'ın bunu daha geç görmesidir. Home Assistant'tan yapılan değişiklikler anında yansır.

## python-kasa ve resmi TP-Link entegrasyonu
- Entegrasyon, Home Assistant'ın resmi TP-Link entegrasyonunun kullandığı **python-kasa** kütüphanesini kullanır. Bu kütüphane Home Assistant ile birlikte kurulu gelir, ayrıca bir şey indirilmez.
- Resmi TP-Link entegrasyonunun kendisini kullanmaz. Kameraya kendi bağlantısını açar ve TP-Link entegrasyonunun kurulu olmasını gerektirmez.
- Aynı kamera hem TP-Link entegrasyonuna hem bu entegrasyona ekliyse kameraya iki ayrı oturum açılır.

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki anahtar) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |

Ses veya ışıktan en az biri açık kalmalıdır; kamera bunu zorunlu tutar.


Logo, Tapo Control entegrasyonunun logosudur. Logoyu Home Assistant 2026.3 ve sonrası `brand/` klasöründen gösterir.

## Kurulum (HACS)
1. HACS → Integrations → sağ üst menü → **Custom repositories**
2. Depo: `https://github.com/ibrahimdoqn/TapoKamera`, kategori: **Integration**
3. **Kasa Camera Control** kurun ve Home Assistant'ı yeniden başlatın.
4. Ayarlar → Cihazlar ve Hizmetler → **Entegrasyon ekle** → *Kasa Camera Control*
5. Kameranın IP adresi ile **TP-Link bulut hesabınızın e-posta ve şifresini** girin. Tapo uygulamasında ve resmi TP-Link entegrasyonunda kullandığınız hesap budur, kamera hesabı (RTSP kullanıcı adı) değil.

> Kameraya sabit IP (DHCP rezervasyonu) vermeniz önerilir.
> Çökmelerden kurtulmak için eski `tapo_control` kurulumunu kaldırın. Aynı kameraya iki entegrasyonun birlikte bağlanması da kameraya yük bindirir.

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

## Geliştirme
```bash
pip install pytest-homeassistant-custom-component python-kasa
pytest
```
