# dikeriz studio

Yatay (16:9) videolarını **dikey (9:16) kısa videolara** çeviren ücretsiz bir program. Reels, Shorts ve TikTok için hazır video verir.

Videoyu bırakırsın; program konuşmayı dinler, en iyi anları bulur ve her biri için üstünde başlık, altında altyazı olan dikey bir video hazırlar.

- Tamamen **kendi bilgisayarında** çalışır. Videoların hiçbir yere yüklenmez.
- Hesap, üyelik ya da API anahtarı gerekmez.
- Windows, macOS ve Linux'ta çalışır.

---

## 1. Gerekenler

**Python 3.9 veya üstü.** Bilgisayarında yoksa [python.org/downloads](https://www.python.org/downloads/) adresinden indir.

> Windows'ta kurulum ekranının altındaki **"Add python.exe to PATH"** kutusunu mutlaka işaretle.

Başka bir şey kurman gerekmez. Diğer her şeyi program kendisi kurar.

---

## 2. Kurulum

### Windows

1. Bu sayfada yeşil **Code** düğmesine bas, **Download ZIP** ile indir ve ZIP'i bir klasöre çıkar.
2. Klasördeki **`Kisayol-Olustur.vbs`** dosyasına çift tıkla. Masaüstüne ve Başlat menüsüne **Dikeriz Studio** kısayolu eklenir.
3. Masaüstündeki **Dikeriz Studio** kısayoluna çift tıkla.

İlk açılışta gerekli paketler kurulur. Bu 2–5 dakika sürer ve bir pencerede ilerlemesi görünür. Bitince program tarayıcında açılır.

Sonraki açılışlarda pencere çıkmaz; program birkaç saniyede doğrudan tarayıcıda açılır.

### macOS / Linux

ZIP'i çıkardığın klasörde bir terminal aç ve şunu çalıştır:

```bash
./dikeriz_studio.sh
```

İlk açılışta paketler kurulur, sonra program tarayıcında açılır.

---

## 3. Kullanım

1. **Videoyu ver.** Videoyu sayfadaki kesikli çizgili alana sürükleyip bırak ya da alana tıklayıp seç.
2. **▶ hepsini çalıştır** düğmesine bas. Program sırayla şu üç adımı yapar:
   - **küçült:** Videonun hafif bir kopyasını oluşturur.
   - **analiz:** Konuşmayı yazıya döker ve en iyi anları bulur.
   - **dikey çıkar:** Seçilen anları dikey video olarak hazırlar.

   Her adımın ilerlemesini çubuklardan takip edebilirsin.
3. **Videolarını izle.** Hazır olan videolar sayfanın altındaki **dikey videolar** bölümünde oynatılabilir. **klasörü aç** düğmesi dosyaların bulunduğu klasörü açar.

### Klipleri kendin seçmek istersen

1. **▶ hepsini çalıştır**'a basmadan önce **"analizden sonra seçimimi bekle"** kutusunu işaretle.
2. Analiz bitince **aday anlar** tablosunda:
   - İstediğin klipleri işaretle, istemediklerinin işaretini kaldır.
   - Başlangıç ve bitiş zamanlarını değiştir (`5:42.5` ya da `342.5` gibi yazabilirsin).
   - Başlığı yeniden yaz. Turuncu olmasını istediğin kelimeleri yıldız içine al: `vazgeçme, sadece *bir yerden başla*`
3. **dikey çıkar** satırındaki **yalnız bunu** düğmesine bas.

---

## 4. Ayarlar

**ayarlar** bölümünü açarak düzenlenir. Her ayarın yanındaki **i** düğmesi, o ayarın açıklamasını ve bir örneğini gösterir.

| Ayar | Ne işe yarar |
|---|---|
| sürüklenen videoların çalışma klasörü | Sürükle-bırak ile verilen videoların işlendiği ve kaydedildiği yer |
| klip sayısı | Kaç klip otomatik seçilsin |
| en kısa / en uzun klip | Kliplerin süre aralığı (saniye) |
| küçültme yüksekliği | Hafif kopyanın çözünürlüğü (1080 önerilir) |
| küçültme kalitesi | Hafif kopyanın sıkıştırması (26 önerilir) |
| konuşma modeli | Yazıya dökmenin isabeti ve hızı (`large-v3-turbo` önerilir) |
| baştan atla | Videonun başındaki intro kısmı kliplere girmesin diye atlanacak saniye |
| alttaki imza | Videonun altına yazılan kullanıcı adın, örn. `@kullaniciadi` (boş bırakırsan yazılmaz) |
| yazı tipi | Başlık, altyazı ve imzanın fontu. **+ yeni font ekle** ile kendi fontunu ekleyebilirsin |
| konuşma dili | Videoda konuşulan dil |
| renkler | Zemin, yazı, vurgu ve imza rengi |

---

## 5. Sık sorulan sorular

**Videolarım nereye kaydediliyor?**
- Videoyu **tıklayıp seçtiysen** videonun yanındaki `Dikey_<video adı>` klasörüne kaydedilir.
- **Sürükle-bırak** yaptıysan ayarlardaki çalışma klasörüne kaydedilir (varsayılan: `Videolar/DikerizStudio/<video adı>`).

Dosyalar `dikey_01.mp4`, `dikey_02.mp4` gibi adlandırılır.

**Videom internete yükleniyor mu?**
Hayır. Her şey senin bilgisayarında olur. Sürükle-bırak yaptığında video, aynı bilgisayardaki programa kopyalanır. Küçültme bitince bu kopya silinir.

**İnternet bağlantısı gerekiyor mu?**
Sadece ilk kurulumda (paketler için) ve ilk analizde (konuşma modeli, yaklaşık 1,6 GB, bir kez indirilir) gerekir. Sonrasında internetsiz çalışır.

**Bir analiz ne kadar sürer?**
Bilgisayarına göre değişir. Örnek bir masaüstü bilgisayarda yaklaşık 7 dakikalık bir video 1,5 dakikada yazıya döküldü.

**Altyazıda adım yanlış yazılıyor, ne yapmalıyım?**
**alttaki imza** ayarına kullanıcı adını yaz (örn. `@berkcandikeriz`). Program adını buradan tanır ("Berk Can Dikeriz") ve altyazıdaki yanlış yazımları kendisi düzeltir. Emin olamadığı kelimeleri de ikinci kez dinleyerek düzeltmeye çalışır.

**Kendi fontumu nasıl eklerim?**
**ayarlar → yazı tipi → + yeni font ekle** yolunu izle ve `.ttf` ya da `.otf` dosyasını açılan alana bırak. Aynı fontun farklı kalınlıklarını (Light, Medium, Bold…) birlikte eklersen program başlık için kalın, imza için ince olanı kendisi seçer. Fontta Türkçe harfler eksikse uyarı verir.

**Yüzüm kadrajın dışında kalıyor.**
Program yüzü takip ederek kırpar. Ekran kaydı gibi yüz olmayan sahnelerde görüntünün ortasını alır.

**Programı nasıl kapatırım?**
Sayfanın sağ üstündeki **kapat** düğmesine bas. Sadece tarayıcı sekmesini kapatırsan program arka planda açık kalır; kısayola tekrar tıkladığında aynı program açılır.

**"Port kullanılıyor" hatası alıyorum.**
Başka bir program 8765 portunu kullanıyor. Programı farklı bir portla başlat: `DikerizStudio.bat --port 8766`

**Program açılmıyor.**
Klasördeki **`DikerizStudio.bat`** dosyasına çift tıkla. Bu yolla açılan pencerede hata mesajını görebilirsin. Hata kaydı ayrıca `studio_hata.log` dosyasına yazılır.

**Programı nasıl silerim?**
Program klasörünü ve masaüstündeki kısayolu sil. Konuşma modeli yer kaplamasın istersen `Kullanıcı klasörün/.cache/huggingface` klasörünü de silebilirsin. Ürettiğin videolar kendi klasörlerinde kalır.

---

## 6. Güvenlik

- Program sadece senin bilgisayarından açılabilir (`127.0.0.1`); ağdaki başka cihazlar erişemez.
- Her açılışta yeni bir gizli anahtar üretilir. Başka bir web sitesi programına komut gönderemez.
- Sadece video (`.mp4`, `.mov`, `.mkv`, `.m4v`) ve font (`.ttf`, `.otf`) dosyaları kabul edilir. Dosyalar türü ve boyutu kontrol edilerek alınır.
- Program diskini taramaz; yalnızca senin verdiğin dosyalarla çalışır.
- Kişisel ayarların (`ayarlar.json`) ve eklediğin fontlar (`fonts/user/`) GitHub'a yüklenmez.

Bir güvenlik sorunu bulursan lütfen herkese açık issue açmak yerine GitHub'daki **Security → Report a vulnerability** bölümünden bildir.

---

## 7. Kullanılan araçlar ve lisans

- Konuşmayı yazıya dökme: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), Whisper modelleri (MIT)
- Yüz takibi: [OpenCV](https://opencv.org) (Apache 2.0)
- Görüntü ve yazı: [Pillow](https://python-pillow.org) (MIT-CMU), NumPy (BSD)
- Video işleme: FFmpeg, [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) ile gelir (BSD; içerdiği FFmpeg LGPL/GPL)
- Varsayılan font: Poppins, [SIL Open Font License 1.1](fonts/OFL.txt). Eklediğin fontlar kendi lisanslarına tabidir.

Program kodu [MIT lisansı](LICENSE) ile yayınlanmıştır © 2026 Berk Can Dikeriz.
