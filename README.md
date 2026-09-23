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

## Varlıklar
| Varlık | Açıklama |
|---|---|
| `switch.<kamera>_alarm` | Otomatik alarmı açar/kapatır (Tapo uygulamasındaki anahtar) |
| `switch.<kamera>_alarm_sesi` | Alarm çalınca ses kullanılsın mı |
| `switch.<kamera>_alarm_isigi` | Alarm çalınca ışık kullanılsın mı |
| `switch.<kamera>_bildirimler` | Tapo uygulaması bildirimlerini açar/kapatır |
| `switch.<kamera>_zengin_bildirimler` | Görüntülü (zengin) bildirimler |
| `siren.<kamera>_siren` | Sireni hemen çalar/durdurur (manuel alarm) |

Ses veya ışıktan en az biri açık kalmalıdır; kamera bunu zorunlu tutar.

Siren için kameralar farklı komutlar kabul eder. Entegrasyon Tapo Control'deki sırayla `manual_msg_alarm` ve `setSirenStatus` komutlarını dener ve çalışanı hatırlar.

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
