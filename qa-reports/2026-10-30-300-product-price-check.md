# TrustFolio - 300 Product Live Price Audit - 30 October 2026

**Read-only test:** no MongoDB writes, deletions or production Worker migration.
Amazon and Flipkart: own Cloudflare Worker. Croma: existing VPS direct API (Cloudflare test HTTP 403).
Extracted prices are not independently checked against the marketplace yet: manually confirm exact variant and seller.

## Overall results

| Platform | Tested | Price extracted | Missing / error | Changed vs MongoDB |
|---|---:|---:|---:|---:|
| Amazon | 100 | 91 | 9 | 89 |
| Flipkart | 100 | 44 | 56 | 9 |
| Croma | 100 | 80 | 20 | 21 |

N/A indicates unverified live price; the catalog price is historical and must not be labelled Live.

## Amazon - 100 products

| # | Open product | SKU | MongoDB price | Fresh price | Status | Error | Manual verified |
|---:|---|---|---:|---:|---|---|---|
| 1 | [1.5 TON, FIX SPEED WINDOW AC Anti-dust Filter, AXG183FSOG, White) / Anti dust ](https://www.amazon.in/dp/B0H75M7JKH) | B0H75M7JKH | ₹47,990 | ₹4,799,000 | ok |  | [ ] |
| 2 | [90L Desert Air Cooler With 30" Axial Fan & 18,000 CMH Airflow For Outdoor Use ](https://www.amazon.in/dp/B0DVH1HDVQ) | B0DVH1HDVQ | ₹26,030 | ₹30,899 | ok |  | [ ] |
| 3 | [Crompton Super Briz Deco 1200 mm (48 Inch) High Speed Decorative Ceiling Fan (](https://www.amazon.in/dp/B074J9SPYX) | B074J9SPYX | ₹2,765 | ₹3,999 | ok |  | [ ] |
| 4 | [Desktop Pc Computer CORE i7 2600/16 GB RAM/ 120GB SSD & 1TB HDD/ 2GB Graphics/](https://www.amazon.in/dp/B08RC27RJM) | B08RC27RJM | ₹29,849 | ₹35,999 | ok |  | [ ] |
| 5 | [Drone with 1080P HD Camera for Adults, Mini Quadcopter with Dual Rudder, 50-Mi](https://www.amazon.in/dp/B0F24RTBDQ) | B0F24RTBDQ | ₹9,999 | ₹15,999 | ok |  | [ ] |
| 6 | [Symphony Swish 3L Instant Water Geyser / 3KW Heating / Fast Heating for Kitche](https://www.amazon.in/dp/B0FWBYMBF5) | B0FWBYMBF5 | ₹3,691 | ₹5,999 | ok |  | [ ] |
| 7 | [DOMA VM Premium True Wireless Earbuds with Active Noise Cancellation, IPX5 Wat](https://www.amazon.in/dp/B0GQ9D332T) | B0GQ9D332T | ₹2,999 | ₹6,200 | ok |  | [ ] |
| 8 | [Pigeon by Stovekraft Cruise 1800-Watt Induction Cooktop (Black) + Pigeon by St](https://www.amazon.in/dp/B08BTJBX1V) | B08BTJBX1V | ₹2,778 | ₹1,389 | ok |  | [ ] |
| 9 | [Lenovo IdeaPad Chromebook Duet / 11 Inch FHD+ 1200p Laptop / MediaTek Kompanio](https://www.amazon.in/dp/B0HJ7WTBS8) | B0HJ7WTBS8 | ₹34,297 | ₹67,490 | ok |  | [ ] |
| 10 | [Cadlec MultiChef Multi-Function OTG for Kitchen, 25 Litre, 1300W, Oven Toaster](https://www.amazon.in/dp/B0FHQB5M26) | B0FHQB5M26 | ₹3,199 | ₹9,999 | ok |  | [ ] |
| 11 | [PADMINI MAGIC Juicer Mixer Grinder 450 Watts, 1.5L Juicer Jar And 0.4L Grindin](https://www.amazon.in/dp/B008KVU41Q) | B008KVU41Q | ₹2,494 | ₹3,880 | ok |  | [ ] |
| 12 | [Samsung 236 L, 2 Star, Convertible, Digital Inverter Frost Free Double Door Re](https://www.amazon.in/dp/B0G8J89W43) | B0G8J89W43 | ₹34,390 | ₹36,999 | ok |  | [ ] |
| 13 | [iQOO Z11 5G (Aurora Green, 12GB RAM, 256GB Storage) / India's 1st MediaTek Dim](https://www.amazon.in/dp/B0HCN78GQL) | B0HCN78GQL | ₹49,999 | ₹69,999 | ok |  | [ ] |
| 14 | [OEM Replacement TV Base Stand Legs Compatible with LG 75 Inch Class LED 4K UHD](https://www.amazon.in/dp/B0BNT6C4V6) | B0BNT6C4V6 | ₹13,267 | ₹28,657 | ok |  | [ ] |
| 15 | [TIMEX iConnect Navigator 1.83"(4.6cm) Display with Turn by Turn Navigation & B](https://www.amazon.in/dp/B0F31GNW15) | B0F31GNW15 | ₹1,995 | ₹5,495 | ok |  | [ ] |
| 16 | [Boat Aavante Soundbar](https://www.amazon.in/dp/B0F5BDTR4K) | B0F5BDTR4K | ₹5,499 | N/A | error | product_identity_unverified | [ ] |
| 17 | [TECLAST Artpadpro Android 15 Tablet, Display 12.8 Inches 2176 x 1600, 20 GB + ](https://www.amazon.in/dp/B0FBWLY68R) | B0FBWLY68R | ₹34,380 | ₹34,380 | ok |  | [ ] |
| 18 | [Eureka Forbes Cyclo Vac -24 kPa High Suction Vacuum Cleaner/Cyclonic Technolog](https://www.amazon.in/dp/B0FMS1V1SW) | B0FMS1V1SW | ₹5,999 | ₹9,100 | ok |  | [ ] |
| 19 | [LG 9 Kg, 5 Star, Smart Inverter Technology, In-built heater with Steam, Fully ](https://www.amazon.in/dp/B0GY8W3MKL) | B0GY8W3MKL | ₹23,989 | ₹33,990 | ok |  | [ ] |
| 20 | [Aquaguard Sure Delight NXT RO+UV Water Purifier / Free Service Plan worth](https://www.amazon.in/dp/B09TB2YC13) | B09TB2YC13 | ₹9,499 | ₹14,000 | ok |  | [ ] |
| 21 | [1.0 ton 3 Star, Inverter Split AC (Copper, 6-in-1 Adjustable Mode, Anti-dust F](https://www.amazon.in/dp/B0FT7PCLFC) | B0FT7PCLFC | ₹45,000 | ₹59,990 | ok |  | [ ] |
| 22 | [Navigator 130 Air Cooler / 130L Tank / 4800 m³/hr Air Flow / 20 Inch Fan / Hea](https://www.amazon.in/dp/B0GSZY8VHK) | B0GSZY8VHK | ₹19,999 | ₹26,999 | ok |  | [ ] |
| 23 | [Crompton SUPER BRIZ DECO 1200 mm (48 inch) Ceiling Fan (Birken Ivory) Star rat](https://www.amazon.in/dp/B0CGDBR9DC) | B0CGDBR9DC | ₹2,679 | ₹267,900 | ok |  | [ ] |
| 24 | [Pratyush Tez K7 Desktop Computer Tower PC - Core i7-4790 Processor CPU (3.6GHz](https://www.amazon.in/dp/B0F6Y8YL8V) | B0F6Y8YL8V | ₹29,395 | ₹50,199 | ok |  | [ ] |
| 25 | [Drone with Camera for Adults 1080P HD Dual Rudder Eletric Adjust, Mini Drone w](https://www.amazon.in/dp/B0F266J4VJ) | B0F266J4VJ | ₹9,999 | ₹15,999 | ok |  | [ ] |
| 26 | [Activa 15L Water Heater Geyser with Temperature Meter, 2 KVA ISI Cooper Elemen](https://www.amazon.in/dp/B086374DS9) | B086374DS9 | ₹3,598 | ₹6,990 | ok |  | [ ] |
| 27 | [Wireless Earbuds, 2025 Bluetooth Headphones 5.3 HiFi Stereo Headphone with 20 ](https://www.amazon.in/dp/B0DSTCN81X) | B0DSTCN81X | ₹2,817 | ₹8,994 | ok |  | [ ] |
| 28 | [Pigeon by Stovekraft Cruise 1800-Watt Induction Cooktop (Black) & Stainless St](https://www.amazon.in/dp/B085GP7S8M) | B085GP7S8M | ₹1,788 | ₹3,690 | ok |  | [ ] |
| 29 | [FUTOPIA Ultimus APEX5 Laptop Intel core i5 12th Gen 1235U Laptop 8GB RAM 512GB](https://www.amazon.in/dp/B0CRVCGHJG) | B0CRVCGHJG | ₹57,990 | ₹75,990 | ok |  | [ ] |
| 30 | [Morphy Richards](https://www.amazon.in/dp/B0F66WHT1M) | B0F66WHT1M | ₹11,799 | ₹29,999 | ok |  | [ ] |
| 31 | [Borosil Max 500 W Mixer Grinder / Wet & Dry Mixing, Grinding & Blending / 3 Ja](https://www.amazon.in/dp/B0DNMD4PJB) | B0DNMD4PJB | ₹2,499 | ₹624 | ok |  | [ ] |
| 32 | [Haier HVC 405 GT5, 5 Star, Touch LED Visi Cooler Glass Door, Adjustable Shelve](https://www.amazon.in/dp/B0DYDYGGHR) | B0DYDYGGHR | ₹34,962 | ₹55,990 | ok |  | [ ] |
| 33 | [realme 16 Pro 5G Smartphone 12+256GB, 144Hz AMOLED Display, 7000mAh Battery, 8](https://www.amazon.in/dp/B0GGY53B9B) | B0GGY53B9B | ₹49,999 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 34 | [IONSTAR 80 CM (32 inches) HD Smart QLED Android TV 2026 / 1000+ Apps Support /](https://www.amazon.in/dp/B0GX5KJ5JN) | B0GX5KJ5JN | ₹9,790 | ₹28,990 | ok |  | [ ] |
| 35 | [TIMEX iConnect Navigator 1.83"(4.6cm) Display with Turn by Turn Navigation & B](https://www.amazon.in/dp/B0F31GV9M5) | B0F31GV9M5 | ₹1,995 | ₹5,495 | ok |  | [ ] |
| 36 | [boAt Aavante 2.1 1650, 160W Signature Sound, 2.1-Channel with Wireless Subwoof](https://www.amazon.in/dp/B0FHJ281GB) | B0FHJ281GB | ₹5,999 | N/A | error | product_identity_unverified | [ ] |
| 37 | [Bigme B6 Color Ebook Reader, 6 Inch e-Paper Tablet, 4GB+64GB Storage, Android ](https://www.amazon.in/dp/B0FY6DGW2D) | B0FY6DGW2D | ₹32,157 | ₹32,157 | ok |  | [ ] |
| 38 | [Eureka Forbes SuperVac Vacuum Cleaner](https://www.amazon.in/dp/B0FMS18RZ2) | B0FMS18RZ2 | ₹8,999 | ₹899,900 | ok |  | [ ] |
| 39 | [Whirlpool 7 kg Inverter Fully Automatic Front Load Washing Machine (Fresh Care](https://www.amazon.in/dp/B09FFGB3CN) | B09FFGB3CN | ₹23,390 | ₹30,090 | ok |  | [ ] |
| 40 | [Aquaguard Aspire Blaze ROUV CUALK 1X Water Purifier](https://www.amazon.in/dp/B0H2F9KKP9) | B0H2F9KKP9 | ₹19,999 | ₹1,999,900 | ok |  | [ ] |
| 41 | [Hitachi 1.5 Ton 3 Star, New Star rated, Heavy Duty Smart Inverter Split AC (Co](https://www.amazon.in/dp/B0GP6SDT4H) | B0GP6SDT4H | ₹41,500 | ₹73,990 | ok |  | [ ] |
| 42 | [PG Power Guard Ice Max Plus 65L Air Cooler/ High Speed Fan / Honey Comb Pad /B](https://www.amazon.in/dp/B0CWB4G9P8) | B0CWB4G9P8 | ₹7,999 | ₹18,999 | ok |  | [ ] |
| 43 | [Crompton Highspeed Toro 1200 mm Designer Ceiling Fan / BEE Star Rated Energy E](https://www.amazon.in/dp/B0GNQTRSWC) | B0GNQTRSWC | ₹2,688 | ₹4,699 | ok |  | [ ] |
| 44 | [TECHSUPPORT Desktop PC, CPU i7-4790T Turbo // 16GB RAM // 1TB SSD 4.0 NVMe // ](https://www.amazon.in/dp/B0FZ551H2R) | B0FZ551H2R | ₹29,999 | ₹35,500 | ok |  | [ ] |
| 45 | [Drone with 4K Camera WiFi FPV 1080P HD Dual Foldable RC Drone Altitude Hold He](https://www.amazon.in/dp/B0DGSGGMB2) | B0DGSGGMB2 | ₹9,999 | ₹12,999 | ok |  | [ ] |
| 46 | [3000W Instant Portable Electric Water Geyser / 1.0L Mini Water Heater, Auto Cu](https://www.amazon.in/dp/B0G6KM5PZX) | B0G6KM5PZX | ₹3,819 | ₹5,999 | ok |  | [ ] |
| 47 | [Grooves Infinity Ultra Luxury Diamond Finish, 120 Hrs Standby, Super Bass and ](https://www.amazon.in/dp/B0D366KV6L) | B0D366KV6L | ₹1,999 | ₹3,999 | ok |  | [ ] |
| 48 | [Elevea 𝟏𝟓 𝐘𝐄𝐀𝐑𝐒 𝐖𝐀𝐑𝐑𝐀𝐍𝐓𝐘 2000W Electric Coil Hot Plate – Single Burner Cooktop](https://www.amazon.in/dp/B0FN4LXXJP) | B0FN4LXXJP | ₹2,989 | ₹8,999 | ok |  | [ ] |
| 49 | [ASUS CX14 Chromebook Laptop, 14" FHD (1920 x 1080) IPS LED Laptop, Intel Celer](https://www.amazon.in/dp/B0FK52KPHX) | B0FK52KPHX | ₹31,890 | ₹35,990 | ok |  | [ ] |
| 50 | [Panasonic 23L Convection Microwave Oven(NN-CT353BFDG,Black Mirror, 360° Heat W](https://www.amazon.in/dp/B00KPSSPZY) | B00KPSSPZY | ₹11,650 | ₹15,350 | ok |  | [ ] |
| 51 | [Blend Art 1000W Heavy Duty Mixer Grinder with Liquidizing Chutney Grinding Coo](https://www.amazon.in/dp/B0FPP6F66H) | B0FPP6F66H | ₹5,899 | ₹9,200 | ok |  | [ ] |
| 52 | [Godrej 30 L Qube Personal Standard Single door Cooling Solution (TEC Qube 30L ](https://www.amazon.in/dp/B07R3WXXH5) | B07R3WXXH5 | ₹7,740 | ₹8,250 | ok |  | [ ] |
| 53 | [iQOO Z11 video](https://www.amazon.in/dp/B0HCN9D5SL) | B0HCN9D5SL | ₹49,999 | ₹69,999 | ok |  | [ ] |
| 54 | [MTC 43 Inch Full HD Smart LED TV / Voice Remote with Assistant / Built-in Wi-F](https://www.amazon.in/dp/B0FNCLVRW5) | B0FNCLVRW5 | ₹24,000 | ₹24,000 | ok |  | [ ] |
| 55 | [URBAN Onyx Smartwatch Full Black](https://www.amazon.in/dp/B0F79J7GL9) | B0F79J7GL9 | ₹2,999 | ₹14,999 | ok |  | [ ] |
| 56 | [Blaupunkt Newly Launched Rock & Roll 100W Party Speaker with Dual 6.5'' woofer](https://www.amazon.in/dp/B0GMJFCYM2) | B0GMJFCYM2 | ₹8,499 | N/A | error | product_identity_unverified | [ ] |
| 57 | [OnePlus Pad Lite with Biggest Battery in Segment 9340 mAh, 11"(27.94 cm) Displ](https://www.amazon.in/dp/B0FHWWDRRM) | B0FHWWDRRM | ₹19,999 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 58 | [AGARO Ace Wet & Dry Vacuum Cleaner for Home, 1600 Watts, 21.5 kPa Suction Powe](https://www.amazon.in/dp/B07RCGTZ4M) | B07RCGTZ4M | ₹6,499 | ₹9,999 | ok |  | [ ] |
| 59 | [Electrolux 9kg 5 Star Front Load Washing Machine, 5 Year Warranty, AutoSense T](https://www.amazon.in/dp/B0BBTRZQNF) | B0BBTRZQNF | ₹45,490 | ₹85,990 | ok |  | [ ] |
| 60 | [Aquaguard Designo NXT 9-Stage Under The Counter Water Purifier / Active Copper](https://www.amazon.in/dp/B0CV7HQ6RZ) | B0CV7HQ6RZ | ₹24,699 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 61 | [Carrier 1 Ton 5 Star, New Star rated, Wi-Fi Smart Flexicool Inverter Split AC ](https://www.amazon.in/dp/B0GCFB848D) | B0GCFB848D | ₹41,990 | ₹64,990 | ok |  | [ ] |
| 62 | [Desert Cooler 110L-BCD110DGL Air Cooler (Grey & White) / Heavy-Duty Double Met](https://www.amazon.in/dp/B0GZ4YV7QT) | B0GZ4YV7QT | ₹16,499 | ₹28,999 | ok |  | [ ] |
| 63 | [REO Tejas 1200mm ES Ceiling Fan / High Speed, High Air Delivery / Strong & Pow](https://www.amazon.in/dp/B0D6BP6VR2) | B0D6BP6VR2 | ₹1,890 | ₹2,500 | ok |  | [ ] |
| 64 | [KRYNORCXY® Premium Gaming Desktop PC / Core i7 6700 Processor / 16GB DDR4 RAM ](https://www.amazon.in/dp/B0H5F6Q767) | B0H5F6Q767 | ₹41,999 | ₹80,000 | ok |  | [ ] |
| 65 | [dRoNe wItH hD DuAl cAmErA BrUsHlEsS MoToR, oNe cLiCk tAkEoFf/lAnDiNg FlIp rOlL](https://www.amazon.in/dp/B0F4RJ8NDT) | B0F4RJ8NDT | ₹9,999 | ₹9,999 | ok |  | [ ] |
| 66 | [ALTINO Zestos Premium Powerful 2 KW Storage Water Geyser 5 ★BEE Energy Rating,](https://www.amazon.in/dp/B0GS2FBWRQ) | B0GS2FBWRQ | ₹3,499 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 67 | [Buds X ANC In Ear Earbuds With Mic, AI-ENC, Upto 24 Hrs Playtime, 10Mm Bass Dr](https://www.amazon.in/dp/B0CRHPPN8M) | B0CRHPPN8M | ₹1,999 | ₹2,999 | ok |  | [ ] |
| 68 | [Drumstone (Exclusive & Limited) Portable Electric Cooktop with Touch Panel, To](https://www.amazon.in/dp/B0GTF6RN8B) | B0GTF6RN8B | ₹2,989 | ₹8,999 | ok |  | [ ] |
| 69 | [𝗗𝗲𝗹𝗹Laptop 5310 / InteI Core i5 10th Gen / 8GB RAM - 256GB SSD /14-inch Full H](https://www.amazon.in/dp/B0H3FDWYQ2) | B0H3FDWYQ2 | ₹29,800 | ₹49,999 | ok |  | [ ] |
| 70 | [INALSA Air Fryer Oven/16L, 1800W/Stainless Steel Body12-in-1 Functions,Fry,Bak](https://www.amazon.in/dp/B0DWN8CQ74) | B0DWN8CQ74 | ₹9,699 | ₹23,995 | ok |  | [ ] |
| 71 | [Blend Art 1000W Juicer Mixer Grinder for Kitchen & Home Use / 1.5L Blending Ja](https://www.amazon.in/dp/B0FMZQ9FSB) | B0FMZQ9FSB | ₹5,699 | ₹9,500 | ok |  | [ ] |
| 72 | [LG 185 L, 4 Star, Smart Inverter, Direct Cool Single Door Refrigerator (GLD194](https://www.amazon.in/dp/B0GRCY68XY) | B0GRCY68XY | ₹17,490 | ₹24,490 | ok |  | [ ] |
| 73 | [Nothing Phone (4a) Pro (Silver, 8GB, 128GB)](https://www.amazon.in/dp/B0GRG8SKTT) | B0GRG8SKTT | ₹45,549 | ₹69,999 | ok |  | [ ] |
| 74 | [TCL 101 cms (40 inches) V5C Series Full HD Smart QLED TV Google TV 40V5C](https://www.amazon.in/dp/B0DZHRYFG7) | B0DZHRYFG7 | ₹22,490 | ₹32,390 | ok |  | [ ] |
| 75 | [Mabron K30 Bluetooth Calling Smart Watch with Heart Rate, Pedometer, Waterproo](https://www.amazon.in/dp/B0BFLV2XNW) | B0BFLV2XNW | ₹2,879 | ₹8,999 | ok |  | [ ] |
| 76 | [Supersonic IQ Sound IQ-3520RGB 2.0CH Portable Bluetooth Speaker with RGB Panel](https://www.amazon.in/dp/B0CNQD1524) | B0CNQD1524 | ₹9,288 | ₹11,999 | ok |  | [ ] |
| 77 | [Android 15 Tablet 30GB RAM 128GB ROM 1TB Expand, 10 inch Tablets with Octa-Cor](https://www.amazon.in/dp/B0FV86MKNX) | B0FV86MKNX | ₹19,885 | ₹18,900 | ok |  | [ ] |
| 78 | [AGARO Ace Wet & Dry Vacuum Cleaner, 1600 Watts, 21.5 Kpa Suction Power, 30 lit](https://www.amazon.in/dp/B0CQGL8ND6) | B0CQGL8ND6 | ₹7,599 | ₹11,499 | ok |  | [ ] |
| 79 | [Electrolux 8kg 5 Star Front Load Washing Machine, 5 Year Warranty, AutoSense T](https://www.amazon.in/dp/B0DF3N46MG) | B0DF3N46MG | ₹44,990 | ₹81,490 | ok |  | [ ] |
| 80 | [Aquaguard Aspire Halo RO+UV CU ALK SS 2X WQI Water purifier](https://www.amazon.in/dp/B0GY145PN5) | B0GY145PN5 | ₹22,800 | ₹31,000 | ok |  | [ ] |
| 81 | [Carrier Smart Air Conditioners 2025 Models](https://www.amazon.in/dp/B0DSXJFF5H) | B0DSXJFF5H | ₹44,450 | ₹75,990 | ok |  | [ ] |
| 82 | [Glacier Air 40 Personal Air Cooler (40L, White) - 2600 RPM Ultra High-Speed Mo](https://www.amazon.in/dp/B0GQ3FFRGH) | B0GQ3FFRGH | ₹8,990 | ₹17,980 | ok |  | [ ] |
| 83 | [Sujata Ceiling Fan / 3 Year Warranty / 100% Copper Winding, 1200mm / BEE 1 Sta](https://www.amazon.in/dp/B0DCW6NQ7L) | B0DCW6NQ7L | ₹2,079 | ₹2,988 | ok |  | [ ] |
| 84 | [KRYNORCXY® Premium Gaming Desktop PC / Core i7 6700 Processor / 16GB DDR4 RAM ](https://www.amazon.in/dp/B0H5FC3VD9) | B0H5FC3VD9 | ₹40,999 | ₹80,000 | ok |  | [ ] |
| 85 | [dRoNe wItH hD DuAl cAmErA BrUsHlEsS MoToR, oNe cLiCk tAkEoFf/lAnDiNg FlIp rOlL](https://www.amazon.in/dp/B0H8SQLGXB) | B0H8SQLGXB | ₹9,999 | ₹8,999 | ok |  | [ ] |
| 86 | [Racold Pronto Pro 3L 3KW Vertical Instant Water Heater (Geyser) / Faster Heati](https://www.amazon.in/dp/B097MKZHNV) | B097MKZHNV | ₹2,799 | ₹4,849 | ok |  | [ ] |
| 87 | [Wireless Earbuds, Bluetooth 5.4 Headphones in Ear with HiFi Stereo Deep Bass, ](https://www.amazon.in/dp/B0GQZ3BX3D) | B0GQZ3BX3D | ₹2,992 | ₹4,788 | ok |  | [ ] |
| 88 | [Bosch Pib375Fb1E, 30 Cm, Built In Induction Hob Ceramic Glass 2 Cooking Zones ](https://www.amazon.in/dp/B016QLMF8G) | B016QLMF8G | ₹49,030 | ₹64,490 | ok |  | [ ] |
| 89 | [Lenovo V15 AMD Ryzen 3 7320U 15.6" (39.62cm) FHD 250 Nits Antiglare Thin and L](https://www.amazon.in/dp/B0CSFW9D4W) | B0CSFW9D4W | ₹49,090 | ₹85,000 | ok |  | [ ] |
| 90 | [MultiChef Pro 3 in 1 Breakfast Maker With Oven Toaster Griller, Coffee Maker, ](https://www.amazon.in/dp/B0FZSR2LYZ) | B0FZSR2LYZ | ₹3,499 | ₹9,999 | ok |  | [ ] |
| 91 | [Butterfly Jubilant 3 Jar Mixer Grinder](https://www.amazon.in/dp/B0F3WG1RDW) | B0F3WG1RDW | ₹3,894 | ₹6,549 | ok |  | [ ] |
| 92 | [Haier 598L Frost Free 3-Door 3 Star Side by Side Refrigerator with Convertible](https://www.amazon.in/dp/B0FCXRWLWP) | B0FCXRWLWP | ₹78,690 | ₹140,890 | ok |  | [ ] |
| 93 | [REDMI A7 Pro 5G (Sunset Orange, 4GB RAM, 64GB Storage) / Segment's Fastest Pro](https://www.amazon.in/dp/B0GS5N7M97) | B0GS5N7M97 | ₹14,489 | ₹26,999 | ok |  | [ ] |
| 94 | [VW 109 cm (43 inches) Pro Series 4K Ultra HD Smart QLED Google TV VW43GQ2](https://www.amazon.in/dp/B0GGR9DCCB) | B0GGR9DCCB | ₹21,699 | ₹54,999 | ok |  | [ ] |
| 95 | [Nervfit Fuel S2 Pro Premium Smartwatch with 2.02" TrueColor+ Display, BT Calli](https://www.amazon.in/dp/B0D6KXNTTW) | B0D6KXNTTW | ₹1,859 | ₹10,999 | ok |  | [ ] |
| 96 | [2 PCS Portable Wireless Bluetooth Mini Speakers with Stereo and LED Lights for](https://www.amazon.in/dp/B0FNLKJYR3) | B0FNLKJYR3 | ₹4,647 | ₹2,348 | ok |  | [ ] |
| 97 | [KADYBE Android 15 11 inch Tablet, 2025 Latest Tablets with 16GB RAM 128GB ROM ](https://www.amazon.in/dp/B0FQBXTT7H) | B0FQBXTT7H | ₹19,939 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 98 | [HM800 Robot Vacuum Cleaner with AI Camera Vision, 2-in-1 Vacuum and Mop Combo ](https://www.amazon.in/dp/B08MF7447G) | B08MF7447G | ₹19,998 | N/A | error | amazon_buybox_price_not_exposed | [ ] |
| 99 | [Siemens 8kg 5 Star Stain Treatment Fully Automatic Front Load Washing Machine ](https://www.amazon.in/dp/B0CS6RVQT7) | B0CS6RVQT7 | ₹37,290 | ₹59,490 | ok |  | [ ] |
| 100 | [Aquaguard Enrich Ritz Pro RO+UV+Copper+Alkaline Water Purifier / India’s 1st 4](https://www.amazon.in/dp/B0H44SBX2T) | B0H44SBX2T | ₹19,999 | ₹1,999,900 | ok |  | [ ] |

## Flipkart - 100 products

| # | Open product | SKU | MongoDB price | Fresh price | Status | Error | Manual verified |
|---:|---|---|---:|---:|---|---|---|
| 1 | [strategic 100 L Room/Personal Air Cooler (White, AC01)](https://flipkart.com/strategic-100-l-room-personal-air-cooler/p/itm0793b0b4b6efd?pid=AICHZGRGDH5JXYZH) | AICHZGRGDH5JXYZH | ₹33,001 | ₹33,001 | ok |  | [ ] |
| 2 | [Crompton Hs Plus 1200 Mm 48 Inches High Speed Energy Efficient Button Control ](https://www.flipkart.com/crompton-hs-plus-1200-mm-48-inches-high-speed-energy-efficient-button-control-opal-white-24-months-warranty-saving-mm-ceiling-fan/p/itm4fb1d47bee44a?pid=FANGJ8EZHZ5GNPYW) | FANGJ8EZHZ5GNPYW | ₹2,760 | N/A | error | product_identity_unverified | [ ] |
| 3 | [ASSEMBLEX RYZEN 3 3200G RYZEN 3 3200G (16 GB RAM/Radeon VEGA 8 Graphics/2 TB H](https://www.flipkart.com/assemblex-ryzen-3-3200g-16-gb-ram-radeon-vega-8-graphics-2-tb-hard-disk-256-ssd-capacity-windows-11-pro-4-graphics-memory-gaming-tower/p/itmd9c685dc07293?pid=CPUHH3FTUQKJHPHJ) | CPUHH3FTUQKJHPHJ | ₹44,990 | N/A | error | product_identity_unverified | [ ] |
| 4 | [HG WORLD GD95 Drone With Camera 720p Photo Transmission,GPS FPV Quadcopter Cam](https://www.flipkart.com/hg-world-gd95-drone-camera-720p-photo-transmission-gps-fpv-quadcopter-motion-controller/p/itm40db7d366063a?pid=ACCHG6XXZAHRQERT) | ACCHG6XXZAHRQERT | ₹8,381 | ₹8,381 | ok |  | [ ] |
| 5 | [Kaal 5 L Instant Water Geyser (Water geyser_5L_46, White) (White)](https://flipkart.com/kaal-water-geyser-5l-46-5-l-instant-geyser/p/itm9732c684310ba?pid=WGYHP54ANWZFY7KK) | WGYHP54ANWZFY7KK | ₹4,000 | N/A | error | html_read_failed | [ ] |
| 6 | [Skullcandy Cassette 40mm drivers 22Hrs Playtime+Rapid Charge Collapsible Desig](https://www.flipkart.com/skullcandy-cassette-40mm-drivers-22hrs-playtime-rapid-charge-collapsible-design-lightweight-bluetooth/p/itm940d2f897374c?pid=ACCFXYZRSRMXQDHT) | ACCFXYZRSRMXQDHT | ₹2,999 | ₹2,999 | ok |  | [ ] |
| 7 | [BOSCH 2 W Induction Cooktop Touch Panel (Black, PIB375FB5I)](https://flipkart.com/bosch-2-w-induction-cooktop-touch-panel/p/itmfc8ec486c300e?pid=ICTHPSFWHJRTS3FD) | ICTHPSFWHJRTS3FD | ₹47,136 | N/A | error | product_page_price_not_exposed | [ ] |
| 8 | [Lenovo IdeaPad 3 Intel Intel Core i3 10th Gen - (4 GB/256 GB SSD/Windows 10 Ho](https://www.flipkart.com/lenovo-ideapad-3-intel-core-i3-10th-gen-4-gb-256-gb-ssd-windows-10-home-81wb010xin-laptop/p/itmf7468c9543cbe?pid=COMG7EJFQHPFHG8Q) | COMG7EJFQHPFHG8Q | ₹34,990 | N/A | error | html_read_failed | [ ] |
| 9 | [Syntro 17-Litre Oven Toaster Grill OTG HEALTHIFY 17 LTR, Black, Silver Rotisse](https://www.flipkart.com/syntro-17-litre-oven-toaster-grill-otg-healthify-17-ltr-black-silver/p/itmcbd16fcfb60d5?pid=OTNHNYDAJTRTTFAP) | OTNHNYDAJTRTTFAP | ₹2,472 | ₹2,472 | ok |  | [ ] |
| 10 | [SUJATA 1 900 W Juicer 4.4 34 Ratings & 4 Reviews Power Consumption: 900 W 1 Ja](https://www.flipkart.com/sujata-1-900-w-juicer/p/itm12d15a0b51e13?pid=MIXFKYH7HGJXT8E5) | MIXFKYH7HGJXT8E5 | ₹5,983 | N/A | error | html_read_failed | [ ] |
| 11 | [Godrej 30 L Direct Cool Portable Cooler 2 Star with Base Drawer Without Compre](https://www.flipkart.com/godrej-30-l-direct-cool-portable-cooler-2-star-base-drawer/p/itm76a4238995f2b?pid=RFRGVJH3BGHDGBDZ) | RFRGVJH3BGHDGBDZ | ₹7,740 | N/A | error | html_read_failed | [ ] |
| 12 | [Motorola Edge 50 Ultra 5G (Forest Grey, 512 GB)](https://www.flipkart.com/motorola-edge-50-ultra-5g-forest-grey-512-gb/p/itm075d34e492ff5?pid=MOBGZZACEMCTCHWY) | MOBGZZACEMCTCHWY | ₹49,999 | ₹49,999 | ok |  | [ ] |
| 13 | [Samsung 80 Cm 32 Inch Hd Ready Led Smart Android Tv 2025 Panel Mega Contrast P](https://www.flipkart.com/samsung-80-cm-32-inch-hd-ready-led-smart-android-tv-2025-panel-mega-contrast-purcolor-picture-quality-slim/p/itm5a451f6d43f55?pid=TVSH7XE5QZARKSTG) | TVSH7XE5QZARKSTG | ₹14,768 | ₹14,768 | ok |  | [ ] |
| 14 | [boAt Ultima Prism with 1.96" AMOLED Smartwatch](https://www.flipkart.com/boat-ultima-prism-1-96-amoled-smartwatch/p/itm8ffc978121c9f?pid=SMWGRZZFGHU7U7AT) | SMWGRZZFGHU7U7AT | ₹1,999 | N/A | error | html_read_failed | [ ] |
| 15 | [boAt Aavante 2.1 1200 120 W Bluetooth Soundbar](https://www.flipkart.com/boat-aavante-2-1-1200-120-w-bluetooth-soundbar/p/itmd78e9348a9f8a?pid=ACCHCBVXRFFVK4EQ) | ACCHCBVXRFFVK4EQ | ₹4,299 | ₹4,299 | ok |  | [ ] |
| 16 | [Samsung Galaxy Tab A11+ 8 GB RAM 256 GB ROM 11 inch with Wi-Fi Only Gaming Med](https://www.flipkart.com/samsung-galaxy-tab-a11-8-gb-ram-256-rom-11-inch-wi-fi-only-gaming-mediatek-mt8755-tablet-silver/p/itmb130d4bc695e7?pid=TABHHQEYGTG3P7GF) | TABHHQEYGTG3P7GF | ₹28,999 | N/A | error | product_identity_unverified | [ ] |
| 17 | [Karcher WD 5 Premium EU Wet & Dry Vacuum Cleaner with Anti-Bacterial Cleaning,](https://www.flipkart.com/karcher-wd-5-premium-eu-wet-dry-vacuum-cleaner-anti-bacterial-cleaning-reusable-dust-bag/p/itm2b360f27901fd?pid=VCLHKBHZ5YCUGSGX) | VCLHKBHZ5YCUGSGX | ₹23,724 | ₹23,724 | ok |  | [ ] |
| 18 | [realme TechLife 9 kg Fully Automatic Front Load with In-built Hea... more](https://flipkart.com/realme-techlife-9-kg-fully-automatic-front-load-washing-machine-in-built-heater-blue/p/itm7cc4435409160?pid=WMNHZN5BNEEUHMUH) | WMNHZN5BNEEUHMUH | ₹25,490 | N/A | error | product_identity_unverified | [ ] |
| 19 | [Aquaguard Sure Delight UV+UF 2X 6 L UV + UF Water Purifier / 2 Year Filter Lif](https://www.flipkart.com/aquaguard-sure-delight-uv-uf-2x-6-l-uv-uf-water-purifier-2-year-filter-life-mega-sediment-6-stage-purification-suitable-municipal-only-tds/p/itmfc4c69ff21cac?pid=WAPHCCX8XHKAYGFA) | WAPHCCX8XHKAYGFA | ₹9,499 | ₹7,499 | ok |  | [ ] |
| 20 | [Crompton Energion Hyperjet Bldc Technology Remote Control 2 Year Warranty Ener](https://www.flipkart.com/crompton-energion-hyperjet-bldc-technology-remote-control-2-year-warranty-energy-saving-1200-mm-ceiling-fan/p/itm92ddfbd06f12d?pid=FANGQFKGPPBCDBZF) | FANGQFKGPPBCDBZF | ₹2,949 | N/A | error | product_identity_unverified | [ ] |
| 21 | [iBall 6 Cores up to 3.9GHz 19MB Cache Ryzen 5 2600 (16 RAM/Inbuilt Onboard Gar](https://www.flipkart.com/iball-6-cores-up-3-9ghz-19mb-cache-ryzen-5-2600-16-ram-inbuilt-onboard-garphics-graphics-1-tb-hard-disk-64-gb-ssd-capacity-windows-10-64-bit-1-graphics-memory-mini-tower/p/itm978dc839f95a7?pid=CPUFXUN4UFSHGZZC) | CPUFXUN4UFSHGZZC | ₹44,999 | N/A | error | product_identity_unverified | [ ] |
| 22 | [Swa Mi Live Video, Wifi Drone for Adults With HD 120 De... ₹2,613 ₹ 8,999 70% ](https://www.flipkart.com/safal-kisan-5g-smartwatch-all-sim-support-social-media-voice-call-hd-camera-wifi-gps/p/itmff88b6775fc61?pid=SMWHHKD89BTCDGPK&lid=LSTSMWHHKD89BTCDGPKD1LZZU&marketplace=FLIPKART&q=wembley+camera+drone+gps&store=search.flipkart.com&srno=s_7_264&otracker=search&fm=organic&iid=759643a9-b826-4b00-ac23-3d89ff5423bb.SMWHHKD89BTCDGPK.SEARCH&ppt=None&ppn=None&ssid=abrz9weyg00000001781597513595&qH=3a7ead6d21980855&ov_redirect=true&ov_redirect=true) | SMWHHKD89BTCDGPK | ₹9,040 | N/A | error | product_page_price_not_exposed | [ ] |
| 23 | [Kaal 5 L Instant Water Geyser (Water geyser_5L_42, White) (White)](https://flipkart.com/kaal-water-geyser-5l-42-5-l-instant-geyser/p/itm7aab904e4c639?pid=WGYHP54ZKRJZCSWZ) | WGYHP54ZKRJZCSWZ | ₹4,000 | ₹4,000 | ok |  | [ ] |
| 24 | [boAt Nirvana Nebula w/ Dolby Audio, ANC(35dB), Adaptive EQ & 6-Mics Enx Techno](https://www.flipkart.com/boat-nirvana-nebula-w-dolby-audio-anc-35db-adaptive-eq-6-mics-enx-technology-bluetooth/p/itma0886f935fe06?pid=ACCGZ5TFF6FJFGX4) | ACCGZ5TFF6FJFGX4 | ₹2,999 | ₹2,999 | ok |  | [ ] |
| 25 | [Pigeon 1800 W Induction Cooktop Push Button Black, Prime 7 Preset Indian Menu ](https://www.flipkart.com/wellberg-fast-efficient-2000w-dual-coil-electric-stove-portable-burner-hot-plate-today-cooking-heater/p/itm05549a50783ea?pid=ECCHGYEGSZUVRT47&lid=LSTECCHGYEGSZUVRT47CLEKMR&marketplace=FLIPKART&q=havells+induction+cooktop&store=j9e%2Fm38%2F575&srno=s_6_228&otracker=search&fm=organic&iid=76bc6dc4-905a-412f-ab39-7cd2c533da2c.ECCHGYEGSZUVRT47.SEARCH&ppt=None&ppn=None&ssid=llefayz4hc0000001781598145339&qH=45097ca698aa1654&ov_redirect=true&ov_redirect=true) | ECCHGYEGSZUVRT47 | ₹2,897 | N/A | error | product_identity_unverified | [ ] |
| 26 | [Lenovo IdeaPad 3 Intel Intel Core i3 10th Gen - (8 GB/256 GB SSD/Windows 10 Ho](https://www.flipkart.com/lenovo-ideapad-3-intel-core-i3-10th-gen-8-gb-256-gb-ssd-windows-10-home-81wa00k1in-laptop/p/itmf7468c9543cbe?pid=COMG57X3HRJ5C8KC) | COMG57X3HRJ5C8KC | ₹34,990 | N/A | error | product_identity_unverified | [ ] |
| 27 | [MODI 10-Litre Oven Toaster Grill OTG MOTG10L, Black Convection Rotisserie 1 Ye](https://www.flipkart.com/modi-10-litre-oven-toaster-grill-otg-motg10l-black/p/itme354885555f43?pid=OTNHNCGJD3TU2VKQ) | OTNHNCGJD3TU2VKQ | ₹2,762 | N/A | error | html_read_failed | [ ] |
| 28 | [Prestige Wnder JMG 550 W Juicer Mixer Grinder 3.](https://www.flipkart.com/prestige-wnder-jmg-550-w-juicer-mixer-grinder/p/itm0eaf371a0db73?pid=MIXF637HPFFJRYTJ) | MIXF637HPFFJRYTJ | ₹3,855 | ₹3,855 | ok |  | [ ] |
| 29 | [Godrej 30 L Direct Cool Single Door Refrigerator (Black, QUBE 30L... more](https://flipkart.com/godrej-30-l-qube-personal-cooling-solution/p/itm76a4238995f2b?pid=RFRFFMH6SYA4D3B3) | RFRFFMH6SYA4D3B3 | ₹7,740 | ₹7,790 | ok |  | [ ] |
| 30 | [REDMI Note 15 Pro+ 5G Special Edition Carbon Black 16GB RAM 512GB... more](https://flipkart.com/redmi-note-15-pro-5g-special-carbon-black-16gb-ram-512gb-rom-carbon-black-512-gb/p/itmbbff4d12d3216?pid=MOBHPHU74JNPCVC7) | MOBHPHU74JNPCVC7 | ₹46,999 | ₹46,999 | ok |  | [ ] |
| 31 | [Onida 80 cm (32 inch) Smart Genius Series HD Ready Smart LED TV 3... more](https://flipkart.com/onida-80-cm-32-inch-smart-genius-series-hd-ready-led-tv-32has-coolita-2025-dolby-digital-supported-apps-youtube-prime-video-sonyliv-hungama-jiocinema-zee5-eros-now-included-components-1-number-unit-remote-control-mini-ev-cable-power-cord-wall-mount-kit-user-manual-2-aaa-batteries-stands-4-stand-screw1-numb-see-more-connectivity-technology-hdmi-usb-wi-fi-aspect-ratio-16-9-product-dimensions-18d-x-73-5w-47-6h-centimeters/p/itm3d4e3b0244b0a?pid=TVSHQGZZMAVYHTAT) | TVSHQGZZMAVYHTAT | ₹15,890 | N/A | error | product_identity_unverified | [ ] |
| 32 | [boAt Ultma Prism with 1.96" AMOLED Display,BT Calling, bt Coins & Watch Face S](https://www.flipkart.com/boat-ultma-prism-1-96-amoled-display-bt-calling-bt-coins-watch-face-studio-smartwatch/p/itmcb71c69f7fc84?pid=SMWGRZZFGWVYZAPN) | SMWGRZZFGWVYZAPN | ₹1,999 | ₹1,999 | ok |  | [ ] |
| 33 | [boAt Aavante Bar 600 w/ Dual Passive Radiators, 7HRS Playback & Portable Desig](https://www.flipkart.com/boat-aavante-bar-600-w-dual-passive-radiators-7hrs-playback-portable-design-25-w-bluetooth-soundbar/p/itm27bac99f0e5ff?pid=ACCH4EHGBTUXYVG5) | ACCH4EHGBTUXYVG5 | ₹1,699 | ₹1,699 | ok |  | [ ] |
| 34 | [REDMI Pad 2 Pro 5G 8 GB RAM 256 GB ROM 12.1 inch with Wi-Fi+5G Gaming Qualcomm](https://www.flipkart.com/redmi-pad-2-pro-5g-8-gb-ram-256-rom-12-1-inch-wi-fi-5g-gaming-qualcomm-snapdragon-7s-gen-4-tablet-quick-silver/p/itm420d5d1297f9a?pid=TABHJFBZH5HAMGQF) | TABHJFBZH5HAMGQF | ₹32,999 | N/A | error | product_identity_unverified | [ ] |
| 35 | [EUREKA FORBES Ultimo Wet & Dry Vacuum Cleaner](https://www.flipkart.com/eureka-forbes-ultimo-wet-dry-vacuum-cleaner/p/itmb4f00070a157d?pid=VCLFMBWGHGTRGHMZ) | VCLFMBWGHGTRGHMZ | ₹9,730 | N/A | error | html_read_failed | [ ] |
| 36 | [TOSHIBA 7.5 kg Fully Automatic Front Load Washing Machine with In-built Heater](https://www.flipkart.com/toshiba-7-5-kg-fully-automatic-front-load-washing-machine-in-built-heater-silver/p/itm79d9fb15424ea?pid=WMNGADHGCYQFNKEG) | WMNGADHGCYQFNKEG | ₹48,990 | N/A | error | html_read_failed | [ ] |
| 37 | [Aquaguard Sure Delight RO+UV 1X 6 L RO + UV Water Purifier / 5-Stage Purificat](https://www.flipkart.com/aquaguard-sure-delight-ro-uv-1x-6-l-ro-uv-water-purifier-5-stage-purification-suitable-all-borewell-tanker-municipality/p/itm4f7d66214aa49?pid=WAPGH4ZWWFHNNVTD) | WAPGH4ZWWFHNNVTD | ₹9,499 | ₹7,499 | ok |  | [ ] |
| 38 | [BAJAJ Crest Turbo BLDC 1200mm Red Walnut with 2 Months](https://www.flipkart.com/bajaj-crest-turbo-bldc-1200mm-red-walnut-2-months-warranty-motor-remote-1200-mm-ceiling-fan/p/itm0b58de62a82bb?pid=FANHYVZ36HQGES3G) | FANHYVZ36HQGES3G | ₹1,999 | N/A | error | html_read_failed | [ ] |
| 39 | [Acer Aspire AMD Ryzen 3 7330U - (8 GB/256 GB SSD/Windows 11 Home)... more](https://flipkart.com/acer-aspire-amd-ryzen-3-7330u-8-gb-256-gb-ssd-windows-11-home-al15-42-notebook/p/itm7c9587abd46b9?pid=COMHQMKSDZZFYCZR) | COMHQMKSDZZFYCZR | ₹39,990 | N/A | error | product_identity_unverified | [ ] |
| 40 | [Kaal 5 L Instant Water Geyser (Water geyser_5L_32, White) (White)](https://flipkart.com/kaal-water-geyser-5l-32-5-l-instant-geyser/p/itm76bab4d8af554?pid=WGYHP5472HUHG4BM) | WGYHP5472HUHG4BM | ₹4,000 | N/A | error | html_read_failed | [ ] |
| 41 | [OPPO Enco Buds3 Pro+ with ANC Bluetooth](https://www.flipkart.com/oppo-enco-buds3-pro-anc-bluetooth/p/itm5b84c15e375b3?pid=ACCHHHAGB3GDTXPK) | ACCHHHAGB3GDTXPK | ₹2,499 | ₹2,499 | ok |  | [ ] |
| 42 | [PHILIPS 2000 W Induction Cooktop Touch Panel (Black, HD4938/01)](https://flipkart.com/philips-2000-w-induction-cooktop-touch-panel/p/itmc84ebcf14d90f?pid=ICTH25BMYQXGTSQH) | ICTH25BMYQXGTSQH | ₹4,849 | N/A | error | product_page_price_not_exposed | [ ] |
| 43 | [ASUS Chromebook CX14 Intel Celeron Dual Core N4500 - (4 GB/64 GB ... more](https://flipkart.com/asus-chromebook-cx14-intel-celeron-dual-core-n4500-4-gb-64-gb-emmc-storage-chrome-os-cx1405cka-nk0154-cx1405cka-s60342/p/itm076cdd51ac69a?pid=COMHDDZ7PYJZSGUZ) | COMHDDZ7PYJZSGUZ | ₹28,411 | N/A | error | product_identity_unverified | [ ] |
| 44 | [Cadlec 28-Litre Oven Toaster Grill OTG OvenMate, Silver and Black 3.9 2,084 Ra](https://www.flipkart.com/cadlec-28-litre-oven-toaster-grill-otg-ovenmate-silver-black/p/itmd187d388be264?pid=OTNHHJRYAG4RGZK9) | OTNHHJRYAG4RGZK9 | ₹3,299 | N/A | error | product_identity_unverified | [ ] |
| 45 | [Prestige Supreme 550 W Mixer Grinder 4.](https://www.flipkart.com/prestige-supreme-550-w-mixer-grinder/p/itm379466fe89020?pid=MIXFA85AA7NXFFHY) | MIXFA85AA7NXFFHY | ₹3,775 | ₹3,775 | ok |  | [ ] |
| 46 | [REDMI Note 15 Pro+ 5G Special Edition Mirage Blue 16GB RAM 512GB ... more](https://flipkart.com/redmi-note-15-pro-5g-special-mirage-blue-16gb-ram-512gb-rom-mirage-blue-512-gb/p/itmedab5f2fe1d51?pid=MOBHPHU77SGPHGMG) | MOBHPHU77SGPHGMG | ₹46,999 | N/A | error | html_read_failed | [ ] |
| 47 | [GARMIN Forerunner 165 Music, Black (A0714) Smartwatch](https://www.flipkart.com/garmin-forerunner-165-music-black-a0714-smartwatch/p/itm8cd0436d11c5a?pid=SMWHA25EAYKBYTMN) | SMWHA25EAYKBYTMN | ₹33,990 | ₹33,990 | ok |  | [ ] |
| 48 | [boAt Aavante Bar 2000 Pro w/ Wireless Subwoofer, Sleek Design & Remote Control](https://www.flipkart.com/boat-aavante-bar-2000-pro-w-wireless-subwoofer-sleek-design-remote-control-200-w-bluetooth-soundbar/p/itm7e71cbbf622ff?pid=ACCGPN5HXE8ZR7SD) | ACCGPN5HXE8ZR7SD | ₹9,499 | N/A | error | html_read_failed | [ ] |
| 49 | [Samsung Galaxy Tab A11+ 8 GB RAM 256 GB ROM 11 inch with Wi-Fi Only Gaming Med](https://www.flipkart.com/samsung-galaxy-tab-a11-8-gb-ram-256-rom-11-inch-wi-fi-only-gaming-mediatek-mt8755-tablet-gray/p/itmb130d4bc695e7?pid=TABHHQEY5EVPKKTE) | TABHHQEY5EVPKKTE | ₹34,648 | N/A | error | html_read_failed | [ ] |
| 50 | [Narwal YJCC015 Robotic Floor Cleaner with 13000Pa Hyper Suction, 7 weeks dust ](https://www.flipkart.com/narwal-yjcc015-robotic-floor-cleaner-13000pa-hyper-suction-7-weeks-dust-storage-self-emptying-zero-tangling-floating-brush-trilaser-obstacle-avoidance-1l-disposable-bag/p/itmdfab0facda195?pid=VCLHZ2CQFQWVGKAJ) | VCLHZ2CQFQWVGKAJ | ₹49,990 | N/A | error | html_read_failed | [ ] |
| 51 | [TOSHIBA 7 kg Fully Automatic Front Load Washing Machine with In-built Heater W](https://www.flipkart.com/toshiba-7-kg-fully-automatic-front-load-washing-machine-in-built-heater-white/p/itmbb61bf0f2d0aa?pid=WMNGADHGDJQEJVFF) | WMNGADHGDJQEJVFF | ₹28,639 | ₹28,639 | ok |  | [ ] |
| 52 | [Aquaguard Champ 6 L RO + UV Water Purifier 4.](https://www.flipkart.com/aquaguard-champ-6-l-ro-uv-water-purifier/p/itm579fe556323be?pid=WAPHY85ACKDPVXFM) | WAPHY85ACKDPVXFM | ₹9,499 | ₹9,499 | ok |  | [ ] |
| 53 | [BAJAJ Crest Turbo BLDC with 2 Year Warranty 1200 mm Ceiling Fan](https://www.flipkart.com/bajaj-crest-turbo-bldc-2-year-warranty-1200-mm-ceiling-fan/p/itm59b0bd161ff7d?pid=FANGZNC8TBDASHCU) | FANGZNC8TBDASHCU | ₹1,999 | N/A | error | html_read_failed | [ ] |
| 54 | [ASSEMBLEX all in one i7 7TH GAMING PC Core i7 (7th Gen) (16 GB DDR4/1 TB/256 G](https://www.flipkart.com/assemblex-all-one-i7-7th-gaming-pc-core-7th-gen-16-gb-ddr4-1-tb-256-ssd-windows-11-home-4-gb-24-inch-screen-infrio-ms-office/p/itm9abde77a3f1d3?pid=AIOHKR53BZ5YDXNQ) | AIOHKR53BZ5YDXNQ | ₹50,000 | ₹50,000 | ok |  | [ ] |
| 55 | [Racold Pronto Pro SS 3V-3KW 3 L Instant Water Geyser / High Grade SS Tank 4.2 ](https://www.flipkart.com/racold-pronto-pro-ss-3v-3kw-3-l-instant-water-geyser-high-grade-tank/p/itma60cd952e0f8d?pid=WGYG4XTC4WKV7J5V) | WGYG4XTC4WKV7J5V | ₹2,799 | ₹2,799 | ok |  | [ ] |
| 56 | [realme Buds Wireless 5 with 50dB ANC, 360 degree Spatial Audio, IP55 and 38hrs](https://www.flipkart.com/realme-buds-wireless-5-50db-anc-360-degree-spatial-audio-ip55-38hrs-playback-bluetooth/p/itmf4d9560c6b3fc?pid=ACCH6SR8NYS7A3ZR) | ACCH6SR8NYS7A3ZR | ₹1,699 | ₹1,699 | ok |  | [ ] |
| 57 | [PHILIPS 2100 W Induction Cooktop Push Button (Silver, Black, HD49... more](https://flipkart.com/philips-2100-w-induction-cooktop-push-button/p/itmf78dcue7vvmqg?pid=ICTDGRVGHPYRHHHK) | ICTDGRVGHPYRHHHK | ₹4,644 | N/A | error | product_page_price_not_exposed | [ ] |
| 58 | [Acer Intel Celeron Dual Core N4500 - (8 GB/128 GB SSD/Windows 11 ... more](https://flipkart.com/acer-intel-celeron-dual-core-n4500-8-gb-128-gb-ssd-windows-11-home-a311-45-notebook/p/itm2f21760b8a3c2?pid=COMHPE3DBQ3VMCQT) | COMHPE3DBQ3VMCQT | ₹26,990 | N/A | error | html_read_failed | [ ] |
| 59 | [FABER FAF CrispX 4.0L Bk 1300W Fry,Roast,Grill,Bake,Digital Displ... more](https://flipkart.com/faber-faf-crispx-4-0l-bk-1300w-fry-roast-grill-bake-digital-display-swirl-cooking-air-fryer/p/itm037cfbd2937d2?pid=AFRHM36AUWJSVFWB) | AFRHM36AUWJSVFWB | ₹3,129 | ₹2,999 | ok |  | [ ] |
| 60 | [Prestige 230V 750 W Mixer Grinder 3.](https://www.flipkart.com/prestige-230v-750-w-mixer-grinder/p/itm736f04fbb0246?pid=MIXHYNFYMMS4CZ9E) | MIXHYNFYMMS4CZ9E | ₹3,940 | N/A | error | fetch_failed:TimeoutError | [ ] |
| 61 | [REDMI Note 15 Pro+ 5G Special Edition Coffee Mocha 16GB RAM 512GB... more](https://flipkart.com/redmi-note-15-pro-5g-special-coffee-mocha-16gb-ram-512gb-rom-coffee-mocha-512-gb/p/itm2a082fd4b24b2?pid=MOBHPHU7QHRVGRW2) | MOBHPHU7QHRVGRW2 | ₹46,999 | ₹46,999 | ok |  | [ ] |
| 62 | [Samsung Galaxy Watch7 44mm BT](https://www.flipkart.com/samsung-galaxy-watch7-44mm-bt/p/itm8833945882e8a?pid=SMWH2EHFZFHQTFSG) | SMWH2EHFZFHQTFSG | ₹32,999 | ₹32,999 | ok |  | [ ] |
| 63 | [Mivi Fort H750 Soundbar, 750 Watts, Dolby Audio, 5.1 Channel, Multi-Input & EQ](https://www.flipkart.com/mivi-fort-h750-soundbar-750-watts-dolby-audio-5-1-channel-multi-input-eq-modes-w-bluetooth-soundbar/p/itm04060c0b96b2a?pid=ACCH3MUYEGHH2WGD) | ACCH3MUYEGHH2WGD | ₹7,499 | ₹7,499 | ok |  | [ ] |
| 64 | [OnePlus Pad Lite 6 GB RAM 128 GB ROM 11.0 inch with Wi-Fi Only Gaming MediaTek](https://flipkart.com/oneplus-pad-lite-6-gb-ram-128-rom-11-0-inch-wi-fi-only-gaming-mediatek-helio-g100-tablet-aero-blue/p/itm5b2d512cb261f?pid=TABHE7YR2Y7XJHFA) | TABHE7YR2Y7XJHFA | ₹19,999 | N/A | error | html_read_failed | [ ] |
| 65 | [Arrom WIRELESS Vacuum Cleaner with Powerful Suction, Cordless Tec... more](https://flipkart.com/arrom-wireless-vacuum-cleaner-powerful-suction-cordless-technology-rechargable-anti-bacterial-cleaning/p/itm1f435c63046bb?pid=VCLHF5MQFF8ZFHYM) | VCLHF5MQFF8ZFHYM | ₹990 | N/A | error | product_identity_unverified | [ ] |
| 66 | [TOSHIBA 8 kg Fully Automatic Front Load Washing Machine with In-built Heater W](https://www.flipkart.com/toshiba-8-kg-fully-automatic-front-load-washing-machine-in-built-heater-white/p/itmbb61bf0f2d0aa?pid=WMNGADHGYGGZB7H8) | WMNGADHGYGGZB7H8 | ₹49,990 | ₹49,990 | ok |  | [ ] |
| 67 | [Aquaguard Aspire Blaze 2x Hot & Ambient/2 Year Filter Life/9 Stage Purificatio](https://www.flipkart.com/aquaguard-aspire-blaze-2x-hot-ambient-2-year-filter-life-9-stage-purification-5-6-l-ro-uv-minerals-steel-tank-water-purifier/p/itm7bf618c6b90dc?pid=WAPHGANZGK5D7JGZ) | WAPHGANZGK5D7JGZ | ₹23,400 | N/A | error | fetch_failed:TimeoutError | [ ] |
| 68 | [Om Enterprise ALTRIX 600 MM with 2 Year Warranty Anti Dust, Anti Rust, High Ai](https://www.flipkart.com/om-enterprise-altrix-600-mm-2-year-warranty-anti-dust-rust-high-air-delivery-ultra-speed-ceiling-fan/p/itm691cd1ae4f7a4?pid=FANHZ6GVFB4C2ARZ) | FANHZ6GVFB4C2ARZ | ₹2,000 | N/A | error | html_read_failed | [ ] |
| 69 | [ASSEMBLEX CORE i7 GAMING SERISE intel core i7 7TH (16 GB RAM/intel HD H110 Gra](https://www.flipkart.com/assemblex-core-i7-gaming-serise-intel-7th-16-gb-ram-intel-hd-h110-graphics-1-tb-hard-disk-256-ssd-capacity-windows-11-pro-4-graphics-memory-tower/p/itmc5fcad52dafb3?pid=CPUHKUHGKHVE8SH7) | CPUHKUHGKHVE8SH7 | ₹50,000 | N/A | error | product_identity_unverified | [ ] |
| 70 | [Crompton Arno Neo 3 L Instant Water Geyser 4.1 19,245 Ratings & 1,133 Reviews ](https://www.flipkart.com/crompton-arno-neo-3-l-instant-water-geyser/p/itmf4a94c4c3d28b?pid=WGYHDVAZWR5ZUJZA&lid=LSTWGYHDVAZWR5ZUJZAHP3KZF&marketplace=FLIPKART&q=storage+geyser+3000+watt&store=j9e%2Fabm%2Fbfm&srno=s_5_113&otracker=search&fm=organic&iid=b0bcf752-0a89-45e8-b2ad-a07234868457.WGYHDVAZWR5ZUJZA.SEARCH&ppt=None&ppn=None&ssid=y7xcf6bmwg0000001781597860156&qH=56dcc2cc598a0fd4&ov_redirect=true) | WGYHDVAZWR5ZUJZA | ₹2,799 | ₹2,799 | ok |  | [ ] |
| 71 | [ACwO DwOTS 333 Hybrid ANC 48dB, 6 Mics AI-ENC Earbuds, 120H Playtime, Dual Pai](https://www.flipkart.com/acwo-dwots-333-hybrid-anc-48db-6-mics-ai-enc-earbuds-120h-playtime-dual-pairing-bluetooth/p/itm8a671eab84dba?pid=ACCHHQREGGHJSHXF) | ACCHHQREGGHJSHXF | ₹1,739 | N/A | error | html_read_failed | [ ] |
| 72 | [PHILIPS 2000 W Induction Cooktop Push Button (Maroon, HD4994/00)](https://flipkart.com/philips-2000-w-induction-cooktop-push-button/p/itm29aab75993aa5?pid=ICTH4M5J7G8MFFTP) | ICTH4M5J7G8MFFTP | ₹4,175 | N/A | error | html_read_failed | [ ] |
| 73 | [Acer Aspire 3 Intel Celeron Dual Core - (8 GB/512 GB SSD/Windows 11 Home) A311](https://www.flipkart.com/acer-aspire-3-intel-celeron-dual-core-8-gb-512-gb-ssd-windows-11-home-a311-45-thin-light-laptop/p/itme28afb5d98cef?pid=COMHKNYGCAHFXPED) | COMHKNYGCAHFXPED | ₹39,990 | N/A | error | product_identity_unverified | [ ] |
| 74 | [Pigeon 25-Litre with Rotisserie Oven Toaster Grill OTG 19003847/19003848, Blac](https://www.flipkart.com/pigeon-25-litre-rotisserie-oven-toaster-grill-otg-19003847-19003848-black/p/itmc37998f02fd67?pid=OTNFKYG5NFJBM9NE) | OTNFKYG5NFJBM9NE | ₹3,199 | ₹3,499 | ok |  | [ ] |
| 75 | [Prestige Zestar /3 Super-Efficient Blades 500 W Mixer Grinder Power Consumptio](https://www.flipkart.com/prestige-zestar-3-super-efficient-blades-500-w-mixer-grinder/p/itm6034dcbf28f5a?pid=MIXHGCG2QGQRNW4H) | MIXHGCG2QGQRNW4H | ₹3,945 | ₹3,945 | ok |  | [ ] |
| 76 | [REDMI 12 5G (Jade Black, 256 GB)](https://www.flipkart.com/redmi-12-5g-jade-black-256-gb/p/itm7389f9825ace3?pid=MOBGS9T6GHDKPSQD) | MOBGS9T6GHDKPSQD | ₹14,495 | N/A | error | html_read_failed | [ ] |
| 77 | [GARMIN Forerunner 70 GPS Running Smartwatch With Advanced Training Metrics Sma](https://www.flipkart.com/garmin-forerunner-70-gps-running-smartwatch-advanced-training-metrics/p/itm14b701302b7d1?pid=SMWHZF4YDYFTN2Z6) | SMWHZF4YDYFTN2Z6 | ₹32,990 | ₹32,990 | ok |  | [ ] |
| 78 | [boAt Aavante 2.1 2000D, Dolby Audio, EQ Modes, Multiple Ports, Remote Control ](https://www.flipkart.com/boat-aavante-2-1-2000d-dolby-audio-eq-modes-multiple-ports-remote-control-200-w-bluetooth-soundbar/p/itmcc06bf302b0b5?pid=ACCHDZR8K8EX67E2) | ACCHDZR8K8EX67E2 | ₹8,999 | ₹9,999 | ok |  | [ ] |
| 79 | [realme Pad 2 8 GB RAM 256 GB ROM 11.5 inch with 4G MediaTek G99 Tablet (Inspir](https://www.flipkart.com/realme-pad-2-8-gb-ram-256-rom-11-5-inch-4g-mediatek-g99-tablet-inspiration-green/p/itmcf4c6380eafa4?pid=TABGRGWKPGVZZFSA) | TABGRGWKPGVZZFSA | ₹22,999 | N/A | error | product_identity_unverified | [ ] |
| 80 | [Narwal Flow Compact Robotic Floor Cleaner with 22000Pa HyperSucti... more](https://flipkart.com/narwal-flow-compact-robotic-floor-cleaner-22000pa-hypersuction-truly-handsfree-automatic-refill-drainage-system-120-day-dust-storage-12mm-mop-lifting-maintenance-free-filter/p/itm51ed0bef9d35a?pid=VCLHZ2FHYXJ39VUQ) | VCLHZ2FHYXJ39VUQ | ₹119,990 | N/A | error | product_identity_unverified | [ ] |
| 81 | [IFB 6 kg 5 Star with Steam Refresh program, 9 Swirl Wash, Eco Inverter, Powere](https://www.flipkart.com/ifb-6-kg-5-star-steam-refresh-program-9-swirl-wash-eco-inverter-powered-ai-power-fully-automatic-front-load-washing-machine-in-built-heater-white-black/p/itm7b2e543317b33?pid=WMNH3F28KTYR6GNE) | WMNH3F28KTYR6GNE | ₹24,990 | N/A | error | product_identity_unverified | [ ] |
| 82 | [Aquaguard GWPDVERUM03000 6.2 L RO + UV Water Purifier Electrical & Storage Fil](https://www.flipkart.com/aquaguard-gwpdverum03000-6-2-l-ro-uv-water-purifier/p/itmffd29e2830ffd?pid=WAPH6ZYRWM3B6ZS7) | WAPH6ZYRWM3B6ZS7 | ₹15,079 | ₹15,079 | ok |  | [ ] |
| 83 | [Dewon Electric Himora Bldc 28W Smart Energy Efficient 215 Cmm 2 Year Warranty ](https://www.flipkart.com/dewon-electric-himora-bldc-28w-smart-energy-efficient-215-cmm-2-year-warranty-remote-controlled-silent-operation-1200-mm-ceiling-fan/p/itmcf9a86034a229?pid=FANHHPPXJRSKYNFR) | FANHHPPXJRSKYNFR | ₹2,000 | N/A | error | product_identity_unverified | [ ] |
| 84 | [Frontech all in one i5 8TH Core i5 (8th Gen) (32 GB DDR4/2 TB/512 GB SSD/Windo](https://www.flipkart.com/frontech-all-one-i5-8th-core-8th-gen-32-gb-ddr4-2-tb-512-ssd-windows-11-home-24-inch-screen-all-8th-ms-office/p/itm982a14362e413?pid=AIOHH5HW2FG8HPYA) | AIOHH5HW2FG8HPYA | ₹50,020 | ₹50,020 | ok |  | [ ] |
| 85 | [FABER FWG Zippy 3.0 3 L Instant Water Geyser 3.9 52 Ratings & 6 Reviews Instan](https://www.flipkart.com/faber-fwg-zippy-3-0-3-l-instant-water-geyser/p/itme227421dc0a7b?pid=WGYH28HQDRPYHCK3) | WGYH28HQDRPYHCK3 | ₹2,950 | ₹2,950 | ok |  | [ ] |
| 86 | [JBL Wave100 with 20 Hours Playback, Dual Sound Modes, Dual Connect and VA Supp](https://www.flipkart.com/jbl-wave100-20-hours-playback-dual-sound-modes-connect-va-support-bluetooth/p/itm6260c3844f47a?pid=ACCG4HYUANMYMTZR) | ACCG4HYUANMYMTZR | ₹6,999 | ₹6,999 | ok |  | [ ] |
| 87 | [PHILIPS 1500 W Induction Cooktop Touch Panel (Black, Grey, HD4944... more](https://flipkart.com/philips-1500-w-induction-cooktop-touch-panel/p/itm644578d3c0a2a?pid=ICTHR9NZRNFPDDFG) | ICTHR9NZRNFPDDFG | ₹3,996 | N/A | error | html_read_failed | [ ] |
| 88 | [Lenovo AMD Ryzen 5 - (8 GB/512 GB SSD/Windows 11 Home) 82R400BGIN Thin and Lig](https://www.flipkart.com/lenovo-amd-ryzen-5-8-gb-512-gb-ssd-windows-11-home-82r400bgin-thin-light-laptop/p/itm09d699c84f79a?pid=COMGTTBFCYKUHQEG) | COMGTTBFCYKUHQEG | ₹37,990 | ₹37,990 | ok |  | [ ] |
| 89 | [FABER 82-Litre Oven Toaster Grill OTG Built-in oven with 11 Functions & Rotiss](https://www.flipkart.com/faber-82-litre-oven-toaster-grill-otg-built-in-11-functions-rotisserie-air-frying-fbio-82l-11f-af-bk-black/p/itm22c095f9286bd?pid=OTNHMZ7GUU5CDFGX) | OTNHMZ7GUU5CDFGX | ₹52,990 | N/A | error | product_identity_unverified | [ ] |
| 90 | [Prestige Delight Mixer Grinder 600 W Mixer Grinder Delight / 3 Jars / Blue 4.3](https://www.flipkart.com/nevia-wonder-mix-550-w-mixer-grinder/p/itm623b378047628?pid=MIXHMD7DE3QCPFTT&lid=LSTMIXHMD7DE3QCPFTTWQBXWP&marketplace=FLIPKART&q=mixer+grinder+3+jars&store=j9e%2Fm38&srno=s_2_76&otracker=search&fm=organic&iid=962a5caa-33d4-4ba2-8a3d-a916f03f9060.MIXHMD7DE3QCPFTT.SEARCH&ppt=None&ppn=None&ssid=f1mw50ajqo0000001781598658895&qH=b2aad0bf74f0a410&ov_redirect=true&ov_redirect=true) | MIXHMD7DE3QCPFTT | ₹1,689 | ₹1,670 | ok |  | [ ] |
| 91 | [OPPO Reno 12 Pro 5G (Space Brown, 512 GB) 4.4 5](https://flipkart.com/oppo-reno-12-pro-5g-space-brown-512-gb/p/itmed01efe011f83?pid=MOBH2AHZH779MGYF) | MOBH2AHZH779MGYF | ₹38,999 | N/A | out_of_stock |  | [ ] |
| 92 | [Withings Scanwatch Nova Brilliant Heart Health Monitor,ECG,SPO2,30 Day Battery](https://www.flipkart.com/withings-scanwatch-nova-brilliant-heart-health-monitor-ecg-spo2-30-day-battery-hybrid-smartwatch/p/itm4f0ca8202bf43?pid=SMWH9MHGTSZSVHHC) | SMWH9MHGTSZSVHHC | ₹39,999 | ₹39,999 | ok |  | [ ] |
| 93 | [boAt PartyPal 230, 90W, Karaoke Auto Tuner, 1 UHF Mic, RGB LEDs, ... more](https://flipkart.com/boat-partypal-230-90w-karaoke-auto-tuner-1-uhf-mic-rgb-leds-app-support-tws-mode-90-w-bluetooth-party-speaker/p/itm306b0495b9912?pid=ACCHZGT7XZCWBNQG) | ACCHZGT7XZCWBNQG | ₹6,499 | ₹5,999 | ok |  | [ ] |
| 94 | [Samsung Galaxy Tab A11+ 6 GB RAM 128 GB ROM 11 inch with Wi-Fi+5G Gaming Media](https://www.flipkart.com/samsung-galaxy-tab-a11-6-gb-ram-128-rom-11-inch-wi-fi-5g-gaming-mediatek-mt8755-tablet-gray/p/itm0c62739da9f41?pid=TABHHQEYGFNBJMB9) | TABHHQEYGFNBJMB9 | ₹28,999 | N/A | error | product_identity_unverified | [ ] |
| 95 | [ECOVACS T80 Omni Black Robotic Floor Cleaner with 2 in 1 Mopping and Vacuum, A](https://www.flipkart.com/ecovacs-t80-omni-black-robotic-floor-cleaner-2-1-mopping-vacuum-anti-bacterial-cleaning-reusable-dust-bag-wifi-connectivity-google-assistant-alexa/p/itm8b56d5cf63cab?pid=VCLHKCMFVK7PH4FA) | VCLHKCMFVK7PH4FA | ₹99,999 | N/A | error | product_identity_unverified | [ ] |
| 96 | [HAVELLS 9 kg Fully Automatic Top Load Washing Machine with In-built Heater Bro](https://www.flipkart.com/havells-9-kg-fully-automatic-top-load-washing-machine-in-built-heater-brown/p/itmfe80728db31c2?pid=WMNHMNGGDYMJXMSN) | WMNHMNGGDYMJXMSN | ₹24,990 | N/A | error | product_page_price_not_exposed | [ ] |
| 97 | [Aquaguard Enrich Marvel Uv Uf 2X 6 L Uv Uf Water Purifier 2 Year Filter Life M](https://www.flipkart.com/aquaguard-enrich-marvel-uv-uf-2x-6-l-uv-uf-water-purifier-2-year-filter-life-mega-sediment-3-in-1-active-copper-technology-e-boiling-9-stage-purification-suitable-municipal-tds/p/itm886ea9b7c8aaa?pid=WAPHCCX8EWY7DYYE) | WAPHCCX8EWY7DYYE | ₹14,499 | ₹8,699 | ok |  | [ ] |
| 98 | [Polycab Zoomer with 1 Year Warranty 600 mm Ceiling Fan (White / P... more](https://flipkart.com/polycab-zoomer-1-year-warranty-600-mm-ceiling-fan/p/itm274d93e1c41a1?pid=FANFHRJ2PBBF52UC) | FANFHRJ2PBBF52UC | ₹2,500 | N/A | error | product_page_price_not_exposed | [ ] |
| 99 | [ASSEMBLEX CORA G RYZEN 3 3200G AMD RYZEN 3 3200G (16 GB RAM/RX 550 Graphics/2 ](https://www.flipkart.com/assemblex-cora-g-ryzen-3-3200g-amd-16-gb-ram-rx-550-graphics-2-tb-hard-disk-512-ssd-capacity-windows-11-pro-4-graphics-memory-gaming-tower/p/itm18dc463640d44?pid=CPUHNYJYFUAQH2VM) | CPUHNYJYFUAQH2VM | ₹50,000 | N/A | error | product_identity_unverified | [ ] |
| 100 | [Hindware Immedio Packs of 1 3 L Instant Water Geyser](https://www.flipkart.com/hindware-immedio-packs-1-3-l-instant-water-geyser/p/itme95cfbd44327d?pid=WGYH6RUXHAQYPGGG) | WGYH6RUXHAQYPGGG | ₹2,854 | N/A | error | html_read_failed | [ ] |

## Croma - 100 products

| # | Open product | SKU | MongoDB price | Fresh price | Status | Error | Manual verified |
|---:|---|---|---:|---:|---|---|---|
| 1 | [O GENERAL 1.8 Ton 2 Star Non Inverter Window AC (Copper Condenser, AXGB22BBAA-](https://crma.clnk.in/CeD7) | 300588 | ₹47,790 | N/A | no_price |  | [ ] |
| 2 | [Symphony Arctic Circle 100 Litres Desert Air Cooler with i-Pure+ Technology (I](https://crma.clnk.in/CevJ) | 313205 | ₹15,130 | ₹15,130 | ok |  | [ ] |
| 3 | [Crompton Energion Cookie 1200mm 3 Blade BLDC Motor Ceiling Fan with Remote (Su](https://crma.clnk.in/Cd6C) | 303035 | ₹2,750 | ₹2,750 | ok |  | [ ] |
| 4 | [Buy Apple Mac mini M4 Chip Mini Tower (16GB, 512GB SSD, 10-core GPU, macOS, Si](https://crma.clnk.in/CfiA) | 324381 | ₹118,900 | ₹118,900 | ok |  | [ ] |
| 5 | [Buy IZI Mini X Drone Combo (3 Axis Stabilized Gimbal, Dark Green) Online - Cro](https://crma.clnk.in/Cfi9) | 304513 | ₹42,199 | ₹42,199 | ok |  | [ ] |
| 6 | [Crompton Solarium Elite 3 Litre Vertical Instant Geyser with Anti Scale Techno](https://crma.clnk.in/Cd7m) | 316342 | ₹3,999 | ₹3,999 | ok |  | [ ] |
| 7 | [Oppo Enco Buds 3 Pro Plus ETEE1 TWS Earbuds with Active Noise Cancellation (IP](https://crma.clnk.in/Cd8f) | 320250 | ₹2,999 | ₹2,999 | ok |  | [ ] |
| 8 | [Pigeon Acer Plus 1800W Induction Cooktop with 8 Preset Menus](https://crma.clnk.in/Cd94) | 227016 | ₹1,999 | ₹1,999 | ok |  | [ ] |
| 9 | [DELL DC 15250 Intel Core 3 Thin & Light Laptop (8GB, 512GB SSD, Windows 11, 15](https://crma.clnk.in/CfcV) | 318510 | ₹44,894 | ₹44,894 | ok |  | [ ] |
| 10 | [Agaro Marvel 25L Oven Toaster Grill with Motorised Rotisserie (Black)](https://crma.clnk.in/Cfft) | 321922 | ₹2,099 | ₹2,099 | ok |  | [ ] |
| 11 | [Crompton DX500 500 Watt 3 Jars Mixer Grinder (Motor Vent-X Technology, Black &](https://crma.clnk.in/CeEQ) | 317102 | ₹2,449 | N/A | no_price |  | [ ] |
| 12 | [Electrolux 600 Series 565 Litres 4 Star Frost Free French Door Refrigerator wi](https://crma.clnk.in/Cec9) | 319009 | ₹85,490 | ₹85,490 | ok |  | [ ] |
| 13 | [Buy Apple iPhone 13 (128GB, Starlight White) Online - Croma](https://crma.clnk.in/CxNt) | 243460 | ₹45,690 | N/A | no_price |  | [ ] |
| 14 | [SAMSUNG Series 4 80 cm (32 inch) HD Ready LED Smart Tizen TV with Hyper Real P](https://crma.clnk.in/CfdM) | 226403 | ₹11,984 | N/A | no_price |  | [ ] |
| 15 | [noise Twist Go Smartwatch with Bluetooth Calling (35mm TFT Display, IP67 Water](https://crma.clnk.in/CeLl) | 305120 | ₹1,899 | ₹1,899 | ok |  | [ ] |
| 16 | [Croma 60W RMS Boombox with Portable Handle (IP67 Water Resistant, 5H Playback,](https://crma.clnk.in/CeRn) | 303052 | ₹8,994 | ₹8,994 | ok |  | [ ] |
| 17 | [Xiaomi Pad 7 Wi-Fi Android Tablet (11.16 Inch, 12GB RAM, 256GB ROM, Graphite G](https://crma.clnk.in/Ceu5) | 312797 | ₹31,999 | N/A | no_price |  | [ ] |
| 18 | [EUREKA FORBES Kordfree K22 220W Cordless Dry Vacuum Cleaner with Powerful Cycl](https://crma.clnk.in/Ceiy) | 314618 | ₹15,999 | ₹15,999 | ok |  | [ ] |
| 19 | [SAMSUNG 8 kg 5 Star Wi-Fi Inverter Fully Automatic Top Load Washing Machine (W](https://crma.clnk.in/CeJw) | 315426 | ₹24,390 | ₹24,390 | ok |  | [ ] |
| 20 | [Aquaguard Blaze Insta 5.6L UV + UF Hot & Ambient Water Purifier with Active Co](https://crma.clnk.in/CekA) | 307019 | ₹10,000 | ₹10,000 | ok |  | [ ] |
| 21 | [Croma 1.5 Ton 5 Star Inverter Window AC with Self Diagnosis (2025 Model, Coppe](https://crma.clnk.in/Cd4U) | 312019 | ₹30,994 | N/A | no_price |  | [ ] |
| 22 | [VOLTAS Thunder 85 Litres Desert Air Cooler with Thermal Overload Protection (3](https://crma.clnk.in/Cfgx) | 313036 | ₹14,290 | ₹14,290 | ok |  | [ ] |
| 23 | [Crompton Surebreeze Hillbriz Deco 1 Star 1200mm 3 Blade High Velocity Ceiling ](https://crma.clnk.in/CeFd) | 303106 | ₹1,975 | N/A | no_price |  | [ ] |
| 24 | [ASUS AiO V470 V470VA-KWPE006WS 27 Inch Full HD IPS Display Intel Core i7 13th ](https://crma.clnk.in/Cd6U) | 315879 | ₹92,990 | ₹95,990 | ok |  | [ ] |
| 25 | [Croma 5 Litre Instant Geyser with Efficient Thermostat (2025 Model, White)](https://crma.clnk.in/Cd6Z) | 311097 | ₹4,499 | ₹4,499 | ok |  | [ ] |
| 26 | [OnePlus Bullets Z3 Neckband with Environmental Noise Cancellation (IP55 Water ](https://crma.clnk.in/Ce4h) | 316447 | ₹1,999 | ₹1,999 | ok |  | [ ] |
| 27 | [HAVELLS Insta Cook TC20 2000W Single Induction Cooktop with 9 Preset Menus](https://crma.clnk.in/Cd9V) | 274590 | ₹5,999 | ₹5,999 | ok |  | [ ] |
| 28 | [ASUS Vivobook Go 15 E1504FA-BQ2490WS AMD Ryzen 5 Thin and Light Laptop (16GB, ](https://crma.clnk.in/CezN) | 320759 | ₹49,990 | N/A | no_price |  | [ ] |
| 29 | [Croma 23L Convection Microwave Oven with 205 Auto Cook Menus (CRAM0151, Black)](https://crma.clnk.in/CebK) | 221297 | ₹11,499 | ₹11,499 | ok |  | [ ] |
| 30 | [BOSCH TrueMixx 750 Watt 4 Jars Mixer Grinder (22000 RPM, HiFlux Motor, Black)](https://crma.clnk.in/Ceoe) | 231666 | ₹5,499 | ₹5,499 | ok |  | [ ] |
| 31 | [Whirlpool Intellifresh Pro 285 Litres 2 Star Frost Free Double Door Bottom Mou](https://crma.clnk.in/CedL) | 269877 | ₹31,890 | N/A | no_price |  | [ ] |
| 32 | [SAMSUNG Galaxy A56 5G (12GB RAM, 256GB, Awesome Graphite)](https://crma.clnk.in/CesK) | 314433 | ₹52,499 | ₹52,499 | ok |  | [ ] |
| 33 | [SAMSUNG Series 4 80 cm (32 inch) HD Ready LED Smart Tizen TV with Alexa Compat](https://crma.clnk.in/CfdY) | 238797 | ₹13,984 | N/A | no_price |  | [ ] |
| 34 | [Croma Velocity S1 Smartwatch with Bluetooth Calling (47mm AMOLED Display, IP68](https://crma.clnk.in/CeLk) | 318498 | ₹2,999 | ₹2,999 | ok |  | [ ] |
| 35 | [Marshall EMBERTON III 76W Bluetooth Speaker (IP67 Dust & Waterproof, 360 Degre](https://crma.clnk.in/Cegy) | 315478 | ₹17,999 | ₹16,999 | ok |  | [ ] |
| 36 | [SAMSUNG Galaxy Tab A11 Plus Wi-Fi+5G Android Tablet (11 Inch, 6GB RAM, 128GB R](https://crma.clnk.in/Ceia) | 319394 | ₹29,990 | ₹27,690 | ok |  | [ ] |
| 37 | [AGARO Ace 1600W Wet & Dry Vacuum Cleaner with Blower Function (2-in-1, Black)](https://crma.clnk.in/CeiA) | 270770 | ₹6,839 | ₹6,839 | ok |  | [ ] |
| 38 | [LG 10 kg 5 Star Fully Automatic Front Load Washing Machine (FHP1410Z5M.AMBQEIL](https://crma.clnk.in/CeiQ) | 301449 | ₹48,990 | ₹48,990 | ok |  | [ ] |
| 39 | [Aquaguard Aspire Halo 5L UV + RO + CU Alkaline Water Purifier with NanoPore Lo](https://crma.clnk.in/CfdO) | 323524 | ₹23,999 | ₹23,999 | ok |  | [ ] |
| 40 | [Blue Star G Series 5 in 1 Convertible 2 Ton 3 Star Inverter Split AC with Smar](https://crma.clnk.in/CeN6) | 322618 | ₹54,490 | N/A | no_price |  | [ ] |
| 41 | [Symphony Air Force 90 Litres Desert Air Cooler with Auto Louver Movement (Inve](https://crma.clnk.in/Cd5e) | 320554 | ₹9,050 | ₹9,050 | ok |  | [ ] |
| 42 | [Crompton Surebreeze Super Briz Deco 1 Star 1200mm 3 Blade Copper Motor Ceiling](https://crma.clnk.in/Cd6R) | 269998 | ₹2,199 | ₹2,199 | ok |  | [ ] |
| 43 | [Apple iMac 24 Inch 4.5K Retina Display 2024 (16GB, 256GB, M4 Chip, macOS Sequo](https://crma.clnk.in/CeUl) | 311753 | ₹134,900 | ₹174,900 | ok |  | [ ] |
| 44 | [Croma AV4315 3 Litres Instant Geyser with Rustproof Design (White)](https://crma.clnk.in/Cd64) | 311096 | ₹2,999 | N/A | no_price |  | [ ] |
| 45 | [noise Three Bluetooth Headphone with Mic (Google Assistant Enabled, Over Ear, ](https://crma.clnk.in/Ce0f) | 303326 | ₹1,799 | ₹1,999 | ok |  | [ ] |
| 46 | [Electrolux UltimateTaste 500 3700W Double Induction Cooktop with Pot Sensor](https://crma.clnk.in/Ceab) | 307722 | ₹50,990 | ₹50,990 | ok |  | [ ] |
| 47 | [Lenovo IdeaPad Slim 3 15AMN8 AMD Ryzen 5 7520U Thin & Light Laptop (16GB, 512G](https://crma.clnk.in/Ceaf) | 319577 | ₹53,490 | N/A | no_price |  | [ ] |
| 48 | [IFB 25SC4 25L Convection Microwave Oven with 26 Auto Menu (Metallic Silver)](https://crma.clnk.in/CeWT) | 187110 | ₹13,490 | ₹13,484 | ok |  | [ ] |
| 49 | [Panasonic 750 Watt 4 Jars Juicer Mixer Grinder (Double Safety Lock, Black)](https://crma.clnk.in/CenG) | 246167 | ₹10,029 | ₹9,999 | ok |  | [ ] |
| 50 | [LG 340 Litres 2 Star Frost Free Double Door Bottom Mount Smart Wifi Enabled Co](https://crma.clnk.in/CeoL) | 321265 | ₹57,490 | ₹52,490 | ok |  | [ ] |
| 51 | [oppo K13x 5G (8GB RAM, 128GB, Midnight Violet)](https://crma.clnk.in/CeX8) | 316308 | ₹14,999 | N/A | no_price |  | [ ] |
| 52 | [SAMSUNG T4380A Series 80 cm (32 inch) HD Ready LED Smart Tizen TV with PurColo](https://crma.clnk.in/CeO7) | 306641 | ₹13,990 | N/A | no_price |  | [ ] |
| 53 | [Redmi Move Bluetooth Android 6.0 Smartwatch (47mm AMOLED Display, 140+ Sports ](https://crma.clnk.in/Cef5) | 320506 | ₹3,999 | ₹3,999 | ok |  | [ ] |
| 54 | [SONY ULT FIELD 5 Portable Bluetooth Speaker (IP66, IP67 Water Resistant, Party](https://crma.clnk.in/CetL) | 316015 | ₹24,990 | ₹21,990 | ok |  | [ ] |
| 55 | [Buy Apple iPad Air 6th Generation Wi-Fi (11 Inch, 128GB, Starlight, 2026 Model](https://crma.clnk.in/Cfg8) | 324212 | ₹85,490 | ₹85,490 | ok |  | [ ] |
| 56 | [Eureka Forbes Tornado 1200W Dry Vacuum Cleaner with Cyclonic Technology (Auto ](https://crma.clnk.in/Ceix) | 321840 | ₹9,999 | ₹9,999 | ok |  | [ ] |
| 57 | [Electrolux 10 kg 5 Star Inverter Fully Automatic Front Load Washing Machine (U](https://crma.clnk.in/CeJH) | 319357 | ₹50,100 | ₹50,100 | ok |  | [ ] |
| 58 | [Aquaguard Aspire Blaze 5.6L RO + UV Hot & Cold Water Purifier with NanoPore Fi](https://crma.clnk.in/Cekn) | 316693 | ₹27,799 | ₹27,799 | ok |  | [ ] |
| 59 | [Godrej Regalis Convertible 1.5 Ton 3 Star Inverter Split AC with Wind Diffuse ](https://crma.clnk.in/CeSX) | 322314 | ₹39,990 | ₹36,990 | ok |  | [ ] |
| 60 | [Croma 60 Litres Desert Air Cooler with Inverter Compatible (Evaporative Coolin](https://crma.clnk.in/CevR) | 267355 | ₹9,499 | ₹10,999 | ok |  | [ ] |
| 61 | [Crompton Energion Hyperjet 5 Star 1200mm 3 Blade BLDC Motor Ceiling Fan with R](https://crma.clnk.in/Cd5L) | 300154 | ₹2,799 | ₹2,799 | ok |  | [ ] |
| 62 | [acer C2D 12.1 Inch TFT Display Intel Duo Windows Vista Home Basic Desktop (2GB](https://crma.clnk.in/Cd6W) | 167654 | ₹16,069 | ₹16,069 | ok |  | [ ] |
| 63 | [Croma 3 Litre Vertical Instant Geyser with Built-in Thermostat (2025 Model, Wh](https://crma.clnk.in/Cd7F) | 316401 | ₹3,199 | ₹3,199 | ok |  | [ ] |
| 64 | [SONY WF-C510 TWS Earbuds (IPX4 Waterproof, Siri & Google Voice Assistant, Blac](https://crma.clnk.in/CeFP) | 311067 | ₹4,990 | ₹3,990 | ok |  | [ ] |
| 65 | [PHILIPS HD4996/00 2100W Induction Cooktop with 8 Preset Menus](https://crma.clnk.in/Cd9T) | 306893 | ₹4,999 | ₹4,999 | ok |  | [ ] |
| 66 | [HP 15-fd0691TU Intel Core i3 13th Gen Thin & Light Laptop (12GB, 512GB SSD, Wi](https://crma.clnk.in/Ce9N) | 316465 | ₹51,494 | N/A | no_price |  | [ ] |
| 67 | [elica EPBIMWO G25 Nero Inox 25L 60cm Built-in Microwave with 8 Autocook Menus ](https://crma.clnk.in/CexM) | 225393 | ₹48,690 | ₹49,690 | ok |  | [ ] |
| 68 | [Prestige Endura 1000 Watt 4 Jars Juicer Mixer Grinder (Ball Bearing Technology](https://crma.clnk.in/Ceoc) | 307760 | ₹6,599 | ₹6,599 | ok |  | [ ] |
| 69 | [LG 343 Litres 2 Star Frost Free Double Door Convertible Refrigerator with Smar](https://crma.clnk.in/Ceph) | 321252 | ₹48,590 | ₹44,490 | ok |  | [ ] |
| 70 | [OnePlus 13s 5G (12GB RAM, 256GB, Green Silk)](https://crma.clnk.in/Ce2G) | 315929 | ₹52,999 | ₹52,999 | ok |  | [ ] |
| 71 | [SAMSUNG Series 4 80 cm (32 inch) HD Ready LED Smart Tizen TV with Hyper Real P](https://crma.clnk.in/CeoE) | 251190 | ₹15,490 | ₹15,490 | ok |  | [ ] |
| 72 | [SAMSUNG Galaxy Watch7 Wi-Fi+4G SIM Wear OS Smartwatch (33.3mm Super AMOLED Dis](https://crma.clnk.in/CefR) | 308288 | ₹33,999 | ₹33,999 | ok |  | [ ] |
| 73 | [SONY ULT Field 1 Portable Bluetooth Speaker (IP67 Waterproof, Massive Bass, Of](https://crma.clnk.in/Cet2) | 307212 | ₹9,990 | ₹7,990 | ok |  | [ ] |
| 74 | [Buy Apple iPad Air 6th Generation Wi-Fi (11 Inch, 256GB, Blue, 2026 Model) Onl](https://crma.clnk.in/Cfj8) | 324317 | ₹96,990 | ₹96,990 | ok |  | [ ] |
| 75 | [Buy DREAME X40 Ultra Robotic Vacuum Cleaner & Mop with Self Emptying (MopExten](https://crma.clnk.in/CfhS) | 315802 | ₹79,999 | ₹79,999 | ok |  | [ ] |
| 76 | [IFB 7 kg 5 Star Fully Automatic Top Load Washing Machine (TL701AG1, Triadic Pu](https://crma.clnk.in/Cejh) | 308876 | ₹23,100 | ₹23,100 | ok |  | [ ] |
| 77 | [Aquaguard Eden 6L RO + UV + MTDS + SS Smart Water Purifier with Active Copper ](https://crma.clnk.in/CeEH) | 250627 | ₹21,999 | ₹21,999 | ok |  | [ ] |
| 78 | [Blue Star M Series 5 in 1 Convertible 1 Ton 3 Star Hexa Inverter Split AC with](https://crma.clnk.in/CeTB) | 313923 | ₹32,294 | ₹32,290 | ok |  | [ ] |
| 79 | [Havells KoolMaster 65 Litres Desert Air Cooler with Bacteria Shield Honeycomb ](https://crma.clnk.in/Cev7) | 320235 | ₹9,970 | ₹9,970 | ok |  | [ ] |
| 80 | [Croma 5 Star 1200mm 3 Blade BLDC Motor Ceiling Fan with Remote (Sleep Function](https://crma.clnk.in/Cd5O) | 316459 | ₹2,499 | N/A | no_price |  | [ ] |
| 81 | [HP 27-cr1007in 27 Inch Full HD IPS Display Intel Core Ultra 7 Windows 11 Home ](https://crma.clnk.in/Cd6Y) | 308282 | ₹95,499 | ₹95,499 | ok |  | [ ] |
| 82 | [morphy richards Lavo EM 10 Litres 5 Star Vertical Storage Water Geyser with Gl](https://crma.clnk.in/CePy) | 228015 | ₹7,999 | ₹7,999 | ok |  | [ ] |
| 83 | [JLAB Go Pop ANC TWS Earbuds with Active Noise Cancellation (IP55 Sweat and Spl](https://crma.clnk.in/CeGY) | 314976 | ₹2,499 | ₹2,499 | ok |  | [ ] |
| 84 | [PHILIPS Daily Collection 2100W Induction Cooktop with 8 Power Settings](https://crma.clnk.in/Cd9Q) | 177061 | ₹3,999 | ₹3,999 | ok |  | [ ] |
| 85 | [Buy Acer Aspire Lite Intel Core i3 1305U 13th Gen Laptop (8GB, 512GB SSD, Wind](https://crma.clnk.in/CfiD) | 323723 | ₹60,999 | ₹60,999 | ok |  | [ ] |
| 86 | [elica 70L 60cm Built-in Microwave with Integral Cooling Fan (EPBI 1161 MTC BK,](https://crma.clnk.in/CexU) | 218221 | ₹59,249 | ₹59,249 | ok |  | [ ] |
| 87 | [Croma 500 Watt 3 Jars Mixer Grinder (Rust Resistant, White/Purple)](https://crma.clnk.in/Cenq) | 225092 | ₹1,399 | ₹1,399 | ok |  | [ ] |
| 88 | [Haier 328 Litres 3 Star Frost Free Double Door Convertible Refrigerator with F](https://crma.clnk.in/CepS) | 302249 | ₹31,490 | ₹27,994 | ok |  | [ ] |
| 89 | [OnePlus 13s 5G (12GB RAM, 256GB, Black Velvet)](https://crma.clnk.in/Cfd6) | 315927 | ₹52,999 | ₹52,999 | ok |  | [ ] |
| 90 | [iFFALCON Q73 109 cm (43 inch) QLED 4K Ultra HD Google TV with Dolby Vision & D](https://crma.clnk.in/CeyN) | 308106 | ₹29,399 | ₹29,399 | ok |  | [ ] |
| 91 | [Apple Watch SE 3 GPS+Cellular with Midnight Sport Band - M/L (44mm Retina LTPO](https://crma.clnk.in/CeLt) | 317499 | ₹33,900 | ₹33,900 | ok |  | [ ] |
| 92 | [Marshall Acton III 60W Portable Bluetooth Speaker (Signature Sound, Stereo Cha](https://crma.clnk.in/CegO) | 263534 | ₹27,999 | ₹20,999 | ok |  | [ ] |
| 93 | [SAMSUNG Galaxy Tab A11 Wi-Fi Android Tablet (8.68 Inch, 8GB RAM, 128GB ROM, Gr](https://crma.clnk.in/CeO2) | 318701 | ₹18,999 | N/A | no_price |  | [ ] |
| 94 | [PHILIPS 5000 Series 1900W Cordless Dry Vacuum Cleaner with PowerCyclone 7 Tech](https://crma.clnk.in/Cfmr) | 259150 | ₹11,198 | N/A | no_price |  | [ ] |
| 95 | [SAMSUNG 8 kg 5 Star Wi-Fi Inverter Fully Automatic Top Load Washing Machine (W](https://crma.clnk.in/CeJu) | 315428 | ₹22,960 | ₹23,440 | ok |  | [ ] |
| 96 | [Aquaguard Blaze Insta 5.6L RO + UV + TA Hot & Ambient Water Purifier with Acti](https://crma.clnk.in/CeEI) | 303711 | ₹15,000 | N/A | no_price |  | [ ] |
| 97 | [Blue Star M Series 5 in 1 Convertible 1 Ton 3 Star Hexa Inverter Split AC with](https://crma.clnk.in/CeTT) | 313950 | ₹32,994 | ₹32,990 | ok |  | [ ] |
| 98 | [Crompton Supremus 100 Litres Desert Air Cooler (Honeycomb Pads, ACGC-SUPREMUS1](https://crma.clnk.in/Cewn) | 305340 | ₹9,999 | ₹9,999 | ok |  | [ ] |
| 99 | [HAVELLS Stealth Neo 5 Star 1200mm 3 Blade BLDC Motor Ceiling Fan with Remote (](https://crma.clnk.in/Cd6g) | 304597 | ₹8,249 | ₹8,249 | ok |  | [ ] |
| 100 | [ASUS AiO 27 Inch Full HD IPS Display Intel Core i3 Windows 11 Home Desktop (8G](https://crma.clnk.in/CeO8) | 323070 | ₹75,990 | ₹68,990 | ok |  | [ ] |
