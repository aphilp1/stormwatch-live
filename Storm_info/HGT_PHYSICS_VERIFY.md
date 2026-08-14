# HGT + physics verification (recomputed from committed CSV + station_results JSON)

Hypothesis (Opus): a station ABOVE the BC pressure level (elev > HGT) gets at/below-ground air
as its 850/700 "wind", so WN(850) overshoots and WN(10m) should win there more often.
Test: gap = station_elev - HGT(bc_level); cross-tab WN10m-beats-WN850 by gap sign. Scorable only.

## Per-event HGT domain mean (physical sanity: 700mb > 850mb; cold events lower)
| event | bc_level | HGT mean m | n |
|---|---|--:|--:|
| boulder_chin2021 | NEEDS_BC mb | 3080 | 9 |
| camp_2018 | 850 mb | 1549 | 12 |
| iowa_derecho2020 | 850 mb | 1521 | 2 |
| kincade_ign_2019 | 850 mb | 1536 | 10 |
| kincade_run_2019 | 850 mb | 1444 | 12 |
| labor_day_or2020 | 700 mb | 3171 | 35 |
| marshall_2021 | 700 mb | 2897 | 8 |
| missoula_dec2025 | 700 mb | 2838 | 8 |
| missoula_jul2024 | NEEDS_BC mb | 1503 | 18 |
| thomas_2017 | 850 mb | 1513 | 26 |
| tubbs_2017 | 850 mb | 1481 | 7 |
| woolsey_2018 | 850 mb | 1526 | 17 |

## Cross-tab: WN(10m) beats WN(850), split by station height vs BC level
| group | n | WN10m beats WN850 | rate |
|---|--:|--:|--:|
| station ABOVE BC level (elev > HGT) | 6 | 3 | 50% |
| station BELOW BC level (elev < HGT) | 43 | 30 | 70% |

Total scorable with HGT: 49. Above=6 Below=43.

## All scorable stations (line-by-line, sorted by gap desc)
| event | stn | elev m | HGT m | gap m | |WN10m| | |WN850| | WN10m wins |
|---|---|--:|--:|--:|--:|--:|:--:|
| missoula_jul2024 | PNTM8 | 2417 | 1502 | +915 | 4.6 | 3.6 |  |
| camp_2018 | HMRC1 | 2048 | 1565 | +484 | 14.1 | 14.1 |  |
| camp_2018 | SLEC1 | 2025 | 1542 | +483 | 12.0 | 14.1 | Y |
| camp_2018 | CBXC1 | 1825 | 1555 | +269 | 0.5 | 6.4 | Y |
| woolsey_2018 | CUUC1 | 1608 | 1537 | +71 | 2.6 | 1.3 |  |
| missoula_jul2024 | MOMM8 | 1563 | 1504 | +59 | 1.9 | 14.5 | Y |
| kincade_ign_2019 | HGLC1 | 1469 | 1538 | -69 | 11.0 | 16.7 | Y |
| marshall_2021 | PKLC2 | 2835 | 2908 | -73 | 9.4 | 19.5 | Y |
| camp_2018 | CDEC1 | 1468 | 1546 | -78 | 2.4 | 23.5 | Y |
| missoula_jul2024 | FINM8 | 1349 | 1506 | -157 | 5.7 | 13.3 | Y |
| camp_2018 | CESC1 | 1383 | 1584 | -201 | 0.2 | 3.9 | Y |
| missoula_jul2024 | MTGRN | 1248 | 1502 | -254 | 0.9 | 6.1 | Y |
| camp_2018 | PKCC1 | 1125 | 1530 | -406 | 11.9 | 30.5 | Y |
| missoula_dec2025 | PNTM8 | 2417 | 2838 | -421 | 0.4 | 53.7 | Y |
| missoula_jul2024 | G0378 | 1061 | 1502 | -440 | 2.8 | 12.4 | Y |
| marshall_2021 | CEKC2 | 2441 | 2899 | -458 | 15.6 | 5.5 |  |
| missoula_jul2024 | BLMM8 | 1033 | 1501 | -468 | 4.2 | 12.7 | Y |
| missoula_jul2024 | E0591 | 1031 | 1501 | -470 | 18.8 | 0.1 |  |
| marshall_2021 | DMTC2 | 2437 | 2914 | -477 | 4.3 | 9.5 | Y |
| missoula_jul2024 | E8564 | 1013 | 1504 | -492 | 0.3 | 1.7 | Y |
| kincade_ign_2019 | COWC1 | 1020 | 1538 | -518 | 4.4 | 4.3 |  |
| missoula_jul2024 | SYN72773 | 976 | 1502 | -527 | 1.7 | 9.6 | Y |
| missoula_jul2024 | KMSO | 974 | 1503 | -529 | 8.9 | 6.8 |  |
| marshall_2021 | LOOC2 | 2295 | 2877 | -582 | 12.6 | 43.2 | Y |
| missoula_jul2024 | G2298 | 923 | 1510 | -587 | 1.9 | 13.0 | Y |
| missoula_jul2024 | MTNNM | 915 | 1512 | -597 | 2.8 | 14.4 | Y |
| kincade_ign_2019 | HPDC1 | 802 | 1537 | -735 | 4.4 | 3.8 |  |
| marshall_2021 | CTPC2 | 2150 | 2894 | -744 | 4.8 | 24.3 | Y |
| camp_2018 | JBGC1 | 766 | 1536 | -771 | 16.2 | 2.6 |  |
| marshall_2021 | BTAC2 | 2050 | 2874 | -824 | 15.5 | 38.8 | Y |
| kincade_ign_2019 | KNXC1 | 663 | 1537 | -875 | 6.1 | 6.4 | Y |
| kincade_ign_2019 | KELC1 | 661 | 1537 | -876 | 2.9 | 23.2 | Y |
| kincade_ign_2019 | WISC1 | 635 | 1542 | -907 | 0.1 | 8.3 | Y |
| kincade_ign_2019 | HWKC1 | 619 | 1532 | -913 | 7.0 | 6.3 |  |
| kincade_ign_2019 | ATLC1 | 616 | 1531 | -915 | 5.2 | 18.7 | Y |
| kincade_ign_2019 | OAAC1 | 582 | 1536 | -953 | 0.4 | 0.1 |  |
| camp_2018 | CSTC1 | 528 | 1542 | -1014 | 1.8 | 18.5 | Y |
| boulder_chin2021 | UP736 | 2031 | 3080 | -1049 | 12.0 | 7.9 |  |
| iowa_derecho2020 | HITI4 | 388 | 1519 | -1131 | 16.0 | 7.4 |  |
| boulder_chin2021 | CO109 | 1902 | 3080 | -1178 | 15.1 | 26.0 | Y |
| boulder_chin2021 | E9688 | 1878 | 3081 | -1203 | 2.4 | 8.0 | Y |
| iowa_derecho2020 | DEOI4 | 306 | 1523 | -1217 | 5.9 | 0.9 |  |
| boulder_chin2021 | RFN | 1802 | 3081 | -1278 | 20.1 | 28.0 | Y |
| marshall_2021 | AENC2 | 1600 | 2899 | -1299 | 4.1 | 16.7 | Y |
| boulder_chin2021 | C7944 | 1738 | 3080 | -1342 | 16.8 | 15.2 |  |
| kincade_ign_2019 | RSAC1 | 182 | 1530 | -1348 | 11.1 | 6.1 |  |
| boulder_chin2021 | ATC01 | 1643 | 3079 | -1436 | 0.0 | 5.6 | Y |
| camp_2018 | CICC1 | 81 | 1540 | -1459 | 9.2 | 14.0 | Y |
| boulder_chin2021 | E3608 | 1603 | 3079 | -1477 | 12.0 | 13.8 | Y |