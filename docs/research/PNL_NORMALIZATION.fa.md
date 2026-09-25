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

گزارش cross-broker شامل حجم B به ازای یک واحد A، میانگین و بیشترین PnL خالص نرمال‌شده و مقدار opportunity است. اختلاف contract size یا tick value با وضعیت `normalization_required` مشخص و فقط در صورت وجود specification کامل پردازش می‌شود. ناسازگاری ارز، point/digit یا نبود trade mode همچنان opportunity را block می‌کند.

## هزینه و محدودیت‌ها

`additional_cost` یک فرض ثابت در واحد قیمت خام است و پیش از تبدیل PnL کم می‌شود. normalizer تبدیل ارز، swap، تفاوت کمیسیون، rebate، margin، partial fill، جایگاه صف یا قراردادهای خاص PnL را مدل نمی‌کند. مقدار نرمال‌شده مثبت یک معیار پژوهشی است، نه سود تحقق‌یافته.

## یادداشت اعتبارسنجی

اعتبارسنجی زنده با دو ترمینال Demo فقط یک observation همگام EURUSD تولید کرد و candidate با مدت صفر گزارش شد. چنین نتیجه کم‌تراکم صریحاً شواهد کافی برای opportunity اجرایی نیست و نباید strategy تلقی شود.
