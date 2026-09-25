# همگام‌سازی Event-Time

## حالت‌ها

حالت `anchor_a` از هر timestamp در Broker A استفاده می‌کند و نزدیک‌ترین observationBroker B را در tolerance انتخاب می‌کند. این حالت سریع است اما ممکن است یک tick از B را برای چند update A دوباره استفاده کند.

حالت `symmetric` فقط matchهای نزدیکِ متقابل را نگه می‌دارد: A باید نزدیک B و B نیز مستقلاً نزدیک A باشد. این روش مجموعه comparison را یک‌به‌یک می‌کند و reuse تکراری quote را جلوگیری می‌کند. گزارش شامل mode، delay علامت‌دار و تعداد unmatched هر دو feed است.

## updateهای tick

بعضی brokerها چند update bid/ask با timestamp یکسان برمی‌گردانند. ذخیره Parquet خام این duplicateها را با شمارش حفظ می‌کند. comparison tick به‌صورت پیش‌فرض aggregation صریح `last` را انتخاب می‌کند. گزینه `tick_aggregation=none` duplicate را رد می‌کند.

## سوگیری انتخاب

mutual matching بهبود reuse quote را تضمین می‌کند اما هم‌زمانی اقتصادی را اثبات نمی‌کند. feed کم‌تراکم، update rate متفاوت، تعطیلی بازار و timestamp خراب می‌توانند match کم یا صفر ایجاد کنند. فرکانس opportunity از یک observation پایدار نیست و باید همراه تعداد مشاهده و مدت گزارش شود.

## آینده

state machine کامل event-time می‌تواند اعتبار interval، sequence ID، quote revision و مرز session را مدل کند. پیاده‌سازی فعلی عمداً قیمت interpolate نمی‌کند و quote stale را در match ردشده عبور نمی‌دهد.
