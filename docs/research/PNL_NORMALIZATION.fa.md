# نرمال‌سازی PnL

## هدف

وقتی contract size یا tick value دو broker متفاوت باشد، edge خام قیمت قابل مقایسه نیست. `ContractEdgeNormalizer` edge خالص با ارز مشترک را برای حجم مشخص Broker A به یک برآورد PnL پژوهشی تبدیل می‌کند.

## نرمال‌سازی حجم

برای پوشش مقدار پایه برابر، حجم Broker B محاسبه می‌شود:

```text
volume_B = volume_A × contract_size_A / contract_size_B
```

## نرمال‌سازی PnL

برای ارز سود یکسان، PnL هر leg از فراداده رسمی tick محاسبه می‌شود:

```text
leg_PnL = net_price_edge × leg_volume × tick_value / tick_size
net_PnL = Broker_A_PnL + Broker_B_PnL
```

گزارش cross-broker شامل حجم B به ازای یک واحد A، میانگین و بیشترین PnL خالص نرمال‌شده و مقدار opportunity است. contract size و tick value که با یک نسبت فرق دارند با وضعیت `normalization_required` مشخص و فقط در صورت وجود specification کامل پردازش می‌شوند. ناسازگاری ارز، point/digit، نبود trade mode، و contract size‌ای که با tick value مقیاس نمی‌شود همگی opportunity را block می‌کنند.

توافق پاها اکنون نقش پشتیبان دارد نه دروازه اصلی: جفتی که contract size و tick value آن با هم مقیاس نمی‌شوند پیش از رسیدن به normalization به‌عنوان `incompatible` رد می‌شود، چون پاها در هر حجمی اختلاف دارند نه فقط در بعضی حجم‌ها. پسوند `_contract_legs_disagree` بنابراین تنها برای جفتی در دسترس است که از دروازه سازگاری عبور کرده و باز هم اختلاف دارد، که نشانه نقص specification یا گرد کردنی است که تلورانس پوشش نداد.

## هزینه و محدودیت‌ها

`additional_cost` یک فرض ثابت در واحد قیمت خام است و پیش از تبدیل PnL کم می‌شود. normalizer تبدیل ارز، swap، تفاوت کمیسیون، rebate، margin، partial fill، جایگاه صف یا قراردادهای خاص PnL را مدل نمی‌کند. مقدار نرمال‌شده مثبت یک معیار پژوهشی است، نه سود تحقق‌یافته.

## یادداشت اعتبارسنجی

اعتبارسنجی زنده با دو ترمینال Demo فقط یک observation همگام EURUSD تولید کرد و candidate با مدت صفر گزارش شد. چنین نتیجه کم‌تراکم صریحاً شواهد کافی برای opportunity اجرایی نیست و نباید strategy تلقی شود.
