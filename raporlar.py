# -*- coding: utf-8 -*-
"""
SKS Tıbbi Kayıt ve Arşiv Raporları.

Sağlıkta Kalite Standartları (SKS) göstergeleri için arşiv birimi listeleri:
güvenli cerrahi kontrol listesi, eksiksiz hasta dosyası oranı, evrak durumu
ve hasta kalış süreleri. Tüm sorgular yalnızca okuma (SELECT) yapar.

Sorgular HBYS'nin Oracle veritabanındaki HASTANE şemasına göre yazılmıştır.
Farklı bir HBYS'de tablo / kolon adlarını kendi şemanıza göre uyarlayın.
"""
from datetime import timedelta

import demo

SAYFA = {"baslik": "SKS Arşiv Raporları", "alt": "Tıbbi kayıt ve arşiv gösterge listeleri",
         "ikon": "🗂️", "renk1": "#0d2e4a", "renk2": "#0f8b8d"}

# Takvim günü olarak kalış: aynı gün = 0, ertesi gün = 1 (eksi değerler 0 sayılır)
TAKVIM_GUN = "GREATEST(TRUNC(P.CTARIH) - TRUNC(P.GTARIH), 0)"

# Çıkış kaydındaki sorun (yataklı servis olmadığı için hasta aynı gün çıkmış olmalı)
CIKIS_SORUNU = """CASE
         WHEN P.CTARIH IS NULL                     THEN 'Protokol kapatılmamış'
         WHEN P.CTARIH < P.GTARIH                  THEN 'Çıkış saati eksik'
         WHEN TRUNC(P.CTARIH) = TRUNC(P.GTARIH)    THEN 'Uygun'
         WHEN TRUNC(P.CTARIH) = TRUNC(P.GTARIH) + 1 THEN 'Ertesi gün kapatılmış'
         ELSE (TRUNC(P.CTARIH) - TRUNC(P.GTARIH)) || ' gün açık kalmış'
       END"""

AMELIYATLI = """EXISTS (SELECT 1 FROM HASTANE.AMELIYATHANE A
              WHERE A.PROTOKOL_NO = P.PROTOKOL_NO AND A.OPERASYON IS NOT NULL)"""


# ----------------------------------------------------------------------------
# RAPORLAR
# Her rapor: menü adı, açıklama, tarih alanı adı, SQL ve kolonlar.
# SQL içinde :hastane_no, :tar1 (başlangıç tarih-saati) ve :tar2 (bitiş
# tarih-saati, dahil) kullanılır. Kolon sırası SELECT sırasıyla aynı olmalıdır.
# Kolon tipi: "tarih" -> GG.AA.YYYY SS:DD, "durum" -> renkli etiket.
# ----------------------------------------------------------------------------
RAPORLAR = {
    "cerrahi": {
        "renk": "#0f8b8d", "ikon": "🩺",
        "menu": "Güvenli Cerrahi Kontrol Listesi",
        "alt": "Gözlem yapılmış ameliyatlar",
        "aciklama": "Seçilen tarihler arasında yapılan ve <b>güvenli cerrahi gözlemi yapılmış</b> ameliyatlar listelenir.",
        "tarih_etiketi": "Ameliyat",
        "sql": """
SELECT K.DOSYA_NO,
       K.ADI || ' ' || K.SOYADI,
       A.PROTOKOL_NO,
       A.BAS_TARIHI,
       OPL.OPERASYON_ADI,
       DR.ADI_SOYADI,
       DR2.ADI_SOYADI,
       CASE WHEN NVL(A.SKS_KONTROL_UYGUN,'F') = 'F' THEN 'UYGUN DEĞİL' ELSE 'UYGUN' END,
       I.ANESTEZI_ONERI,
       I.CERRAH_ONERI,
       I.TARIH
FROM HASTANE.AMELIYATHANE A
JOIN HASTANE.AMELIYAT_YAP AME
     ON  AME.DOSYA_NO    = A.DOSYA_NO
     AND AME.PROTOKOL_NO = A.PROTOKOL_NO
     AND AME.SIRA_NO     = A.SIRA_NO
JOIN HASTANE.INDIKATOR_CERR_KONTROL I ON I.PROTOKOL_NO = A.PROTOKOL_NO
JOIN HASTANE.KIMLIK K                 ON K.DOSYA_NO    = I.DOSYA_NO
LEFT JOIN HASTANE.AMELIYAT_LIST OPL   ON OPL.OPERASYON_KODU = AME.OPERASYON_KODU
LEFT JOIN HASTANE.DRADI DR            ON DR.DR_KODU  = A.OPERATOR_DR
LEFT JOIN HASTANE.DRADI DR2           ON DR2.DR_KODU = A.ANEZTEZI_UZ
WHERE A.BAS_TARIHI >= :tar1
  AND A.BAS_TARIHI <= :tar2
  AND A.HASTANE_NO = :hastane_no
  AND A.SKS_GOZLEM_YAPILDI = 'T'
ORDER BY A.BAS_TARIHI, K.ADI, K.SOYADI""",
        "kolonlar": [
            ("Dosya No", "sayi", 10), ("Hasta", "metin", 26), ("Protokol No", "sayi", 12),
            ("Ameliyat Tarihi", "tarih", 17), ("Operasyon Adı", "metin", 45),
            ("Doktor", "metin", 22), ("Anestezist", "metin", 22),
            ("Kontrol Uygun mu?", "durum", 16), ("Anestezist Önerisi", "metin", 30),
            ("Cerrah Önerisi", "metin", 30), ("Kontrol Listesi Tarihi", "tarih", 17),
        ],
    },
    "eksiksiz_tum": {
        "renk": "#2f6fdf", "ikon": "📁",
        "menu": "Eksiksiz Hasta Dosyası Oranı",
        "alt": "Tüm liste (arşive teslim edilenler)",
        "aciklama": "Seçilen tarihler arasında çıkışı yapılmış ve <b>arşive teslim edilmiş</b> tüm dosyalar, eksiksiz olup olmadıklarıyla birlikte listelenir.",
        "tarih_etiketi": "Çıkış",
        "sql": """
SELECT P.PROTOKOL_NO,
       K.ADI || ' ' || K.SOYADI,
       P.GTARIH,
       P.CTARIH,
       P.ARSIV_SIRA_NO,
       P.EVRAK_DURUMU,
       CASE WHEN E.EKSIKSIZ_EVRAK = 'T' THEN 'EVET' ELSE 'HAYIR' END,
       P.DOSYA_NO
FROM HASTANE.PROTOKOL P
JOIN HASTANE.KIMLIK K         ON K.DOSYA_NO = P.DOSYA_NO
LEFT JOIN HASTANE.EVRAKLIST E ON E.EVRAKNO  = P.EVRAK_DURUMU
WHERE P.HASTANE_NO = :hastane_no
  AND P.CTARIH >= :tar1
  AND P.CTARIH <= :tar2
  AND P.ARSIV_SIRA_NO IS NOT NULL
ORDER BY P.CTARIH, K.ADI, K.SOYADI""",
        "kolonlar": [
            ("Protokol No", "sayi", 12), ("Hasta", "metin", 28), ("Giriş Tarihi", "tarih", 17),
            ("Çıkış Tarihi", "tarih", 17), ("Arşiv Sıra No", "sayi", 13), ("Evrak No", "sayi", 9),
            ("Eksiksiz mi?", "durum", 12), ("Dosya No", "sayi", 10),
        ],
    },
    "arsivsiz": {
        "renk": "#c26a00", "ikon": "🗄️",
        "menu": "Eksiksiz Hasta Dosyası Oranı",
        "alt": "Arşiv sıra no verilmeyenler",
        "aciklama": "Evrakı <b>eksiksiz</b> işaretlenmiş ama <b>arşiv sıra numarası girilmemiş</b> dosyalar listelenir. Bu dosyalar oranı %100'ün üstüne çıkarır; arşiv numarası verilmelidir.",
        "tarih_etiketi": "Çıkış",
        "sql": """
SELECT P.PROTOKOL_NO,
       K.ADI || ' ' || K.SOYADI,
       P.GTARIH,
       P.CTARIH
FROM HASTANE.PROTOKOL P
JOIN HASTANE.KIMLIK K    ON K.DOSYA_NO = P.DOSYA_NO
JOIN HASTANE.EVRAKLIST E ON E.EVRAKNO  = P.EVRAK_DURUMU
WHERE P.HASTANE_NO = :hastane_no
  AND P.CTARIH >= :tar1
  AND P.CTARIH <= :tar2
  AND E.EKSIKSIZ_EVRAK = 'T'
  AND P.ARSIV_SIRA_NO IS NULL
ORDER BY P.CTARIH""",
        "kolonlar": [
            ("Protokol No", "sayi", 12), ("Hasta", "metin", 30),
            ("Giriş Tarihi", "tarih", 17), ("Çıkış Tarihi", "tarih", 17),
        ],
    },
    "evraksiz": {
        "renk": "#d64545", "ikon": "📝",
        "menu": "Evrak No Verilmeyen Hastalar",
        "alt": "Arşivde olup evrak durumu 0 olanlar",
        "aciklama": "Seçilen tarihler arasında çıkışı yapılmış, <b>arşive teslim edilmiş</b> ama <b>evrak durumu 0 (veya boş)</b> olan dosyalar listelenir.",
        "tarih_etiketi": "Çıkış",
        "kopyala": 2,   # "Protokol No'ları kopyala" düğmesi bu kolonu kopyalar
        "sql": """
SELECT P.DOSYA_NO,
       K.ADI || ' ' || K.SOYADI,
       P.PROTOKOL_NO,
       P.ARSIV_SIRA_NO,
       P.CTARIH,
       NVL(P.EVRAK_DURUMU, 0),
       CASE WHEN E.EKSIKSIZ_EVRAK = 'T' THEN 'EVET' ELSE 'HAYIR' END
FROM HASTANE.PROTOKOL P
JOIN HASTANE.KIMLIK K         ON K.DOSYA_NO = P.DOSYA_NO
LEFT JOIN HASTANE.EVRAKLIST E ON E.EVRAKNO  = P.EVRAK_DURUMU
WHERE P.CTARIH >= :tar1
  AND P.CTARIH <= :tar2
  AND P.HASTANE_NO = :hastane_no
  AND P.ARSIV_SIRA_NO IS NOT NULL
  AND NVL(P.EVRAK_DURUMU, 0) = 0
ORDER BY P.CTARIH, K.ADI, K.SOYADI""",
        "kolonlar": [
            ("Dosya No", "sayi", 10), ("Hasta", "metin", 28), ("Protokol No", "sayi", 12),
            ("Arşiv Sıra No", "sayi", 13), ("Çıkış Tarihi", "tarih", 17),
            ("Evrak Durumu", "sayi", 12), ("Eksiksiz mi?", "durum", 12),
        ],
    },
    "cerrahi_arsiv": {
        "renk": "#5b3fc4", "ikon": "🔎",
        "menu": "Güvenli Cerrahi – Arşiv / Evrak",
        "alt": "Arşiv sıra no ve evrak durumu",
        "aciklama": "Güvenli cerrahi kontrol listesindeki hastaların <b>arşiv sıra numarası</b> ve <b>evrak durumu</b> gösterilir. Her protokol bir kez listelenir; protokoldeki ameliyatlardan biri uygun değilse <b>UYGUN DEĞİL</b> yazar.",
        "tarih_etiketi": "Ameliyat",
        "kopyala": 2,
        "sql": """
SELECT K.DOSYA_NO,
       K.ADI || ' ' || K.SOYADI,
       A.PROTOKOL_NO,
       CASE WHEN MIN(NVL(A.SKS_KONTROL_UYGUN,'F')) = 'F' THEN 'UYGUN DEĞİL' ELSE 'UYGUN' END,
       P.ARSIV_SIRA_NO,
       NVL(P.EVRAK_DURUMU, 0)
FROM HASTANE.AMELIYATHANE A
JOIN HASTANE.AMELIYAT_YAP AME
     ON  AME.DOSYA_NO    = A.DOSYA_NO
     AND AME.PROTOKOL_NO = A.PROTOKOL_NO
     AND AME.SIRA_NO     = A.SIRA_NO
JOIN HASTANE.INDIKATOR_CERR_KONTROL I ON I.PROTOKOL_NO = A.PROTOKOL_NO
JOIN HASTANE.KIMLIK K                 ON K.DOSYA_NO    = I.DOSYA_NO
JOIN HASTANE.PROTOKOL P               ON P.PROTOKOL_NO = A.PROTOKOL_NO
                                     AND P.DOSYA_NO    = A.DOSYA_NO
WHERE A.BAS_TARIHI >= :tar1
  AND A.BAS_TARIHI <= :tar2
  AND A.HASTANE_NO = :hastane_no
  AND A.SKS_GOZLEM_YAPILDI = 'T'
GROUP BY K.DOSYA_NO, K.ADI, K.SOYADI, A.PROTOKOL_NO, P.ARSIV_SIRA_NO, P.EVRAK_DURUMU
ORDER BY MIN(A.BAS_TARIHI), K.ADI, K.SOYADI""",
        "kolonlar": [
            ("Dosya No", "sayi", 10), ("Hasta", "metin", 28), ("Protokol No", "sayi", 12),
            ("Kontrol Uygun mu?", "durum", 16), ("Arşiv Sıra No", "sayi", 13),
            ("Evrak Durumu", "sayi", 12),
        ],
    },
    "kalis": {
        "renk": "#c2185b", "ikon": "🛏️",
        "menu": "Hasta Kalış Süreleri",
        "alt": "Ameliyatlı hastaların kalış süresi",
        "aciklama": "Seçilen tarihler arasında girişi yapılmış ve <b>ameliyat olmuş</b> hastalar listelenir. Çıkış saatleri güvenilir olmadığından kalış <b>takvim günü</b> olarak hesaplanır (aynı gün = 0, ertesi gün = 1). <b>Uyarı</b> kolonu düzeltilmesi gereken kayıtları gösterir.",
        "tarih_etiketi": "Giriş",
        "ozet": {"tur": "kalis", "gun": 6, "uyari": 7},
        "sql": f"""
SELECT P.DOSYA_NO,
       P.PROTOKOL_NO,
       K.ADI || ' ' || K.SOYADI,
       P.GTARIH,
       P.CTARIH,
       ROUND(P.CTARIH - P.GTARIH, 2),
       {TAKVIM_GUN},
       {CIKIS_SORUNU}
FROM HASTANE.PROTOKOL P
LEFT JOIN HASTANE.KIMLIK K ON K.DOSYA_NO = P.DOSYA_NO
WHERE P.HASTANE_NO = :hastane_no
  AND P.GTARIH >= :tar1
  AND P.GTARIH <= :tar2
  AND P.CTARIH IS NOT NULL
  AND {AMELIYATLI}
ORDER BY P.GTARIH, P.PROTOKOL_NO""",
        "kolonlar": [
            ("Dosya No", "sayi", 10), ("Protokol No", "sayi", 12), ("Hasta", "metin", 28),
            ("Giriş Tarihi", "tarih", 17), ("Çıkış Tarihi", "tarih", 17),
            ("Kayıttaki Süre (Gün)", "ondalik", 16), ("Takvim Günü", "sayi", 12),
            ("Uyarı", "uyari", 24),
        ],
    },
}

ALT_RAPORLAR = {}


def ozet_hesapla(rapor, satirlar, toplam=None):
    """Listenin üstünde gösterilecek toplamlar (sadece 'ozet' tanımlı raporlarda)."""
    oz = rapor.get("ozet")
    if not oz or oz["tur"] != "kalis":
        return None
    sorunlar = [r[oz["uyari"]] or "" for r in satirlar]
    gunler = [int(r[oz["gun"]]) for r in satirlar if r[oz["gun"]] is not None]
    toplam_gun = sum(gunler)
    return [
        {"ad": "Hasta", "deger": len({r[0] for r in satirlar})},
        {"ad": "Protokol", "deger": len(satirlar)},
        {"ad": "Toplam kalış (takvim günü)", "deger": toplam_gun},
        {"ad": "Ortalama kalış (gün)", "deger": round(toplam_gun / len(gunler), 2) if gunler else 0},
        {"ad": "Düzeltilecek kayıt", "deger": sum(1 for x in sorunlar if x != "Uygun")},
    ]


# ----------------------------------------------------------------------------
# DEMO VERİSİ (DEMO=1 ile veritabanısız çalıştırma)
# ----------------------------------------------------------------------------
def demo_veri(kod, tar1, tar2):
    r = demo.tohum(kod)
    n = r.randint(14, 24)
    satirlar = []
    for _ in range(n):
        dosya, prot = demo.numara(r, 100000, 199999), demo.numara(r, 2000000, 2999999)
        ad, t = demo.maskeli_ad(r), demo.tarih(r, tar1, tar2)
        cikis = t.replace(hour=min(t.hour + r.randint(1, 4), 23))
        arsiv = r.choice([None] + [demo.numara(r, 1000, 9999)] * 6)
        evrak = r.choice([0, 1, 1, 1, 2])
        uygun = r.random() > 0.15
        if kod == "cerrahi":
            satirlar.append([dosya, ad, prot, t, r.choice(demo.OPERASYONLAR), r.choice(demo.DOKTORLAR),
                             r.choice(demo.ANESTEZISTLER), "UYGUN" if uygun else "UYGUN DEĞİL",
                             r.choice(["Yok", "Lokal anestezi uygun", ""]), r.choice(["Yok", "Taburcu sonrası kontrol", ""]), t])
        elif kod == "eksiksiz_tum":
            satirlar.append([prot, ad, t, cikis, arsiv, evrak, "EVET" if evrak else "HAYIR", dosya])
        elif kod == "arsivsiz":
            satirlar.append([prot, ad, t, cikis])
        elif kod == "evraksiz":
            satirlar.append([dosya, ad, prot, arsiv or demo.numara(r, 1000, 9999), cikis, 0, "HAYIR"])
        elif kod == "cerrahi_arsiv":
            satirlar.append([dosya, ad, prot, "UYGUN" if uygun else "UYGUN DEĞİL", arsiv, evrak])
        elif kod == "kalis":
            gun = r.choice([0, 0, 0, 0, 0, 0, 1, 2])
            c = cikis + timedelta(days=gun)
            uyari = {0: "Uygun", 1: "Ertesi gün kapatılmış"}.get(gun, f"{gun} gün açık kalmış")
            satirlar.append([dosya, prot, ad, t, c, round((c - t).total_seconds() / 86400, 2), gun, uyari])
    satirlar.sort(key=lambda s: str(s[3]))
    return satirlar, None
