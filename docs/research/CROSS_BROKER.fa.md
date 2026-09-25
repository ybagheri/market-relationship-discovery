# مقایسه چند بروکر

## هدف

مقایسه چند بروکر تفاوت نظری قیمت را از اختلاف پژوهشی که bid/ask آن را قابل عبور می‌کند جدا می‌کند. مشاهده crossable فقط وقتی است که ask یک بروکر بیش از هزینه اضافی پیکربندی‌شده از bid بروکر دیگر کمتر باشد. این وضعیت آربیتراژ بدون ریسک یا اجرای تضمینی نامیده نمی‌شود.

## همگام‌سازی

`CrossBrokerComparisonEngine` هم `anchor_a` و هم همگام‌سازی متقارن mutual-nearest یک‌به‌یک را پشتیبانی می‌کند. delay منبع با علامت و تعداد unmatched حفظ می‌شود. updateهای tick با timestamp تکراری در storage خام حفظ و به‌صورت پیش‌فرض با policy صریح `last` aggregate می‌شوند؛ `none` آن‌ها را رد می‌کند.

داشبورد previewهای ذخیره‌شده مقایسه را نمایش می‌دهد. این نما جایگزین موتور full-resolution یا timeline اجرایی نیست.

## مقایسه tick

داده tick تفاوت mid، bid و ask را در دو جهت گزارش می‌کند. دو edge ناخالص جهتی عبارت‌اند از:

- bid بروکر B منهای ask بروکر A
- bid بروکر A منهای ask بروکر B

از هر edge کمی از `additional_cost` کم می‌شود. observationهای با net مثبت در episodeهای پیوسته گروه‌بندی می‌شوند و جهت، شروع، پایان، مدت، تعداد مشاهده و بیشترین/میانگین edge ثبت می‌شود. خلاصه شامل فرکانس، مدت، delay، تفاوت آگاه به spread و observationهای بدون match است.

## ایمنی bar

مقایسه bar از close استفاده می‌کند و همیشه `theoretical_bar_price_comparison` است. حتی با اختلاف زیاد هیچ opportunity crossable نمی‌سازد. bar نمی‌تواند اجرای tick-level را اثبات کند.

## safety gate قرارداد

مقایسه tick می‌تواند دو فایل JSON از `ContractSpecification` دریافت کند. نبود spec برچسب unverified می‌دهد. قرارداد ناسازگار، trade mode مفقود و اختلاف contract size یا tick value که نیازمند normalization است، episode opportunity را block می‌کنند. طبقه validated فقط با تطابق ارز، point/digits، محدودیت volume، trade mode، contract size و tick value ممکن است.

## بازتولیدپذیری

فرمان `compare-brokers` فایل CSV یا Parquet می‌گیرد و نام و SHA-256 هر دو منبع، symbol، برچسب broker، نوع observation، tolerance، هزینه اضافی، بازه و preview ردیف‌های همگام‌شده را در گزارش JSON با شناسه `EXP-*` ثبت می‌کند.

## visualization

گزارش‌های ذخیره‌شده `EXP-*.json` در داشبورد در دسترس‌اند. discrepancy explorer معیارهای bid/ask/mid، net edge، PnL و delay را همراه با مرجع هزینه و observationهای crossable نمایش می‌دهد. broker comparison قیمت mid همگام‌شده هر دو broker را رسم می‌کند. این نماها فقط‌خواندنی و توصیفی‌اند، نه شاهد اجرا.

## محدودیت‌ها

موتور اختلاف سازگار contract size و tick value را نرمال می‌کند، اما currency conversion، funding، rebate، session، ساخت symbol و قوانین اجرای broker-specific را مدل نمی‌کند. هزینه اضافی یک فرض ثابت پژوهشی است. episode مثبت فقط نامزد پژوهش اجرایی عمیق‌تر است.
