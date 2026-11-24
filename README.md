# Data Lab 2 – Nạp 20 triệu dòng NYC Taxi vào SQLite bằng Python (2 cách)

## 1. Dữ liệu
**NYC TLC Yellow Taxi Trip Records, 01–06/2024** (nguồn: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) + bảng `taxi_zone_lookup.csv`.

| File | Số dòng |
|---|---|
| yellow_tripdata_2024-01.csv | 2.964.624 |
| yellow_tripdata_2024-02.csv | 3.007.526 |
| yellow_tripdata_2024-03.csv | 3.582.628 |
| yellow_tripdata_2024-04.csv | 3.514.289 |
| yellow_tripdata_2024-05.csv | 3.723.833 |
| yellow_tripdata_2024-06.csv | 3.539.193 |
| **Tổng** | **20.332.093** (mỗi file > 1 triệu; tổng > 10 triệu) |

TLC phát hành dạng Parquet; `01_download.py` tải về rồi chuyển sang CSV (2,1 GB) để hai loader đọc bằng module `csv`.

## 2. Schema (6 bảng, SQLite)
- `vendors`, `rate_codes`, `payment_types`, `zones` – bảng tra cứu (zones lấy từ `taxi_zone_lookup.csv`).
- `trips` – thông tin chuyến đi (thời gian, quãng đường, FK tới các bảng trên).
- `trip_fares` – chi tiết tiền (quan hệ 1–1 với `trips`).

Mỗi dòng CSV được **tách thành 2 dòng** (`trips` + `trip_fares`) → 40,7 triệu dòng INSERT. Ba index: `pickup_ts`, `pu_location_id`, `do_location_id`.

## 3. Hai cách insert
| | **A – Row-by-row** (`load_rowbyrow.py`) | **B – Batch** (`load_batch.py`) |
|---|---|---|
| Lệnh | `cursor.execute()` cho từng dòng, từng bảng | gom buffer, `cursor.executemany()` mỗi 100.000 dòng |
| Commit | tuỳ chọn: mỗi dòng / mỗi N dòng / mỗi file | 1 lần mỗi file |
| PRAGMA | mặc định (journal=DELETE, synchronous=FULL) | journal=OFF, synchronous=OFF, cache 400 MB, locking EXCLUSIVE |
| Index | tạo **trước** khi nạp | tạo **sau** khi nạp (tính vào thời gian) |

## 4. Cách chạy lại
```bash
pip install -r requirements.txt
python scripts/01_download.py        # tải + đổi sang CSV (~2 GB)
python scripts/run_benchmark.py      # chạy toàn bộ thí nghiệm (~15 phút), kết quả ở results/*.json
python scripts/verify.py             # so sánh nội dung 2 DB
# hoặc chạy riêng:
python scripts/load_rowbyrow.py --name demo_a --commit-every 0
python scripts/load_batch.py --name demo_b --batch-size 100000
```
Máy test: Windows 11, Python 3.11, SQLite (module `sqlite3`), ổ SSD.

## 5. Kết quả

### 5.1 Toàn bộ 20,33 triệu dòng CSV (40,7 triệu INSERT)
| Cách | Thời gian | Dòng CSV/giây | Kích thước DB |
|---|---|---|---|
| A – row-by-row, commit mỗi file | **350,4 s** (5 phút 50) | 58.034 | 3.748 MB |
| B – batch executemany + tune | **231,9 s** (3 phút 52; trong đó nạp 162 s, dựng index 70 s) | 87.695 | 3.631 MB |

→ B nhanh hơn A khoảng **1,5 lần**.

### 5.2 Ảnh hưởng của kích thước transaction (mẫu 10.000 dòng đầu, cách A)
| Commit | Thời gian | Dòng/giây | Ước tính cho 20,3M dòng |
|---|---|---|---|
| mỗi dòng | 169,2 s | **59** | **~4 ngày** (ngoại suy) |
| mỗi 1.000 dòng | 0,21 s | 47.368 | ~7 phút |
| mỗi file | – | 58.034 (đo thật) | 5,8 phút |

Đây là chênh lệch lớn nhất: commit mỗi dòng buộc fsync xuống đĩa mỗi lần.

### 5.3 Ablation trên 500.000 dòng đầu (cái gì làm B nhanh hơn?)
| Cấu hình | Thời gian | Dòng/giây |
|---|---|---|
| A: row-by-row | 5,43 s | 92.155 |
| B: executemany, PRAGMA mặc định, batch 100k | 4,58 s | 109.225 |
| B: executemany + PRAGMA tune, batch 100k | 4,47 s | 111.958 |
| B: tuned, batch 10k | 4,32 s | 115.704 |
| B: tuned, batch 1k | 4,24 s | 117.966 |

Lưu ý: ở mẫu nhỏ, chênh lệch A/B chỉ ~20%, nhỏ hơn ở quy mô đầy đủ (~50%) vì index chưa lớn. Phần ablation chạy trong lúc `verify.py` đang đọc DB nên số đo có thể lệch vài %; mỗi cấu hình chỉ chạy 1 lần (không lặp) nên chênh lệch dưới ~10% giữa các batch size không đủ để kết luận.

## 6. Nhận xét ưu / nhược
**A – Row-by-row**
- ✅ Đơn giản, dễ viết, dễ xử lý/bỏ qua từng dòng lỗi, ít tốn RAM, có thể commit dần để không mất tiến độ.
- ❌ Chậm hơn ở quy mô lớn (1,5×); nếu commit mỗi dòng thì cực kỳ chậm (59 dòng/s); duy trì index khi insert làm chậm dần theo kích thước bảng.

**B – Batch**
- ✅ Nhanh hơn; ít lời gọi qua lại Python↔SQLite; index dựng sau nhanh hơn chèn vào index từng dòng; kết quả ổn định theo batch size.
- ❌ Tốn RAM cho buffer; một dòng lỗi làm hỏng cả batch; với `journal_mode=OFF` + `synchronous=OFF` nếu mất điện/crash giữa chừng thì DB có thể hỏng (chỉ dùng được khi nạp lại từ đầu được); code phức tạp hơn một chút.

**Kết luận thực nghiệm:** yếu tố ảnh hưởng nhất là *số lần commit/fsync*. Gộp batch và tune PRAGMA chỉ cải thiện khoảng 1,2–1,5× vì phần lớn thời gian còn lại là Python đọc CSV và ép kiểu (cả hai cách dùng chung code parse). Muốn nhanh hơn nữa cần bulk-load gốc của DB (ví dụ `COPY` của PostgreSQL), không thực hiện ở đây.

## 7. Kiểm tra tính đúng đắn
Xem `results/verify.json` (so sánh số dòng, tổng tiền, tổng quãng đường, checksum `trip_id`, kết quả truy vấn join giữa 2 DB và số vi phạm khoá ngoại). Xem mục 8.

## 8. Kết quả verify
Hai DB cho **kết quả giống hệt nhau** trên mọi truy vấn kiểm tra (`identical_results = true`):
- 20.332.093 dòng ở cả `trips` và `trip_fares`; tổng `total_amount` = 557.830.247,45; tổng `trip_distance` = 95.659.760,68.
- 0 vi phạm khoá ngoại (`PRAGMA foreign_key_check`).
- Dữ liệu gốc có dòng bất thường: `pickup_ts` nhỏ nhất là 2002-12-31, lớn nhất 2026-06-26 (giữ nguyên, không làm sạch).
- Thời gian truy vấn trong `verify.json` **không dùng để so sánh A/B**: DB của A được đọc trước (cache nguội) và chạy lúc ablation đang chạy song song.

## 9. Hạn chế
- Dùng SQLite (không cần server), chưa thử PostgreSQL/MySQL; chênh lệch có thể khác trên DB client-server.
- Mỗi thí nghiệm chạy một lần, không lặp; số đo phụ thuộc máy.
- Dữ liệu TLC có dòng bất thường (ví dụ thời gian ngoài tháng, khoảng cách 0) – giữ nguyên, không làm sạch.
- Thư mục `data/` không đưa lên Git (2 GB); chạy `01_download.py` để tạo lại.
