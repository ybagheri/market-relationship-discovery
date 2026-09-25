# Collection موازی

## چرا process لازم است

ماژول رسمی Python متاتریدر 5 یک اتصال سراسری در هر process دارد. بنابراین initialize کردن ترمینال‌های مختلف ایمن نیازمند processهای worker جدا و نه adapter state مشترک است.

## مدل اجرا

`ParallelCollectionCoordinator` برای هر پروفایل broker یک job در `ProcessPoolExecutor` می‌سازد. هر job پروفایل MT5 تایپ‌شده، نگاشت symbol، درخواست collection و پوشه raw کامل دریافت می‌کند. هر worker آداپتور مستقل می‌سازد، `DEMO` را تأیید می‌کند، collection فقط‌خواندنی انجام می‌دهد، Parquet و manifest مستقل می‌نویسد، ترمینال را می‌بندد و batch را برمی‌گرداند.

collection موازی با فرمان زیر فعال می‌شود:

```bash
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
```

`DATA__COLLECTION_MAX_WORKERS` مقدار پیش‌فرض را می‌دهد و بین یک تا هشت محدود است. پروفایل broker تکراری رد می‌شود.

## خطا و ترتیب

worker ناموفق `ParallelCollectionError` با نام پروفایل ایجاد می‌کند؛ نتایج دیگر نباید اجرای کامل تلقی شوند. نتایج پس از پایان دوباره مطابق ترتیب ورودی مرتب می‌شوند. شناسه dataset شامل زمان و entropy تصادفی است تا نام فایل workerها تداخل نکند.

## مرز اعتبارسنجی

پیاده‌سازی روی Windows با یک ترمینال Demo و یک worker واقعی integration-test شد. collection هم‌زمان دو ترمینال اجرا نشد چون ترمینال Demo دوم پیکربندی نشده است. معماری از آن پشتیبانی می‌کند، اما concurrency واقعی چندترمینالی به اعتبارسنجی محیط با حداقل دو ترمینال Demo مجاز نیاز دارد.
