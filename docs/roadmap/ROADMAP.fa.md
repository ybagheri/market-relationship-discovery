# نقشه راه

وضعیت: `[ ] برنامه‌ریزی‌شده`، `[~] در حال انجام`، `[x] تکمیل‌شده`.

## فاز ۰ — زیرساخت

- [x] بررسی مخزن اولیه خالی
- [x] package، پیکربندی تایپ‌شده و logging
- [x] زیرساخت تست قطعی
- [x] مستندات انگلیسی و فارسی

## فاز ۱ — اتصال MT5

- [x] آداپتور رسمی فقط‌خواندنی MT5
- [x] تشخیص ترمینال و حساب
- [x] تأیید حساب دمو
- [x] کشف symbol و فراداده
- [x] دریافت tick و bar

## فاز ۲ — داده بازار

- [x] مدل نرمال‌شده quote و bar
- [x] الزام UTC
- [x] گزارش کیفیت داده
- [x] هم‌ترازی timestamp با tolerance
- [x] repository پارکت و manifest اتمیک dataset
- [x] پروفایل چند broker و collection تاریخی ترتیبی
- [x] collection موازی brokerها در processهای جدا
- [x] مقایسه همگام چند broker

## فاز ۳ — قیمت مصنوعی

- [x] parser و موتور فرمول عمومی
- [x] بازه اجرایی bid/ask
- [x] کاتالوگ اولیه روابط

## فاز ۴ — اختلاف قیمت

- [x] تفکیک نظری و اجرایی
- [x] edge خالص با هزینه قابل پیکربندی
- [x] اختلاف bid/ask بین brokerها، delay، فرکانس و مدت
- [x] دریافت specification قرارداد و safety gate فرصت
- [x] edge پژوهشی با PnL نرمال‌شده و قرارداد
- [ ] شبیه‌سازی funding، کمیسیون، margin و partial fill

## فاز ۵ — پژوهش آماری

- [x] همبستگی Pearson و Spearman
- [x] rolling z-score
- [x] half-life و lead/lag
- [ ] rolling beta و پایداری
- [ ] هم‌انباشت و ایستایی

## فاز ۶ — کشف

- [x] چارچوب تولید نامزد
- [ ] رتبه‌بندی مبتنی بر داده و فیلتر پایداری

## فاز ۷ — بک‌تست

- [x] معیارهای پایه و قطعی هزینه‌آگاه
- [x] اجرای سیگنال در observation بعدی بدون نشت هم‌زمان
- [x] foldهای walk-forward و انتخاب threshold فقط با train
- [x] ensemble سیگنال چندمرحله‌ای علی
- [x] شناسه experiment، hash منبع و گزارش JSON
- [x] پایداری Monte Carlo با circular block-bootstrap
- [x] سناریوهای spread، slippage، latency و stress ترکیبی

## فاز ۸ — داشبورد

- [x] هشدار دائمی دمو/پژوهش
- [x] نمای کلی، مانیتور، کاتالوگ و محدودیت‌ها
- [x] نمودار تعاملی اختلاف و broker

## فاز ۹ — پژوهش پیشرفته

- [x] مقایسه همگام anchor‌شده روی Broker A و provenance دو منبع
- [x] collection موازی MT5 در processهای جدا
- [x] همگام‌سازی event-time متقارن mutual-nearest
- [x] aggregate صریح duplicate tick و نرمال‌سازی PnL
- [x] تحلیل مدت opportunity در سطح tick
- [ ] تشخیص regime
- [ ] کشف رابطه با گراف
- [ ] رتبه‌بندی با کمک یادگیری ماشین

## فاز ۱۰ — اجرای اختیاری

- [ ] پیاده‌سازی نشده و خارج از دامنه
- [ ] در صورت مجوز آینده: فقط دمو، kill switch، سقف ریسک و audit
