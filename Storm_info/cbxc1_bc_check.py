import csv
with open(r'C:\Users\aphil\Documents\Stormwatch\Storm_info\hrrr_error_dataset.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['event_id'] == 'camp_2018' and row['stid'] == 'CBXC1':
            for k, v in row.items():
                print(f'{k}: {v}')
            break
