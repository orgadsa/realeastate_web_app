# Real Estate Listing Scraper 🏠

כלי לחילוץ מידע ממודעות נדל"ן מאתרים ישראליים וייצוא ל-Google Sheets.

## אתרים נתמכים

- **יד2** (yad2.co.il)
- **מדלן** (madlan.co.il)

## מידע שנחלץ

- כתובת, עיר, שכונה
- מחיר
- מספר חדרים, שטח (מ"ר), קומה
- סוג נכס, תאריך כניסה
- מאפיינים (חניה, מעלית, מרפסת, ממ"ד, מיזוג, ריהוט)
- פרטי קשר (שם, טלפון)
- תמונות

## התקנה

```bash
pip install -r requirements.txt
playwright install chromium
```

## הגדרת Google Sheets (חד פעמי)

1. היכנס ל-[Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. צור פרויקט חדש (או השתמש בקיים)
3. הפעל את **Google Sheets API** ו-**Google Drive API**
4. צור **Service Account** → הורד את קובץ ה-JSON
5. שמור את הקובץ כ-`credentials.json` בתיקיית הפרויקט
6. שתף את ה-Google Sheet עם המייל של ה-Service Account (מסתיים ב-`@...iam.gserviceaccount.com`)

## שימוש

### מודעה בודדת (JSON בלבד)
```bash
python3 -m scraper "https://www.yad2.co.il/realestate/item/..."
```

### ייצוא ל-Google Sheets (יוצר גיליון חדש)
```bash
python3 -m scraper "https://www.yad2.co.il/realestate/item/..." --sheet
```

### ייצוא לגיליון קיים (מוסיף שורות)
```bash
python3 -m scraper "https://www.yad2.co.il/realestate/item/..." --sheet-url "https://docs.google.com/spreadsheets/d/..."
```

### מספר מודעות
```bash
python3 -m scraper "URL1" "URL2" "URL3" --sheet
```

### מקובץ טקסט
```bash
python3 -m scraper --file urls.txt --sheet
```

## פלט

- **Google Sheets**: טבלה מסודרת עם כל הפרטים (RTL, כותרות מודגשות)
- **JSON**: נשמר תמיד גם בתיקיית `output/` כגיבוי
